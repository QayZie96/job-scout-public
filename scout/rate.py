"""Step 2: rate every job that passed, 0 to 100. The rating only sorts."""
import re
from datetime import date

from .settings import families
from .text import fold

LOCATION_POINTS = {
    "Athens": "points_athens", "Remote GR": "points_remote_greece",
    "Remote EU": "points_remote_eu", "Relocation": "points_relocation",
    "Greece (other)": "points_greece_other", "Remote (unclear)": "points_remote_unclear",
}


def _match(text, words):
    padded = f" {fold(text)} "
    for word in words:
        w = fold(word)
        if w != w.strip():  # words written with spaces must match as whole words
            if re.search(rf"(?<![a-z0-9]){re.escape(w.strip())}(?![a-z0-9])", padded):
                return word.strip()
        elif re.search(rf"(?<![a-z0-9α-ω]){re.escape(w)}", padded):  # word start: "llm" not in "bellman"
            return word
    return ""


def _desc_hits(text, words, need):
    """Distinct family words found in the description, if there are enough."""
    padded = f" {fold(text)} "
    found = []
    for word in words:
        w = fold(word)
        if w != w.strip():
            ok = re.search(rf"(?<![a-z0-9]){re.escape(w.strip())}(?![a-z0-9])", padded)
        else:
            ok = re.search(rf"(?<![a-z0-9α-ω]){re.escape(w)}", padded)
        if ok:
            found.append(word.strip())
    return found if len(found) >= need else []


def rate(job, bucket, settings, today=None):
    """Returns (score, label, why)."""
    today = today or date.today()
    score, label, why = 0, "Unsorted", []
    title, description = job["title"], job.get("description") or ""
    all_families = families(settings)
    specific = [f for f in all_families if f[0] != "family_generalist"]

    for key, name in all_families:
        hit = _match(title, settings[key])
        if hit:
            points = settings["points_generalist_title" if key == "family_generalist"
                              else "points_family_title"]
            score, label = score + points, name
            why.append(f"title: {hit} (+{points})")
            break
    else:
        for key, name in specific:
            hits = _desc_hits(description[:8000], settings[key], settings["description_min_hits"])
            if hits:
                points = settings["points_family_description"]
                score, label = score + points, f"{name} (in description)"
                why.append(f"description: {', '.join(hits[:3])} (+{points})")
                break
    # a generalist title with an e-commerce/AI/ops description gets both
    if label == "Generalist":
        for key, name in specific:
            hits = _desc_hits(description[:8000], settings[key], settings["description_min_hits"])
            if hits:
                points = settings["points_family_description"]
                score += points
                label = f"Generalist + {name}"
                why.append(f"description: {', '.join(hits[:3])} (+{points})")
                break

    points = settings.get(LOCATION_POINTS.get(bucket, ""), 0)
    if points:
        score += points
        why.append(f"{bucket} (+{points})")

    text = f"{title}\n{description}".lower()
    tools = [t for t in settings["tools"] if t.lower() in text]
    if tools:
        points = min(len(tools) * settings["points_per_tool"], settings["points_tools_max"])
        score += points
        why.append(f"tools: {', '.join(tools[:4])} (+{points})")

    hit = _match(title, settings["senior_words"])
    years = None
    for found in re.finditer(r"\b(\d{1,2})\+?\s*(?:years|yrs)\b", description, flags=re.I):
        if int(settings.get("senior_years_min", 5)) <= int(found.group(1)) <= 19:
            years = found
            break
    if hit or years:
        score += settings["points_senior"]
        why.append(f"senior: {hit or years.group(0)} ({settings['points_senior']})")

    for kind, text in job.get("flags") or []:
        points = int(settings.get({"degree": "points_degree_asked",
                                   "offfield": "points_offfield_rescued"}.get(kind, ""), 0) or 0)
        score += points
        why.append(f"{text} ({points})" if points else text)

    if job.get("posted"):
        try:
            age = (today - date.fromisoformat(job["posted"])).days
            if 0 <= age <= settings["fresh_days"]:
                score += settings["points_fresh"]
                why.append(f"new ad (+{settings['points_fresh']})")
        except ValueError:
            pass
    return max(0, min(100, score)), label, "; ".join(why)
