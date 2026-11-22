"""Curated companies, read through their ATS (hiring system) public feeds.

`detect()` works out which ATS a company uses, once. `fetch()` then reads its
open jobs every day. Career pages are only opened during detection.
"""
import json
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests

from .sources import UA, clean, job

TIMEOUT = 20
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/126.0 Safari/537.36")  # Workday turns away anything that does not look like a browser

# (ATS name, pattern with the board id in group 1). Checked in this order.
PATTERNS = [
    ("Greenhouse", r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?([a-z0-9_-]+)"),
    ("Greenhouse", r"boards-api\.greenhouse\.io/v1/boards/([a-z0-9_-]+)"),
    ("Lever", r"jobs\.(?:eu\.)?lever\.co/([a-z0-9_.-]+)"),
    ("Ashby", r"jobs\.ashbyhq\.com/([a-z0-9_.%-]+)"),
    ("Workable", r"apply\.workable\.com/([a-z0-9_-]+)"),
    ("Workable", r"https?://([a-z0-9-]+)\.workable\.com"),
    ("SmartRecruiters", r"(?:careers|jobs)\.smartrecruiters\.com/([a-z0-9_-]+)"),
    ("Personio", r"https?://([a-z0-9-]+\.jobs\.personio\.(?:de|com))"),
    ("Recruitee", r"https?://([a-z0-9-]+)\.recruitee\.com"),
    ("Teamtailor", r"https?://([a-z0-9-]+)\.teamtailor\.com"),
    ("Workday", r"https?://([a-z0-9_-]+\.wd\d+\.myworkdayjobs\.com/(?:[a-z]{2}-[a-z]{2}/)?[a-z0-9_-]+)"),
]
SKIP_IDS = {"embed", "job_board", "www", "apply", "jobs", "careers", "api", "app", "help", "support",
            "widget", "js", "assets", "static", "cdn", "j", "get", "www2", "blog", "resources", "try",
            "info", "status", "id", "docs", "developers", "partners", "community", "hire", "recruiting"}


def _get(url, kind="json", **kwargs):
    for wait in (4, 10, None):  # a busy feed (429/503) gets two more tries
        response = requests.get(url, headers=UA, timeout=TIMEOUT, **kwargs)
        if response.status_code not in (429, 503) or wait is None:
            break
        time.sleep(wait)
    response.raise_for_status()
    return response.json() if kind == "json" else response.text


def find_all(text):
    """Every distinct ATS link in a URL or a page's HTML, in the order of PATTERNS."""
    out = []
    for name, pattern in PATTERNS:
        for match in re.finditer(pattern, text, flags=re.I):
            board = match.group(1).strip("/")
            if board.split(".")[0].lower() not in SKIP_IDS and (name, board) not in out:
                out.append((name, board))
    return out


def find_ats(text):
    """First ATS link found in a URL or a page's HTML."""
    found = find_all(text)
    return found[0] if found else ("", "")


# ------------------------------------------------------------------ fetchers
def _greenhouse(board, company):
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
    return [job(company, j.get("title"), company, j.get("absolute_url"),
                location=(j.get("location") or {}).get("name"), description=clean(clean(j.get("content"))),
                posted=j.get("first_published") or j.get("updated_at"), job_id=j.get("id"))
            for j in data.get("jobs") or []]


def _lever(board, company):
    try:
        data = _get(f"https://api.lever.co/v0/postings/{board}?mode=json")
    except requests.RequestException:
        data = _get(f"https://api.eu.lever.co/v0/postings/{board}?mode=json")
    out = []
    for j in data if isinstance(data, list) else []:
        cats = j.get("categories") or {}
        text = " \n".join([j.get("descriptionPlain") or ""] +
                          [f"{l.get('text', '')}\n{l.get('content', '')}" for l in j.get("lists") or []] +
                          [j.get("additionalPlain") or ""])
        out.append(job(company, j.get("text"), company, j.get("hostedUrl"),
                       location=cats.get("location") or ", ".join(cats.get("allLocations") or []),
                       remote=True if j.get("workplaceType") == "remote" else None,
                       description=text, posted=j.get("createdAt"), job_id=j.get("id")))
    return out


def _ashby(board, company):
    data = _get(f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true")
    out = []
    for j in data.get("jobs") or []:
        if j.get("isListed") is False:
            continue
        places = [j.get("location") or ""] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        out.append(job(company, j.get("title"), company, j.get("jobUrl"),
                       location=", ".join(p for p in places if p),
                       remote=True if j.get("isRemote") else None,
                       description=j.get("descriptionPlain") or j.get("descriptionHtml"),
                       posted=j.get("publishedAt"), job_id=j.get("id"),
                       salary=(j.get("compensation") or {}).get("scrapeableCompensationSalarySummary")
                       or (j.get("compensation") or {}).get("compensationTierSummary") or "",
                       arrangement={"Remote": "Remote", "Hybrid": "Hybrid", "OnSite": "On-site"}
                       .get(j.get("workplaceType") or "", "")))
    return out


def _workable(board, company):
    data = _get(f"https://apply.workable.com/api/v1/widget/accounts/{board}?details=true")
    return [job(company, j.get("title"), company, j.get("url") or j.get("shortlink"),
                location=", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x),
                remote=True if j.get("telecommuting") else False,
                restrictions=[j.get("country")] if j.get("telecommuting") else [],
                description=j.get("description"), posted=j.get("published_on") or j.get("created_at"),
                job_id=j.get("shortcode"))
            for j in data.get("jobs") or []]


def _smartrecruiters(board, company):
    out, offset = [], 0
    while offset < 500:
        data = _get(f"https://api.smartrecruiters.com/v1/companies/{board}/postings",
                    params={"limit": 100, "offset": offset})
        rows = data.get("content") or []
        for j in rows:
            loc = j.get("location") or {}
            out.append(job(company, j.get("name"), company,
                           f"https://jobs.smartrecruiters.com/{board}/{j.get('id')}",
                           location=", ".join(x for x in (loc.get("city"), loc.get("country", "").upper()) if x),
                           remote=True if loc.get("remote") else None,
                           posted=j.get("releasedDate"), job_id=j.get("id")))
        offset += 100
        if len(rows) < 100:
            break
    return out


def _personio(board, company):
    root = ET.fromstring(_get(f"https://{board}/xml?language=en", kind="text"))
    out = []
    for p in root.findall(".//position"):
        text = " \n".join(f"{d.findtext('name') or ''}\n{d.findtext('value') or ''}"
                          for d in p.findall(".//jobDescription"))
        out.append(job(company, p.findtext("name"), company, f"https://{board}/job/{p.findtext('id')}",
                       location=p.findtext("office"), description=text,
                       posted=p.findtext("createdAt"), job_id=p.findtext("id")))
    return out


def _recruitee(board, company):
    data = _get(f"https://{board}.recruitee.com/api/offers/")
    return [job(company, j.get("title"), company, j.get("careers_url"),
                location=", ".join(x for x in (j.get("city"), j.get("country")) if x) or j.get("location"),
                remote=True if j.get("remote") else None,
                description=f"{j.get('description') or ''}\n{j.get('requirements') or ''}",
                posted=j.get("published_at") or j.get("created_at"), job_id=j.get("id"))
            for j in data.get("offers") or []]


def _teamtailor(board, company):
    host = board if "." in board else f"{board}.teamtailor.com"  # own domains work too
    root = ET.fromstring(_get(f"https://{host}/jobs.rss", kind="text"))
    out = []
    for item in root.findall("./channel/item"):
        places = [el.text or "" for el in item.iter() if el.tag.endswith("}city") or el.tag.endswith("}country")]
        remote = next((el.text for el in item.iter() if el.tag.endswith("remoteStatus")), "") or ""
        out.append(job(company, item.findtext("title"), company, item.findtext("link"),
                       location=", ".join(dict.fromkeys(p for p in places if p)),
                       remote=True if "fully" in remote.lower() else None,
                       description=item.findtext("description"), posted=item.findtext("pubDate"),
                       job_id=item.findtext("guid")))
    return out


WORKDAY_SEARCHES = ("operations", "ecommerce", "marketplace", "automation", "coordinator",
                    "specialist", "assistant", "Greece")


def _workday(board, company):
    match = re.match(r"([a-z0-9_-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[a-z]{2}/)?([a-z0-9_-]+)", board, re.I)
    if not match:
        return []
    tenant, shard, site = match.groups()
    base = f"https://{tenant}.{shard}.myworkdayjobs.com"
    out, seen = [], set()
    for text in WORKDAY_SEARCHES:
        response = requests.post(f"{base}/wday/cxs/{tenant}/{site}/jobs", timeout=TIMEOUT,
                                 headers={"User-Agent": BROWSER_UA, "Content-Type": "application/json",
                                          "Accept": "application/json", "Origin": base,
                                          "Referer": f"{base}/{site}"},
                                 data=json.dumps({"limit": 20, "offset": 0, "searchText": text,
                                                  "appliedFacets": {}}))
        response.raise_for_status()
        for j in response.json().get("jobPostings") or []:
            path = j.get("externalPath")
            if not path or path in seen:
                continue
            seen.add(path)
            out.append(job(company, j.get("title"), company, f"{base}/{site}{path}",
                           location=j.get("locationsText"), job_id=path))
    return out


FETCHERS = {"Greenhouse": _greenhouse, "Lever": _lever, "Ashby": _ashby, "Workable": _workable,
            "SmartRecruiters": _smartrecruiters, "Personio": _personio, "Recruitee": _recruitee,
            "Teamtailor": _teamtailor, "Workday": _workday}


def fetch(ats, board, company):
    found = [j for j in FETCHERS[ats](board, company) if j]
    for j in found:
        j["source"] = f"Company list ({ats})"
        if j["remote"] is None and re.search(r"\bremote\b", j["location"], flags=re.I):
            j["remote"] = True
    return found


# ------------------------------------------------------------------ detection
def _slugs(name, website):
    base = re.sub(r"\(.*?\)", "", name.lower())
    base = re.sub(r"\b(?:s\.?a\.?|group|ltd|gmbh|inc|hellas|greece)\b", "", base)
    words = re.findall(r"[a-z0-9]+", base)
    out = ["".join(words), "-".join(words)]
    host = urlparse(website if "//" in website else f"https://{website}").hostname or ""
    labels = [l for l in host.split(".") if l not in ("www", "careers", "jobs", "career", "corporate", "group")]
    if labels:
        out.append(labels[0])
    return [s for s in dict.fromkeys(out) if len(s) >= 3]


def _same_company(name, other):
    a = set(re.findall(r"[a-z0-9]{3,}", name.lower()))
    b = set(re.findall(r"[a-z0-9]{3,}", str(other or "").lower()))
    return bool(a & b)


def _guesses(name, website):
    """Boards whose id is the company's name, on the ATSs where that can be tried.
    Where the feed shows the company name, it has to match."""
    out = []

    def attempt(ats, slug, url, check):
        try:
            if check(_get(url)):
                out.append((ats, slug))
        except (requests.RequestException, ValueError, AttributeError, TypeError):
            pass

    for slug in _slugs(name, website):
        attempt("Greenhouse", slug, f"https://boards-api.greenhouse.io/v1/boards/{slug}",
                lambda d: _same_company(name, d.get("name")))
        attempt("Ashby", slug, f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                lambda d: bool(d.get("jobs")))
        attempt("Lever", slug, f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=1",
                lambda d: isinstance(d, list) and bool(d))
        attempt("Workable", slug, f"https://apply.workable.com/api/v1/widget/accounts/{slug}",
                lambda d: bool(d.get("jobs")) and _same_company(name, d.get("name")))
        attempt("SmartRecruiters", slug, f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1",
                lambda d: bool(d.get("content")) and
                _same_company(name, (d["content"][0].get("company") or {}).get("name")))
        attempt("Recruitee", slug, f"https://{slug}.recruitee.com/api/offers/",
                lambda d: bool(d.get("offers")) and _same_company(name, d["offers"][0].get("company_name")))
        for ats, board in (("Teamtailor", slug), ("Personio", f"{slug}.jobs.personio.de"),
                           ("Personio", f"{slug}.jobs.personio.com")):
            if _count(ats, board, name) > 0:  # these feeds carry no company name; the address is the company's own
                out.append((ats, board))
                break
    return out


def _looks_like(name, website, board):
    """True when a board id resembles the company's own name."""
    whole = re.sub(r"[^a-z0-9]", "", board.lower())
    board = re.sub(r"[^a-z0-9]", "", board.split(".")[0].lower())
    for slug in _slugs(name, website):
        slug = slug.replace("-", "")
        if slug and board and (slug in board or board in slug or slug in whole):
            return True
    return False


ERRORS = {}  # (ats, board) -> why the feed could not be read


def _count(ats, board, name):
    """Number of open jobs on a board, or -1 when the feed cannot be read."""
    try:
        return len(fetch(ats, board, name))
    except Exception as exc:  # noqa: BLE001
        code = getattr(getattr(exc, "response", None), "status_code", "")
        ERRORS[(ats, board)] = f"{type(exc).__name__} {code}".strip()
        return -1


def _pages(website, careers):
    """Pages worth opening to look for a link to the company's hiring system."""
    pages = [careers] if careers else []
    if website:
        root = (website if "//" in website else f"https://{website}").rstrip("/")
        host = urlparse(root).hostname or ""
        bare = host[4:] if host.startswith("www.") else host
        pages += [f"{root}/careers", f"{root}/jobs", root, f"{root}/career", f"{root}/en/careers",
                  f"{root}/about/careers", f"{root}/company/careers", f"{root}/join-us"]
        if bare.count(".") == 1:
            pages += [f"https://careers.{bare}", f"https://jobs.{bare}"]
    return list(dict.fromkeys(pages))


def detect(name, website="", careers=""):
    """Returns (ats, board, status, jobs_count).

    Links on the company's own careers page come first, but only when the board
    has jobs and looks like this company. Then boards matched by company name.
    A board with no jobs is kept only if the careers page itself links to it."""
    website = "" if "not provided" in website.lower() else website.strip()
    careers = "" if "not provided" in careers.lower() else careers.strip()
    linked = find_all(f"{careers} {website}")
    if not linked:
        for page in _pages(website, careers):
            try:
                response = requests.get(page, headers=UA, timeout=12)
            except requests.RequestException:
                continue
            if response.status_code >= 400:
                continue
            linked = find_all(f"{response.url} {response.text[:600000]}")
            if not linked and "teamtailor" in response.text.lower():
                host = urlparse(response.url).hostname  # Teamtailor on the company's own domain
                if _count("Teamtailor", host, name) >= 0:
                    linked = [("Teamtailor", host)]
            if linked:
                break
    linked = [(a, b, _count(a, b, name)) for a, b in linked[:4]]
    for ats, board, count in linked:
        if count > 0 and _looks_like(name, website, board):
            return ats, board, "OK (found on careers page)", count
    guessed = [(a, b, _count(a, b, name)) for a, b in _guesses(name, website)
               if (a, b) not in [(x, y) for x, y, _ in linked]]
    guessed = sorted((g for g in guessed if g[2] > 0), key=lambda g: -g[2])
    if guessed:
        ats, board, count = guessed[0]
        return ats, board, "OK (matched by company name)", count
    for ats, board, count in linked:
        if count > 0:
            return ats, board, "OK (found on careers page, please check)", count
    for ats, board, count in linked:
        if count == 0 and _looks_like(name, website, board):
            return ats, board, "OK (no open jobs right now)", 0
    if linked:
        ats, board, count = linked[0]
        if count < 0:
            return ats, board, f"Feed error ({ERRORS.get((ats, board), 'unknown')})", 0
        return ats, board, "No feed found", 0
    return "", "", "No feed found", 0


def detect_many(companies, workers=6):
    """companies: [(name, website, careers)] -> same order list of detect() results."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda c: detect(*c), companies))


def fetch_many(boards, workers=8):
    """boards: [(company, ats, board)] -> (jobs, {company: count}, {company: error})."""
    def one(item):
        company, ats, board = item
        try:
            return company, fetch(ats, board, company), ""
        except Exception as exc:
            return company, [], f"{type(exc).__name__}: {exc}"[:120]
    jobs, counts, errors = [], {}, {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for company, found, error in pool.map(one, boards):
            jobs.extend(found)
            counts[company] = len(found)
            if error:
                errors[company] = error
    return jobs, counts, errors
