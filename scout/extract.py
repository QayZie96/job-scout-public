"""Small text helpers: posted salary and work arrangement, read from the ad."""
import re

from .text import fold

_CUR = r"(?:€|\$|£|eur|euro|euros|usd|gbp|chf|dkk|sek|nok|pln|ευρώ)"
_NUM = r"\d{1,3}(?:[.,\s]\d{3})+|\d+(?:[.,]\d+)?\s?k|\d{3,6}"
_PER = (r"(?:\s*(?:gross|net|brutto|netto|μικτά|καθαρά))?(?:\s*(?:per|a|/|ανά|το)\s*"
        r"(?:year|yr|annum|month|mo|hour|hr|h|έτος|μήνα|ώρα)|\s*(?:p\.?a\.?|annually|monthly|yearly|hourly))?"
        r"(?:\s*(?:gross|net|μικτά|καθαρά))?")
_SALARY = re.compile(
    rf"(?:{_CUR}\s?(?:{_NUM})(?:\s?(?:-|–|—|to|έως)\s?{_CUR}?\s?(?:{_NUM}))?(?:\s?{_CUR})?{_PER}"
    rf"|(?:{_NUM})(?:\s?(?:-|–|—|to|έως)\s?(?:{_NUM}))?\s?{_CUR}{_PER})", re.I)
_CONTEXT = re.compile(r"salary|compensation|annum|pay\b|paid|gross|net\b|per (?:year|month|hour)|annual|monthly|"
                      r"hourly|/\s?(?:year|yr|month|mo|hour|hr|h)\b|p\.a\.|ote|base|μισθ|αποδοχ|μικτά|καθαρά", re.I)
_NOT_PAY = re.compile(r"revenue|funding|raised|valuation|turnover|budget|customers|users|arr\b|gmv|sales of|"
                      r"million|billion|\bm\b|\bbn\b|bonus of|voucher|allowance|stipend|equipment", re.I)


def find_salary(text):
    """First amount in the ad that reads like pay. Empty when none is stated."""
    text = str(text or "")
    for match in _SALARY.finditer(text):
        around = text[max(0, match.start() - 70):match.end() + 40]
        digits = re.sub(r"\D", "", match.group(0))
        if not digits or int(digits[:7]) < 5:
            continue
        if _CONTEXT.search(around) and not _NOT_PAY.search(around):
            return re.sub(r"\s+", " ", match.group(0)).strip(" .,;")[:60]
    return ""


def salary_range(low, high, currency="", period=""):
    """'EUR 30,000 - 40,000 / year' from numbers given by a feed."""
    def num(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None
    low, high = num(low), num(high)
    if not low and not high:
        return ""
    parts = [f"{int(v):,}" for v in (low, high) if v]
    text = " - ".join(dict.fromkeys(parts))
    return " ".join(x for x in (str(currency or "").upper(), text, f"/ {period}" if period else "") if x)


def arrangement(job):
    """Remote, Hybrid or On-site. Empty when the ad does not say."""
    if job.get("arrangement"):
        return job["arrangement"]
    head = f"{job.get('title', '')} {job.get('location', '')}".lower()
    text = (job.get("description") or "")[:6000].lower()
    if re.search(r"\bhybrid\b|υβριδικ", head):
        return "Hybrid"
    if job.get("remote"):
        return "Remote"
    if re.search(r"\bhybrid\b|υβριδικ|days? (?:per week |a week )?(?:in|at|from) (?:the |our )?office|"
                 r"days? (?:per week |a week )?(?:from|at) home|work from home \d", text):
        return "Hybrid"
    if re.search(r"\b(?:fully|100%|full)[- ]remote\b|\bremote[- ]first\b|πλήρως απομακρυσμέν", text):
        return "Remote"
    if job.get("remote") is False or re.search(r"\bon[- ]?site\b|\bin[- ]office\b|δια ζώσης|φυσική παρουσία", text):
        return "On-site"
    return ""


# ---------------------------------------------------------------- country
COUNTRIES = {  # country shown in the sheet -> words that give it away in a location text
    "Greece": ("greece", "hellas", "ελλάδα", "ελλαδα", "αθήνα", "αθηνα", "athens", "attica", "attiki",
               "thessaloniki", "θεσσαλονίκη", "piraeus", "πειραι", "patras", "heraklion", "ηράκλειο",
               "larissa", "ioannina", "volos", "crete", "marousi", "maroussi", "chalandri", "kifisia",
               "kifissia", "glyfada", "kallithea", "peristeri", "metamorfosi", "gerakas", "μοσχάτο",
               "γέρακας", "μαρούσι", "χαλάνδρι", "καλλιθέα", "γλυφάδα", "κηφισιά", "περιστέρι"),
    "Cyprus": ("cyprus", "nicosia", "limassol", "larnaca", "paphos"),
    "Germany": ("germany", "deutschland", "berlin", "munich", "münchen", "hamburg", "frankfurt", "cologne",
                "köln", "düsseldorf", "dusseldorf", "stuttgart", "leipzig", "mannheim", "nuremberg"),
    "Netherlands": ("netherlands", "nederland", "amsterdam", "rotterdam", "utrecht", "eindhoven", "the hague"),
    "Switzerland": ("switzerland", "schweiz", "zurich", "zürich", "geneva", "basel", "bern", "lausanne", "zug"),
    "Spain": ("spain", "españa", "madrid", "barcelona", "valencia", "malaga", "málaga", "seville"),
    "Portugal": ("portugal", "lisbon", "lisboa", "porto"),
    "France": ("france", "paris", "lyon", "marseille", "bordeaux", "lille", "nantes", "toulouse"),
    "Ireland": ("ireland", "dublin", "cork", "galway", "limerick"),
    "Italy": ("italy", "italia", "milan", "milano", "rome", "roma", "turin", "bologna", "florence"),
    "Austria": ("austria", "österreich", "vienna", "wien", "graz", "linz", "salzburg"),
    "Belgium": ("belgium", "brussels", "antwerp", "ghent", "leuven"),
    "Denmark": ("denmark", "copenhagen", "aarhus"),
    "Sweden": ("sweden", "stockholm", "gothenburg", "malmö", "malmo"),
    "Finland": ("finland", "helsinki", "espoo", "tampere"),
    "Norway": ("norway", "oslo", "bergen"),
    "Poland": ("poland", "warsaw", "krakow", "kraków", "wroclaw", "wrocław", "gdansk", "poznan"),
    "Czechia": ("czech", "prague", "brno"),
    "Hungary": ("hungary", "budapest"),
    "Romania": ("romania", "bucharest", "cluj", "iasi", "timisoara"),
    "Bulgaria": ("bulgaria", "sofia", "plovdiv", "varna"),
    "Estonia": ("estonia", "tallinn", "tartu"),
    "Latvia": ("latvia", "riga"),
    "Lithuania": ("lithuania", "vilnius", "kaunas"),
    "Luxembourg": ("luxembourg",),
    "Malta": ("malta", "valletta", "sliema"),
    "Croatia": ("croatia", "zagreb", "split"),
    "Slovenia": ("slovenia", "ljubljana"),
    "Slovakia": ("slovakia", "bratislava"),
    "Iceland": ("iceland", "reykjavik"),
    "United Kingdom": ("united kingdom", "england", "scotland", "london", "manchester", "edinburgh"),
    "United States": ("united states", "usa", "new york", "san francisco"),
}
REGIONS = (("Europe", ("europe", "emea", "european union", "eea")),
           ("Worldwide", ("worldwide", "anywhere", "global")))


def country(location):
    """'Greece', 'Germany, Spain' (up to three), 'Europe', 'Worldwide' or ''."""
    text = f" {fold(location)} "
    found = [name for name, words in COUNTRIES.items()
             if any(re.search(rf"(?<![a-zα-ωά-ώ]){re.escape(fold(w))}(?![a-zα-ωά-ώ])", text) for w in words)]
    if found:
        return ", ".join(found[:3]) + (" +" if len(found) > 3 else "")
    for name, words in REGIONS:
        if any(w in text for w in words):
            return name
    return ""
