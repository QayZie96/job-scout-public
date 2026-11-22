"""Step 1: the only filters. A job is removed only for a hard reason.

`screen(job, settings)` returns (bucket, reason). If `reason` is not empty the
job goes to the Filtered out tab; otherwise `bucket` says where the job is.
"""
import re
from datetime import date

from .settings import families
from .text import fold

ATHENS = ("athens", "attica", "attiki", "piraeus", "marousi", "maroussi", "chalandri",
          "halandri", "kifisia", "kifissia", "glyfada", "kallithea", "peristeri", "ilion",
          "metamorfosi", "nea ionia", "koropi", "aspropyrgos", "αθήνα", "αττική", "πειραι",
          "athina", "nea smyrni", "alimos", "agios dimitrios", "elliniko", "lykovrysi", "tavros",
          "moschato", "vrilissia", "agia paraskevi", "pallini", "paiania", "peania", "spata",
          "acharnes", "kryoneri", "agios stefanos", "galatsi", "zografou", "cholargos",
          "psychiko", "argyroupoli", "voula", "egaleo", "aigaleo", "nikaia", "renti", "mandra",
          "elefsina", "magoula", "gerakas", "pefki", "nea erythraia", "chaidari", "ilioupoli",
          "kantza", "penteli", "ampelokipoi", "nea filadelfeia", "markopoulo", "irakleio attik",
          "neo irakleio", "drapetsona", "keratsini", "vouliagmeni", "melissia", "nea chalkidona",
          "vari", "varkiza", "dafni", "petroupoli", "neo psychiko", "filothei", "holargos",
          # Greek spelling (Indeed and Jobfind write places in Greek)
          "κορωπί", "ταύρος", "νέα χαλκηδόνα", "μαρούσι", "αμαρούσιο", "χαλάνδρι", "κηφισιά", "γλυφάδα",
          "περιστέρι", "ίλιον", "μεταμόρφωση", "νέα ιωνία", "ασπρόπυργος", "ελληνικό", "άλιμος",
          "μοσχάτο", "καλλιθέα", "αιγάλεω", "νίκαια", "ρέντη", "παλλήνη", "παιανία", "σπάτα",
          "αχαρνές", "μενίδι", "άγιος στέφανος", "γαλάτσι", "ζωγράφου", "χολαργός", "ψυχικό",
          "αργυρούπολη", "βούλα", "βουλιαγμένη", "μάνδρα", "ελευσίνα", "μαγούλα", "γέρακας",
          "πεύκη", "νέα ερυθραία", "χαϊδάρι", "ηλιούπολη", "κάντζα", "πεντέλη", "αμπελόκηποι",
          "νέα φιλαδέλφεια", "μαρκόπουλο", "νέο ηράκλειο", "δραπετσώνα", "κερατσίνι", "μελίσσια",
          "βριλήσσια", "αγία παρασκευή", "νέα σμύρνη", "άγιος δημήτριος", "λυκόβρυση", "κρυονέρι",
          "βάρη", "βύρωνας", "δάφνη", "πετρούπολη", "μεγάρα", "λαύριο")
GREECE = ("greece", "hellas", "ελλάδα", "thessaloniki", "patras", "heraklion", "larissa",
          "ioannina", "volos", "crete")
# EU + EEA + Switzerland (Greek citizens can work there without a visa)
EU_COUNTRIES = (
    "austria", "belgium", "bulgaria", "croatia", "cyprus", "czech", "czechia", "denmark",
    "estonia", "finland", "france", "germany", "deutschland", "hungary", "ireland", "italy",
    "latvia", "lithuania", "luxembourg", "malta", "netherlands", "poland", "portugal",
    "romania", "slovakia", "slovenia", "spain", "sweden", "norway", "iceland",
    "liechtenstein", "switzerland",
)
EU_CITIES = (
    "berlin", "munich", "münchen", "hamburg", "frankfurt", "cologne", "köln", "düsseldorf",
    "stuttgart", "leipzig", "amsterdam", "rotterdam", "utrecht", "eindhoven", "the hague",
    "paris", "lyon", "madrid", "barcelona", "valencia", "malaga", "lisbon", "porto",
    "dublin", "cork", "vienna", "wien", "zurich", "zürich", "geneva", "basel", "bern",
    "lausanne", "zug", "brussels", "antwerp", "copenhagen", "stockholm", "gothenburg",
    "helsinki", "oslo", "warsaw", "krakow", "kraków", "wroclaw", "gdansk", "prague", "brno",
    "budapest", "bucharest", "cluj", "sofia", "tallinn", "riga", "vilnius", "milan", "rome",
    "turin", "luxembourg", "valletta", "nicosia", "limassol", "ljubljana", "zagreb",
    "bratislava",
)
EU_WIDE = ("europe", "european union", " eu", "eu ", "emea", "eea", "worldwide", "anywhere",
           "global", "international", "any country", "all countries", "cet", "utc+")
NON_EU = (
    "usa", "united states", "u.s.", "us only", "us-only", "north america", "canada",
    "latam", "latin america", "south america", "brazil", "mexico", "argentina", "colombia",
    "india", "philippines", "apac", "asia", "australia", "new zealand", "africa", "nigeria",
    "kenya", "south africa", "uk only", "united kingdom", "uk", "england", "london",
    "japan", "china", "singapore", "israel", "turkey", "ukraine", "uae", "dubai",
    "saudi", "pakistan", "us", "manchester", "edinburgh", "glasgow", "leeds", "birmingham",
    "bristol", "newcastle", "cambridge", "oxford", "casablanca", "morocco", "beirut",
    "lebanon", "new york", "san francisco", "toronto", "serbia", "belgrade", "albania", "indonesia", "vietnam", "korea", "americas", "egypt",
)


ATHENS, GREECE, EU_COUNTRIES, EU_CITIES, EU_WIDE, NON_EU = (
    tuple(fold(w) for w in words) for words in (ATHENS, GREECE, EU_COUNTRIES, EU_CITIES, EU_WIDE, NON_EU))


def _has(text, words):
    return any(w in text for w in words)


def _word(text, words):
    return any(re.search(rf"(?<![a-z]){re.escape(w.strip())}(?![a-z])", text) for w in words)


def location_bucket(job):
    """Returns (bucket, reason). Buckets: Athens, Greece (other), Remote GR,
    Remote EU, Remote (unclear), Relocation."""
    place = f" {job.get('location', '')} {' '.join(job.get('restrictions') or [])} "
    place = fold(place)
    in_greece = _has(place, GREECE) or _has(place, ATHENS) or re.search(r"\bgr[ih]?\b", place)
    # Indeed writes the region code: GRI = Attica
    in_attica = _has(place, ATHENS) or re.search(r"\bgri\b", place)
    if job.get("remote"):
        if in_greece:
            return "Remote GR", ""
        if _has(place, EU_WIDE) or _word(place, EU_COUNTRIES) or _word(place, EU_CITIES):
            return "Remote EU", ""
        if _word(place, NON_EU):
            return "", f"Remote, but limited to: {job.get('location') or 'outside EU'}"
        return "Remote (unclear)", ""
    if in_attica:
        return "Athens", ""
    if in_greece:
        return "Greece (other)", ""
    if _word(place, EU_COUNTRIES) or _word(place, EU_CITIES):
        return "Relocation", ""
    if not place.strip():
        return "Location unclear", ""
    return "", f"On-site outside Greece/EU/CH: {job.get('location')}"


# ---- deal-breakers (ported from Job-Funnel v2 Screen.gs, plus Greek ads) ----
_DEG = r"(?:bachelor'?s?|bsc|b\.sc\.?|ba|master'?s?|msc|m\.sc\.?|mba|university|college|academic|undergraduate)"
_DEGREE_PATTERNS = [
    rf"\b(?:a\s+)?(?:completed\s+)?{_DEG}(?:'s)?\s+(?:degree|diploma)\s+(?:in\s+[^.;\n]{{0,60}}\s+)?(?:is\s+)?(?:strictly\s+)?(?:required|mandatory|essential|a must|necessary)\b",
    rf"\b(?:must|required to|need to)\s+(?:have|hold|possess)\s+(?:a|an)?\s*(?:completed\s+)?{_DEG}(?:'s)?\s+(?:degree|diploma)\b",
    rf"\b(?:required|requirements?|must[- ]haves?|qualifications)\s*:?\s*(?:[-•*]\s*)?{_DEG}(?:'s)?\s+degree\b",
    r"απαραίτητ[οαη]ς?\s+(?:προσόν\s+)?(?:το\s+)?πτυχίο",
    r"πτυχίο\s+(?:αει|τει|α\.ε\.ι|τ\.ε\.ι|ανώτατης|ανώτερης|πανεπιστημ)[^.;\n]{0,80}(?:απαραίτητ|απαιτείται|προαπαιτούμεν)",
    r"(?:απαιτείται|προαπαιτούμενο)[^.;\n]{0,40}πτυχίο",
]
# "or equivalent experience" softens a degree; "or a related field" / "or equivalent degree" does not
_NOT_SOFT = r"(?!\s+(?:fields?|disciplines?|subjects?|areas?|degrees?|qualifications?|studies|majors?|diplomas?)\b)"
_DEGREE_SOFT = (rf"\bor\s+(?:an?\s+)?(?:equivalent|comparable|relevant|related)\b{_NOT_SOFT}|\bin lieu of\b|"
                r"\bequivalent\s+(?:practical\s+|work\s+|professional\s+)?experience\b|"
                r"\b(?:preferred|a plus|nice to have|desirable|advantage|bonus|ideally|is a plus|"
                r"not required|not necessary|optional|will be considered|appreciated|"
                r"an asset|as an asset|considered an? (?:asset|advantage|plus))\b|"
                r"\bor\s+(?:[a-z-]+\s+){0,3}experience\b|"
                r"επιθυμητ|θα εκτιμηθεί|θα θεωρηθεί|ή αντίστοιχη|ή ανάλογη|ή σχετική|"
                # optional, or a school-leaving certificate (not a degree)
                r"προαιρετικ|δευτεροβάθμιας|λυκείου|απολυτήριο")

_LANGS = ("german|french|spanish|italian|dutch|portuguese|polish|arabic|mandarin|chinese|"
          "japanese|korean|russian|turkish|swedish|norwegian|danish|finnish|czech|romanian|"
          "hungarian|hebrew|ukrainian|bulgarian")
_LANG_PATTERNS = [
    rf"\b(?:fluent|fluency|native(?:[- ]level)?|business[- ]level|professional(?:\s+working)?|proficient|c1|c2)\s+(?:fluency\s+|proficiency\s+|level\s+)?(?:in\s+)?({_LANGS})\b",
    rf"\b({_LANGS})\s+(?:language\s+)?(?:fluency|proficiency|skills?)?\s*(?:is\s+|are\s+)?(?:required|mandatory|essential|a must)\b",
    rf"\b(?:must|need to|required to)\s+(?:speak|write|communicate in)\s+({_LANGS})\b",
    rf"\b({_LANGS})[- ]speaking\b",
    rf"\b(?:native|fluent)\s+({_LANGS})\b",
]
_LANG_SOFT = r"\b(?:preferred|optional|a plus|nice to have|bonus|not required|desirable|advantage|is a plus|beneficial)\b"

_HARD = [
    ("Commission-only sales", [r"\bcommission[- ]only\b", r"\b(?:100%|purely|solely)\s+commission\b",
                               r"\bno\s+base\s+salary\b"]),
    ("Cold-calling sales", [r"\bcold[- ]call(?:ing|s)?\b(?!\s+(?:is\s+)?not)", r"\btelemarketing\b",
                            r"\bdoor[- ]to[- ]door\b", r"τηλεφωνικ(?:ές|ών)\s+πωλήσε"]),
    ("Phone-heavy support", [r"\bhigh[- ]volume\s+(?:of\s+)?(?:inbound\s+|outbound\s+|customer\s+)?calls?\b",
                             r"\b(?:handle|handling|answer|answering|take|taking)\s+(?:incoming\s+|inbound\s+)(?:phone\s+)?calls\b",
                             r"\bphone[- ](?:heavy|based)\b"]),
    ("Translation-only work", [r"\btranslat(?:e|ing|ion)\s+[^.\n]{0,60}\s+(?:is|as)\s+(?:the\s+)?(?:core|main|primary)\b"]),
    ("US residence or work permit required", [
        r"\b(?:must|need to)\s+(?:be\s+)?(?:located|based|reside|live)\s+in\s+(?:the\s+)?(?:united states|u\.?s\.?a?\.?|canada)\b",
        r"\b(?:us|u\.s\.)\s+(?:citizens?|residents?|work authorization)\b",
        r"\bauthorized to work in the (?:united states|u\.?s\.?)\b"]),
]

_STOPWORDS = {
    "German": (" und ", " der ", " die ", " das ", " mit ", " für ", " wir ", " du ", " ist ",
               " nicht ", " eine ", " deine ", " unser ", " bei ", " zum ", " auf "),
    "French": (" et ", " les ", " des ", " une ", " vous ", " nous ", " pour ", " dans ", " est ",
               " avec ", " sur ", " votre ", " notre ", " aux ", " qui ", " du "),
    "Dutch": (" en ", " het ", " een ", " van ", " voor ", " je ", " met ", " wij ", " onze ",
              " bij ", " zijn ", " naar ", " ook ", " niet ", " jouw ", " aan "),
    "Spanish": (" y ", " los ", " las ", " una ", " para ", " con ", " por ", " del ", " que ",
                " nuestro ", " tu ", " en el ", " se ", " como ", " más ", " es "),
    "Italian": (" e ", " il ", " di ", " per ", " con ", " una ", " che ", " del ", " della ",
                " nostro ", " sono ", " gli ", " nel ", " alla ", " più ", " le "),
}


_DEGREE_BULLET = (r"(?:^|\n)[\s\-•*·–]*((?:a\s+|an\s+)?(?:bachelor|bsc|b\.sc|ba/bsc|bs/ba|ba or bs|master|msc|"
                  r"university degree|college degree|academic degree|degree in|degree from|"
                  r"πτυχίο|κάτοχος πτυχίου|απόφοιτος αει|απόφοιτος/η αει|απόφοιτοι αει)[^\n]{0,140})")


def degree_required(text):
    # a degree listed as its own requirement line, with nothing softening it
    for match in re.finditer(_DEGREE_BULLET, text, flags=re.I):
        before = text[max(0, match.start() - 250): match.start()]
        optional_section = re.search(
            r"(?:nice[- ]to[- ]have|preferred|bonus|a plus|desirable|good to have|"
            r"επιθυμητ|θα εκτιμηθ)[^\n]{0,40}\n(?:[^\n]*\n){0,3}[^\n]*$", before, flags=re.I)
        if not optional_section and not re.search(_DEGREE_SOFT, match.group(1), flags=re.I):
            return match.group(1).strip()[:80]
    for pattern in _DEGREE_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.I):
            nearby = text[max(0, match.start() - 120): match.end() + 200]
            if not re.search(_DEGREE_SOFT, nearby, flags=re.I):
                return match.group(0)[:80]
    return ""


def language_required(text, title=""):
    combined = f"{title}\n{text}"
    for pattern in _LANG_PATTERNS:
        for match in re.finditer(pattern, combined, flags=re.I):
            tail = combined[match.end(): match.end() + 70].split(".")[0]
            if re.search(_LANG_SOFT, tail, flags=re.I):
                continue
            return match.group(1).title()
    return ""


def foreign_language_ad(text):
    """Name of the language if the ad is clearly not written in English or Greek."""
    sample = f" {text[:3000].lower()} "
    english = sum(sample.count(w) for w in (" the ", " and ", " you ", " with ", " for ", " our "))
    for language, words in _STOPWORDS.items():
        hits = sum(sample.count(w) for w in words)
        if hits >= 14 and hits > english * 1.5:
            return language
    return ""


def language_in_title(title):
    match = re.search(rf"(?<![a-z])({_LANGS})(?![a-z])", title, flags=re.I)
    return match.group(1).title() if match else ""


# off-field words that are only the start of an unrelated word: "intern" in "International"
FALSE_FRIENDS = {
    "intern": ("internal", "international", "internet", "internacional", "internationa"),
    "doctor": ("doctoral", "doctorate"),
    "cook": ("cookie",),
    "counsel": ("counselor", "counsellor"),
}


def _false_friend(word, padded, start):
    return any(padded.startswith(f, start) for f in FALSE_FRIENDS.get(word, ()))


def offfield(title, settings):
    padded = f" {fold(title)} "
    # a wanted phrase in the title protects the words inside it:
    # "ηλεκτρονικού καταστήματος" (e-shop) must not be removed for "καταστήματος" (store staff)
    wanted = [fold(w).strip() for key, _ in families(settings) if key != "family_generalist"
              for w in settings.get(key, [])]
    wanted = [w for w in wanted if w in padded]
    for word in settings["offfield_titles"]:
        word = fold(word)
        if any(word.strip() in w and w != word.strip() for w in wanted):
            continue
        if word.endswith(" ") or word.startswith(" "):
            if f" {word.strip()} " in padded or re.search(rf"(?<![a-z]){re.escape(word.strip())}(?![a-z])", padded):
                return word.strip()
        else:
            for match in re.finditer(rf"(?<![a-zα-ω]){re.escape(word)}", padded):
                if not _false_friend(word, padded, match.start()):
                    return word
    return ""


def rescued(title, settings):
    """A rescue word in the title ("automation", "operations", "customer"...) that keeps
    an off-field title such as "Automation Engineer" or "Driver Operations Associate"
    in the list, with a penalty, so the AI can judge it."""
    padded = f" {fold(title)} "
    for word in settings.get("offfield_rescue_words") or []:
        w = fold(word).strip()
        if w and re.search(rf"(?<![a-z0-9α-ω]){re.escape(w)}", padded):
            return word.strip()
    return ""


_OPEN_CALL = re.compile(r"\btalent\s+(?:pool|community|network)\b|\b(?:open|spontaneous|general|speculative|"
                        r"unsolicited)\s+application\b|^join\s+(?:us|our\s+team|[\w.&-]+)\s*!?$|"
                        r"\bfuture\s+opportunit|αυθόρμητη\s+αίτηση", re.I)


def matches_family(title, settings):
    padded = f" {fold(title)} "
    for key, _ in families(settings):
        for word in settings.get(key, []):
            w = fold(word)
            if w != w.strip():
                if re.search(rf"(?<![a-z0-9]){re.escape(w.strip())}(?![a-z0-9])", padded):
                    return True
            elif w in padded:
                return True
    return False


def _ok_language(name, settings):
    return name and name.lower() in {str(x).strip().lower() for x in settings.get("ok_languages") or []}


def _yes(value):
    return str(value).strip().lower() in ("yes", "true", "1", "on")


def screen(job, settings):
    """Returns (bucket, reason). Empty reason = the job passes."""
    bucket, reason = location_bucket(job)
    if reason:
        return bucket, reason
    if bucket in (settings.get("removed_types") or []):
        return bucket, f"Not a wanted place ({bucket}): {job.get('location') or '?'}"
    if _OPEN_CALL.search(job["title"]):
        return bucket, "General application, not a specific job"
    flags = job.setdefault("flags", [])
    hit = offfield(job["title"], settings)
    if hit:
        rescuable = {fold(w).strip() for w in settings.get("offfield_rescuable") or []}
        others = dict(settings, offfield_titles=[w for w in settings["offfield_titles"]
                                                 if fold(w).strip() not in rescuable])
        # rescued only when every off-field word in the title may be rescued
        saved = rescued(job["title"], settings) if hit in rescuable and not offfield(job["title"], others) else ""
        if not saved:
            return bucket, f"Another field (title has '{hit}')"
        flags.append(("offfield", f"maybe another field: '{hit}', kept for '{saved}'"))
    max_age = int(settings.get("max_ad_age_days") or 0)
    if max_age and job.get("posted") and not str(job.get("source", "")).startswith("Company list"):
        try:
            age = (date.today() - date.fromisoformat(job["posted"][:10])).days
        except ValueError:
            age = 0
        if age > max_age:
            return bucket, f"Old ad: posted {age} days ago (job boards are not re-checked)"
    if _yes(settings.get("title_must_match_family", "no")) and not matches_family(job["title"], settings):
        return bucket, "Title is not one of the wanted job kinds"
    text = job.get("description") or ""
    hit = foreign_language_ad(text)
    if hit and not _ok_language(hit, settings):
        return bucket, f"Ad written in {hit}"
    hit = language_in_title(job["title"])
    if hit and not _ok_language(hit, settings):
        return bucket, f"{hit} language required"
    mode = str(settings.get("remove_degree_required", "yes")).strip().lower()
    hit = degree_required(text) if (_yes(mode) or mode == "flag") else ""
    if hit and mode == "flag":
        flags.append(("degree", f"degree asked: “{hit[:50]}”"))
    elif hit:
        return bucket, f"Degree required: “{hit}”"
    hit = language_required(text, job["title"])
    if hit and not _ok_language(hit, settings):
        return bucket, f"{hit} language required"
    for label, patterns in _HARD:
        if any(re.search(p, f"{job['title']}\n{text}", flags=re.I) for p in patterns):
            return bucket, label
    return bucket, ""
