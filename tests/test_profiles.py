"""The example profile (profiles/example-hr): HR jobs only, Athens or remote."""
from datetime import date

from scout import profile, settings as settings_mod
from scout.rate import rate
from scout.screen import screen


def hr_settings():
    s = dict(settings_mod.DEFAULTS)
    for key, value in profile.settings_changes("example-hr").items():
        if value is None:
            s.pop(key, None)
        else:
            s[key] = value
    return s


def job(title, location="Athens, Greece", remote=False, description=""):
    return {"title": title, "company": "X", "location": location, "remote": remote,
            "description": description, "url": "u", "source": "t", "posted": ""}


def test_default_profile_is_unchanged():
    assert profile.settings_changes("") == {}
    assert [k for k, _ in settings_mod.families(settings_mod.DEFAULTS)] == [
        "family_ecommerce", "family_ai_automation", "family_gtm", "family_operations", "family_generalist"]


def test_profile_files_exist():
    for name in ("settings.json", "profile.txt", "prompt.txt", "title_prompt.txt", "companies.csv"):
        assert profile.path(name, default_dir=None, name="example-hr")
    prompt = profile.read("prompt.txt", name="example-hr")
    assert "{profile}" in prompt and "{jobs}" in prompt


def test_hr_jobs_pass_and_others_go():
    s = hr_settings()
    for title in ("Talent Acquisition Specialist", "HR Business Partner", "Senior Recruiter",
                  "Employer Branding Specialist", "People Operations Coordinator",
                  "International Recruiter", "Internal Communications Specialist",
                  "Υπεύθυνη Ανθρώπινου Δυναμικού", "Learning & Development Specialist", "HR Generalist"):
        assert screen(job(title), s)[1] == "", title
    for title in ("E-commerce Specialist", "Accountant", "Sales Development Representative",
                  "HR Intern", "Customer Service Agent", "Άμεση Πρόσληψη Προσωπικού Αποθήκης",
                  "BEE The Future-Internship Program",
                  "Θέση Πρακτικής Άσκησης - Τμήμα Μισθοδοσίας & HR"):
        assert screen(job(title), s)[1] != "", title


def test_only_athens_or_remote():
    s = hr_settings()
    assert screen(job("HR Specialist", "Thessaloniki, Greece"), s)[1]
    assert screen(job("HR Specialist", "Berlin, Germany"), s)[1]
    assert screen(job("Recruiter", "Europe", remote=True), s) == ("Remote EU", "")
    assert screen(job("Recruiter", "Greece", remote=True), s) == ("Remote GR", "")


def test_degree_does_not_remove_but_other_languages_do():
    s = hr_settings()
    text = "Requirements:\n- Bachelor's degree in HR is required"
    assert screen(job("HR Specialist", description=text), s)[1] == ""
    assert screen(job("HR Specialist", description=text + "\n- Fluent Spanish required"), s)[1]


def test_rating_labels():
    s = hr_settings()
    score, label, _ = rate(job("Talent Acquisition Specialist"), "Athens", s, date(2026, 11, 17))
    assert label == "Talent Acquisition" and score >= 70
    score, label, _ = rate(job("Head of People", description="10+ years"), "Athens", s, date(2026, 11, 17))
    assert label == "HR / People" and score < 70
