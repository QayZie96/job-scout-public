"""Readers for free public job feeds. No LLM, no scraping of career pages.

Every reader returns a list of jobs in one common shape (see `job()`), and
every reader may fail on its own without stopping the run.
"""
import html
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

from .extract import salary_range

UA = {"User-Agent": "Mozilla/5.0 (compatible; job-scout/1.0; personal job search)"}
TIMEOUT = 30


def clean(text):
    """HTML to plain text."""
    text = re.sub(r"<(br|/p|/li|/h\d|/div)[^>]*>", "\n", str(text or ""), flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def iso_date(value):
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).date().isoformat()
    value = str(value).strip()
    if re.match(r"^[A-Za-z]{3},", value):  # RFC 2822 (RSS)
        try:
            return parsedate_to_datetime(value).date().isoformat()
        except (TypeError, ValueError):
            return ""
    return value[:10]


def job(source, title, company, url, *, location="", remote=None, restrictions=None,
        description="", posted="", job_id="", salary="", arrangement=""):
    title, company, url = clean(title), clean(company), str(url or "").strip()
    if not title or not company or not url.startswith("http"):
        return None
    return {
        "source": source, "id": str(job_id or url), "title": title, "company": company,
        "url": url, "location": clean(location), "remote": remote,
        "restrictions": [str(r) for r in (restrictions or []) if r],
        "description": clean(description), "posted": iso_date(posted),
        "salary": clean(salary)[:60], "arrangement": arrangement,
    }


def _get(url, params=None, kind="json"):
    response = requests.get(url, params=params, headers=UA, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json() if kind == "json" else response.text


def _keep(items):
    return [i for i in items if i]


# ---------------------------------------------------------------- Workable
def workable(settings):
    """jobs.workable.com public search: Greek employers, Athens and Greece-remote."""
    seen, out = set(), []
    for location in settings["workable_locations"]:
        for keyword in [""] + list(settings["workable_keywords"]):
            params = {"location": location}
            if keyword:
                params["query"] = keyword
            try:
                data = _get("https://jobs.workable.com/api/v1/jobs", params)
            except requests.RequestException:
                continue
            for item in data.get("jobs") or []:
                if item.get("state") not in (None, "published") or item.get("id") in seen:
                    continue
                seen.add(item.get("id"))
                loc = item.get("location") or {}
                place = ", ".join(x for x in (loc.get("city"), loc.get("subregion"),
                                                   loc.get("countryName")) if x)
                workplace = item.get("workplace") or ""
                description = " \n".join(str(item.get(k) or "") for k in
                                         ("description", "requirementsSection", "benefitsSection"))
                out.append(job(
                    "Workable", item.get("title"), (item.get("company") or {}).get("title"),
                    item.get("url"), location=place or ", ".join(item.get("locations") or []),
                    remote=True if workplace == "remote" else False if workplace else None,
                    restrictions=[loc.get("countryName")] if workplace == "remote" else [],
                    description=description, posted=item.get("created"), job_id=item.get("id"),
                    arrangement={"remote": "Remote", "hybrid": "Hybrid", "on_site": "On-site",
                                 "onsite": "On-site"}.get(str(workplace).lower(), "")))
            time.sleep(0.4)
    return _keep(out)


def _known_place(place):
    from .screen import EU_CITIES, EU_COUNTRIES, NON_EU, _word
    text = f" {place.lower()} "
    return _word(text, EU_CITIES) or _word(text, EU_COUNTRIES) or _word(text, NON_EU)


# ---------------------------------------------------------------- Remote boards
def arbeitnow(settings):
    out, url, pages = [], "https://www.arbeitnow.com/api/job-board-api", 0
    while url and pages < 5:
        data = _get(url)
        pages += 1
        for item in data.get("data") or []:
            place = item.get("location") or ""
            # Arbeitnow is mostly a German board and often lists only a German town
            if place and "," not in place and not _known_place(place):
                place += ", Germany"
            out.append(job("Arbeitnow", item.get("title"), item.get("company_name"), item.get("url"),
                           location=place, remote=bool(item.get("remote")),
                           description=item.get("description"), posted=item.get("created_at"),
                           job_id=item.get("slug")))
        url = (data.get("links") or {}).get("next")
    return _keep(out)


def remotive(settings):
    data = _get("https://remotive.com/api/remote-jobs")
    return _keep(job("Remotive", i.get("title"), i.get("company_name"), i.get("url"),
                     location=i.get("candidate_required_location"), remote=True,
                     description=i.get("description"), posted=i.get("publication_date"),
                     job_id=i.get("id"), salary=i.get("salary") or "") for i in data.get("jobs") or [])


def himalayas(settings):
    out, seen = [], set()
    plans = [({"country": "GR", "sort": "recent", "page": p}) for p in (1, 2, 3)]
    plans += [{"q": q, "country": "GR", "sort": "recent"} for q in
              ("operations", "ecommerce", "automation", "assistant", "marketplace", "ai")]
    for params in plans:
        try:
            data = _get("https://himalayas.app/jobs/api/search", params)
        except requests.RequestException:
            continue
        for i in data.get("jobs") or []:
            guid = i.get("guid") or i.get("applicationLink")
            if guid in seen:
                continue
            seen.add(guid)
            restrictions = [r.get("name") or r.get("alpha2") for r in (i.get("locationRestrictions") or [])
                            if isinstance(r, dict)]
            out.append(job("Himalayas", i.get("title"), i.get("companyName"), i.get("applicationLink"),
                           location=", ".join(restrictions) or "Worldwide", remote=True,
                           # these searches are limited to jobs open to people in Greece
                           restrictions=(restrictions or ["Worldwide"]) + ["Greece"],
                           description=i.get("description") or i.get("excerpt"),
                           posted=i.get("pubDate"), job_id=guid,
                           salary=salary_range(i.get("minSalary"), i.get("maxSalary"),
                                               i.get("currency") or i.get("salaryCurrency"))))
        time.sleep(0.5)
    return _keep(out)


def jobicy(settings):
    out, seen = [], set()
    for geo in ("greece", "europe", "emea"):
        try:
            data = _get("https://jobicy.com/api/v2/remote-jobs", {"count": 50, "geo": geo})
        except requests.RequestException:
            continue
        for i in data.get("jobs") or []:
            if i.get("id") in seen:
                continue
            seen.add(i.get("id"))
            out.append(job("Jobicy", i.get("jobTitle"), i.get("companyName"), i.get("url"),
                           location=i.get("jobGeo") or "", remote=True,
                           description=i.get("jobDescription") or i.get("jobExcerpt"),
                           posted=i.get("pubDate"), job_id=i.get("id"),
                           salary=salary_range(i.get("annualSalaryMin") or i.get("salaryMin"),
                                               i.get("annualSalaryMax") or i.get("salaryMax"),
                                               i.get("salaryCurrency"), "year")))
        time.sleep(1)
    return _keep(out)


def remote_ok(settings):
    data = _get("https://remoteok.com/api")
    return _keep(job("Remote OK", i.get("position"), i.get("company"), i.get("url"),
                     location=i.get("location") or "", remote=True,
                     description=i.get("description"), posted=i.get("date"), job_id=i.get("id"),
                     salary=salary_range(i.get("salary_min"), i.get("salary_max"), "USD", "year"))
                 for i in data if isinstance(i, dict) and i.get("position"))


def we_work_remotely(settings):
    out, seen = [], set()
    feeds = ["https://weworkremotely.com/remote-jobs.rss",
             "https://weworkremotely.com/categories/remote-customer-support-jobs.rss",
             "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss",
             "https://weworkremotely.com/categories/remote-sales-and-marketing-jobs.rss",
             "https://weworkremotely.com/categories/all-other-remote-jobs.rss"]
    for feed in feeds:
        try:
            root = ET.fromstring(_get(feed, kind="text"))
        except (requests.RequestException, ET.ParseError):
            continue
        for item in root.findall("./channel/item"):
            full = item.findtext("title") or ""
            link = item.findtext("link") or ""
            if ":" not in full or link in seen:
                continue
            seen.add(link)
            company, title = full.split(":", 1)
            out.append(job("We Work Remotely", title, company, link,
                           location=item.findtext("region") or "", remote=True,
                           description=item.findtext("description"),
                           posted=item.findtext("pubDate"), job_id=item.findtext("guid")))
    return _keep(out)


def remotejobs_org(settings):
    data = _get("https://remotejobs.org/api/v1/jobs")
    out = []
    for i in data.get("data") or []:
        company = i.get("company")
        company = company.get("name") if isinstance(company, dict) else company
        place = i.get("location")
        if isinstance(place, dict):
            place = place.get("name") or place.get("display_name") or ""
        out.append(job("RemoteJobs.org", i.get("title"), company, i.get("url") or i.get("job_url"),
                       location=place or "", remote=True, description=i.get("description"),
                       posted=i.get("posted_at"), job_id=i.get("id")))
    return _keep(out)


# ---------------------------------------------------------------- Indeed Greece
def indeed(settings):
    """Indeed has no free feed. The open-source JobSpy library reads the same search
    the Indeed phone app uses. It can stop working without notice; the run goes on."""
    from jobspy import scrape_jobs  # installed from requirements.txt

    def text(value):
        return "" if value is None or value != value else str(value)  # value != value: empty cell (NaN)

    seen, out = set(), []
    for keyword in settings["indeed_keywords"]:
        try:
            table = scrape_jobs(site_name=["indeed"], search_term=keyword, location=settings["indeed_location"],
                                country_indeed="Greece", results_wanted=int(settings["indeed_results_per_search"]),
                                hours_old=int(settings["indeed_hours_old"]), verbose=0)
        except Exception:  # noqa: BLE001
            continue
        for _, row in table.iterrows():
            if text(row.get("id")) in seen:
                continue
            seen.add(text(row.get("id")))
            remote = bool(row.get("is_remote")) if text(row.get("is_remote")) else False
            out.append(job("Indeed", text(row.get("title")), text(row.get("company")), text(row.get("job_url")),
                           location=text(row.get("location")), remote=remote,
                           restrictions=["Greece"] if remote else [],
                           description=text(row.get("description")), posted=text(row.get("date_posted")),
                           job_id=text(row.get("id")),
                           salary=salary_range(text(row.get("min_amount")), text(row.get("max_amount")),
                                               text(row.get("currency")),
                                               {"monthly": "month", "yearly": "year", "hourly": "hour"}
                                               .get(text(row.get("interval")), text(row.get("interval")))),
                           arrangement="Remote" if remote else ""))
        time.sleep(1)
    return _keep(out)


# ---------------------------------------------------------------- Jobfind.gr
def jobfind(settings):
    """Jobfind's own published RSS feed: the 100 newest ads in Greece, all professions.
    The feed gives no company name, so each ad is listed as "Jobfind ad" with its number."""
    response = requests.get("https://www.jobfind.gr/rss/rssjobfind_recentads.ashx", headers=UA, timeout=TIMEOUT)
    response.raise_for_status()
    root = ET.fromstring(response.content.decode("utf-8-sig").encode("utf-8"))
    out = []
    for item in root.findall("./channel/item"):
        title, link = clean(item.findtext("title")), (item.findtext("link") or "").strip()
        region = clean(item.findtext("region"))
        parts = [p.strip() for p in title.split(" - ")]
        places = []
        while len(parts) > 1 and (parts[-1] == region or parts[-1].isupper()) and len(places) < 2:
            places.insert(0, parts.pop())
        if region and region not in places:
            places.append(region)
        out.append(job("Jobfind", " - ".join(parts), f"Jobfind ad {link.rsplit('/', 1)[-1][:8]}", link,
                       location=", ".join(places + ["Greece"]), remote=False,
                       description=item.findtext("description"), posted=item.findtext("pubDate"),
                       job_id=link))
    return _keep(out)


SOURCES = [
    ("Indeed", indeed), ("Jobfind", jobfind),
    ("Workable", workable), ("Himalayas", himalayas), ("Jobicy", jobicy),
    ("Remotive", remotive), ("Arbeitnow", arbeitnow), ("Remote OK", remote_ok),
    ("We Work Remotely", we_work_remotely), ("RemoteJobs.org", remotejobs_org),
]


def collect(settings, only=None):
    """Run every source. Returns (jobs, counts, errors)."""
    jobs, counts, errors = [], {}, {}
    for name, reader in SOURCES:
        if only and name not in only:
            continue
        try:
            found = reader(settings)
            counts[name] = len(found)
            jobs.extend(found)
        except Exception as exc:  # one broken feed must never stop the run
            counts[name] = 0
            errors[name] = f"{type(exc).__name__}: {exc}"[:200]
    return jobs, counts, errors
