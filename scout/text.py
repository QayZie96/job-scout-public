"""Text folding shared by the filters and the rating."""
import re
import unicodedata


def fold(text):
    """Lower case without accents, so "ΗΛΕΚΤΡΟΝΙΚΟΥ ΚΑΤΑΣΤΗΜΑΤΟΣ" and
    "ηλεκτρονικού καταστήματος" compare equal. Spaces are kept as they are."""
    text = unicodedata.normalize("NFD", str(text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.replace("ς", "σ")


_GENDER = re.compile(r"\(\s*(?:[mfwdxh]\s*/\s*){1,3}[mfwdxh]\s*\)|\(\s*all genders\s*\)|[-–]?\s*all genders\b", re.I)
_TAIL = re.compile(r"\s*(?:[-–|@,]|\(|#)\s*([^-–|@,(#]*?)\)?\s*$")
_PLACE_WORDS = re.compile(r"\b(?:remote|hybrid|on-?site|office|home office|europe|emea|eu|worldwide|global|"
                          r"permanent|full[- ]time|part[- ]time|nordics|dach|benelux)\b", re.I)


def _is_place(text):
    from .screen import ATHENS, EU_CITIES, EU_COUNTRIES, GREECE  # here, to avoid a circular import
    folded = f" {fold(text)} "
    return bool(_PLACE_WORDS.search(text)) or text.lstrip().startswith("#") or any(
        re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", folded) for w in ATHENS + GREECE + EU_CITIES + EU_COUNTRIES)


def base_title(title):
    """The title without gender tags and trailing place parts (" - Germany remote", " | Athens",
    " #JD Glyfada", "(Remote EU)"), so the same job posted for several places is listed once.
    Other trailing parts (" - Retail", " - Hospitality") are kept: those are different jobs."""
    text = re.sub(r"\s+", " ", _GENDER.sub(" ", str(title or ""))).strip()
    for _ in range(3):
        match = _TAIL.search(text)
        if not match or len(text[:match.start()].strip()) < 6 or not _is_place(match.group(0)):
            break
        text = text[:match.start()].strip()
    return text
