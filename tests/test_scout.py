from datetime import date

from scout import settings as settings_mod
from scout.rate import rate
from scout.run import key_of, process
from scout.sheet import J
from scout.screen import degree_required, language_required, location_bucket, screen
from scout.sources import job

S = settings_mod.load()
TODAY = date(2026, 11, 16)


def make(title, company="Acme", location="Athens, Greece", remote=False, description="",
         restrictions=None, posted="2026-11-15", source="Test"):
    return job(source, title, company, f"https://example.com/{title.replace(' ', '-')}",
               location=location, remote=remote, description=description,
               restrictions=restrictions, posted=posted)


# ---------------- location
def test_location_buckets():
    assert location_bucket(make("x"))[0] == "Athens"
    assert location_bucket(make("x", location="Thessaloniki, Greece"))[0] == "Greece (other)"
    assert location_bucket(make("x", location="Greece", remote=True))[0] == "Remote GR"
    assert location_bucket(make("x", location="Europe", remote=True))[0] == "Remote EU"
    assert location_bucket(make("x", location="Worldwide", remote=True))[0] == "Remote EU"
    assert location_bucket(make("x", location="Zurich, Switzerland"))[0] == "Relocation"
    assert location_bucket(make("x", location="Berlin, Germany"))[0] == "Relocation"
    assert location_bucket(make("x", location="", remote=True))[0] == "Remote (unclear)"


def test_location_removed():
    assert location_bucket(make("x", location="USA", remote=True))[1]
    assert location_bucket(make("x", location="US", remote=True))[1]
    assert location_bucket(make("x", location="LATAM", remote=True))[1]
    assert location_bucket(make("x", location="New York, United States"))[1]
    assert location_bucket(make("x", location="London, UK"))[1]
    # a mixed list that includes Europe stays
    assert not location_bucket(make("x", location="USA, Europe", remote=True))[1]


# ---------------- deal-breakers
def test_degree():
    assert degree_required("A Bachelor's degree is required for this role.")
    assert degree_required("You must have a university degree in Business.")
    assert degree_required("Απαραίτητο πτυχίο ΑΕΙ οικονομικής κατεύθυνσης")
    assert not degree_required("Bachelor's degree is required, or equivalent experience.")
    assert not degree_required("A university degree is a plus.")
    assert not degree_required("Bachelor's degree preferred.")
    assert not degree_required("Πτυχίο ΑΕΙ/ΤΕΙ θα εκτιμηθεί")
    assert not degree_required("We care about what you can do, not your degree.")
    # a degree as its own requirement line counts, unless softened on that line
    assert degree_required("Requirements\n Bachelor's degree in Business Administration\n 2 years experience")
    assert degree_required("Προσόντα\n Πτυχίο ΑΕΙ/ΤΕΙ\n Άριστα Αγγλικά")
    assert not degree_required("Requirements\n Bachelor's degree or equivalent experience\n Excel")
    assert not degree_required("Nice to have\n Degree in Marketing is a plus")
    assert not degree_required("Skills\n Master's degree in Marketing is considered an asset.")
    assert not degree_required("Skills\n A degree in Computer Science, or hands-on technical experience.")
    assert not degree_required("Requirements\n Excel\nNice to have:\n SQL\n Bachelor's degree in Marketing")
    # "or a related field" names other degrees, it does not make the degree optional
    assert degree_required("Requirements:\n- Bachelor's degree in Business Administration, Marketing, Economics, or a related field\n- 2 years")
    assert degree_required("A Bachelor's degree in Finance or a related discipline is required.")
    assert degree_required("Requirements\n Bachelor's degree or equivalent qualification\n Excel")
    assert not degree_required("Requirements\n Bachelor's degree or relevant work experience\n Excel")


def test_language():
    assert language_required("Fluent German is required.") == "German"
    assert language_required("", "German-speaking Customer Operations Specialist") == "German"
    assert not language_required("German is a plus.")
    assert not language_required("Fluent in German preferred but not required.")
    assert not language_required("Fluent English and Greek.")


def test_other_dealbreakers_and_offfield():
    assert "Cold" in screen(make("Growth Associate", description="You will be cold calling leads."), S)[1]
    assert "Commission" in screen(make("Agent", description="This is a commission-only position."), S)[1]
    assert "Another field" in screen(make("Senior Backend Engineer"), S)[1]
    assert "Another field" in screen(make("Λογιστής"), S)[1]
    strict = dict(S, remove_degree_required="yes")
    assert "Degree" in screen(make("E-commerce Specialist",
                                   description="Bachelor's degree is required."), strict)[1]


def test_audit_2026_11_18_fixes():
    # a degree is flagged, not removed, and costs points
    flagged = dict(S, remove_degree_required="flag", points_degree_asked=-10)
    job = make("E-commerce Specialist", description="Bachelor's degree is required.")
    assert screen(job, flagged)[1] == ""
    assert any(kind == "degree" for kind, _ in job["flags"])
    assert "degree asked" in rate(job, "Athens", flagged)[2]
    assert not degree_required("Απαιτούμενα προσόντα:\n- Πτυχίο δευτεροβάθμιας εκπαίδευσης")
    assert not degree_required("Πτυχίο ανώτατης σχολής (προαιρετικό)")
    # "intern" no longer removes International / Internal titles; real internships still go
    for title in ("International Category Manager (Associate experience)", "Internal Sales Administrator",
                  "International Freight Road Operations & Customer Support"):
        assert screen(make(title), S)[1] == "", title
    assert "Another field" in screen(make("Marketing Intern"), S)[1]
    assert "Another field" in screen(make("Summer Internship"), S)[1]
    # off-field titles with a rescue word stay, with a penalty
    rescue = dict(S, offfield_rescue_words=["automation", "operations", "customer"], points_offfield_rescued=-15,
                  offfield_rescuable=["engineer", "driver"])
    for title in ("AI Automation Engineer", "Driver Operations Associate", "Customer Support Engineer"):
        job = make(title)
        assert screen(job, rescue)[1] == "", title
        assert any(kind == "offfield" for kind, _ in job["flags"])
    assert "Another field" in screen(make("Senior Backend Engineer"), rescue)[1]
    assert "Another field" in screen(make("Working Student - Automation Engineer"), rescue)[1]
    assert "Another field" in screen(make("Account Executive, Customer Success"), rescue)[1]
    # Indeed's Attica code and Greek-spelled suburbs are Athens
    for place in ("Κορωπί, GRI, Greece", "Ταύρος, GRI, Greece", "Μαρούσι, Greece", "Νέα Χαλκηδόνα, GRI, Greece"):
        assert location_bucket({"location": place, "remote": False})[0] == "Athens", place
    assert location_bucket({"location": "Γρεβενά, Greece", "remote": False})[0] == "Greece (other)"
    # old job-board ads are removed, company-feed ads are not (those are re-checked daily)
    aged = dict(S, max_ad_age_days=45)
    assert "Old ad" in screen(make("Operations Assistant", posted="2026-01-01", source="Himalayas"), aged)[1]
    assert screen(make("Operations Assistant", posted="2026-01-01", source="Company list (Ashby)"), aged)[1] == ""


def test_wanted_roles_are_never_removed():
    for title in ("Operations Assistant", "AI Automation Specialist", "AI Operations Associate",
                  "E-commerce Specialist", "Marketplace Coordinator", "Office Administrator",
                  "Customer Success Associate", "Catalog Data Specialist", "Project Coordinator",
                  "Υπάλληλος Γραφείου", "Υπεύθυνος E-shop", "Sales Operations Officer",
                  "Renewals Coordinator", "Content Operations Associate"):
        assert screen(make(title), S)[1] == "", title


# ---------------- rating
def test_rating_orders_sensibly():
    ecom = rate(make("E-commerce Specialist", description="Shopify and Excel"), "Athens", S, TODAY)
    ai = rate(make("AI Automation Specialist", description="n8n workflows"), "Athens", S, TODAY)
    assistant = rate(make("Operations Assistant"), "Athens", S, TODAY)
    unsorted = rate(make("Brand Ambassador"), "Remote (unclear)", S, TODAY)
    senior = rate(make("Head of E-commerce", description="10+ years of experience"), "Athens", S, TODAY)
    assert ecom[1] == "E-commerce" and ecom[0] >= 70
    assert ai[1] == "AI / Automation" and ai[0] >= 70
    assert assistant[0] >= 60
    assert unsorted[1] == "Unsorted" and unsorted[0] < 30
    assert senior[0] < ecom[0]


def test_generalist_with_family_description():
    score, label, _ = rate(make("Junior Associate", description="Help run our Shopify store: "
                                "update the product catalog, pricing and marketplace listings."),
                           "Athens", S, TODAY)
    assert label == "Generalist + E-commerce" and score >= 55
    # one stray word in a description is not enough
    assert rate(make("Junior Associate", description="We use AI and automation a bit."),
                "Athens", S, TODAY)[1] == "Generalist"


def test_tuning_from_first_live_run():
    from scout.screen import foreign_language_ad, language_in_title
    assert "Another field" in screen(make("Oracle Database Administrator"), S)[1]
    assert "Another field" in screen(make("Financial Analyst - Due Diligence"), S)[1]
    assert "Another field" in screen(make("Visual Merchandiser"), S)[1]
    assert language_in_title("Customer Support Specialist - Dutch - Remote in Greece") == "Dutch"
    assert not language_in_title("Operations Specialist")
    french = ("Nous recherchons une personne pour notre équipe. Vous travaillez avec les clients "
              "et les partenaires pour le développement des ventes dans une entreprise qui est "
              "en pleine croissance. Vous avez une expérience et vous aimez les défis pour nous. ") * 2
    assert foreign_language_ad(french) == "French"
    assert not foreign_language_ad("We are looking for a person to join our team and work with "
                                   "the clients and the partners for our growth. " * 3)
    assert location_bucket(make("x", location="London"))[1]
    # a phone line mentioned in passing is not a phone-heavy job
    assert screen(make("Reporting Analyst", description="You will report on our call center KPIs."), S)[1] == ""


def test_ai_word_does_not_match_inside_words():
    assert rate(make("Retail Chain Maintenance Planner"), "Athens", S, TODAY)[1] != "AI / Automation"


# ---------------- pipeline
def test_process_dedupes_and_skips_known():
    jobs = [make("E-commerce Specialist"), make("E-commerce Specialist"),
            make("Operations Assistant", company="Bolt"), make("Backend Engineer")]
    known = ({key_of("Bolt S.A.", "Operations Assistant")}, set())
    rows, removed, stats, queue, low = process(jobs, S, known, TODAY)
    assert [r[J["Title"]] for r in rows] == ["E-commerce Specialist"]
    assert stats["duplicates"] == 1 and stats["already_known"] == 1 and len(removed) == 1
    assert rows[0][J["Status"]] == "New" and rows[0][J["Work"]] == "On-site"
    assert not rows[0][J["Why this score"]].startswith(("+", "=", "-"))
    assert [(k, r is rows[0]) for k, _, r in queue] == [(rows[0][J["Key"]], True)]


def test_listed_jobs_without_ai_fit_join_the_queue():
    jobs = [make("Operations Assistant", company="Bolt"), make("E-commerce Specialist")]
    key = key_of("Bolt", "Operations Assistant")
    rows, removed, stats, queue, low = process(jobs, S, ({key}, set()), TODAY, waiting={key})
    assert len(rows) == 1 and not removed
    assert [(k, r is None) for k, _, r in queue] == [(rows[0][J["Key"]], False), (key, True)]


def test_ai_answers_are_read_safely():
    from scout import ai
    answer = '''```json
    [{"job_index": 0, "eligibility": "eligible", "fit": 72, "note": "Good match.", "salary": "EUR 1,400", "work": "Hybrid"},
     {"job_index": 1, "eligibility": "nonsense", "fit": null, "note": "", "salary": "", "work": "Moon"},
     {"job_index": 9, "fit": 50}]```'''
    got = ai.parse(answer, 2)
    assert got[0]["fit"] == 72 and got[0]["note"].startswith("Eligible. Good") and got[0]["work"] == "Hybrid"
    assert got[1]["fit"] == "" and got[1]["eligibility"] == "uncertain" and got[1]["work"] == ""
    assert 9 not in got and ai.parse("sorry", 2) == {}


def test_ai_is_capped_and_survives_errors():
    from scout import ai
    settings = dict(S, ai_max_jobs_per_run=7, ai_jobs_per_call=3, ai_calls_per_minute=60)
    calls = []

    def fake(model, text):
        calls.append(model)
        if len(calls) == 2:
            raise RuntimeError("429: quota")
        return '[{"job_index": 0, "eligibility": "eligible", "fit": 60, "note": "ok"}]'
    jobs = [make(f"Operations Assistant {i}") for i in range(20)]
    results, info = ai.evaluate(jobs, settings, call=fake, sleep=lambda s: None)
    assert len(calls) == 4 and set(results) == {0, 3, 6}  # 3 batches for 7 jobs, one retried after a 429
    calls.clear()
    results, info = ai.evaluate(jobs, settings, call=lambda m, t: (_ for _ in ()).throw(RuntimeError("500: down")),
                                sleep=lambda s: None)
    assert results == {} and "Stopped early" in info


def test_salary_and_title_link():
    from scout.extract import find_salary
    from scout.sheet import _plain, safe, title_link
    assert find_salary("Salary: €1,200 - €1,500 gross per month") == "€1,200 - €1,500 gross per month"
    assert find_salary("We raised $50 million in funding") == ""
    assert find_salary("μισθός 1.100€ καθαρά").startswith("1.100€")
    link = title_link('Manager, "Ops" team', "https://x.test/a")
    assert link.startswith("=HYPERLINK(") and _plain(link) == 'Manager, "Ops" team'
    assert safe("+45 title") == "'+45 title" and safe("plain") == "plain"


def test_settings_round_trip():
    rows = settings_mod.to_sheet_rows(settings_mod.DEFAULTS)
    assert settings_mod.load(settings_mod.parse_sheet_rows(rows)) == settings_mod.DEFAULTS


def test_find_ats():
    from scout.ats import _slugs, find_ats
    assert find_ats("https://job-boards.greenhouse.io/adyen") == ("Greenhouse", "adyen")
    assert find_ats("https://job-boards.eu.greenhouse.io/bitpanda") == ("Greenhouse", "bitpanda")
    assert find_ats('<script src="https://boards.greenhouse.io/embed/job_board/js?for=wolt">') == ("Greenhouse", "wolt")
    assert find_ats("https://jobs.lever.co/protolabs?location=Amsterdam") == ("Lever", "protolabs")
    assert find_ats("https://jobs.ashbyhq.com/n8n") == ("Ashby", "n8n")
    assert find_ats("https://apply.workable.com/plaisio-careers/") == ("Workable", "plaisio-careers")
    assert find_ats("https://careers.smartrecruiters.com/Gcore") == ("SmartRecruiters", "Gcore")
    assert find_ats("https://caravelo.jobs.personio.com/")[0] == "Personio"
    assert find_ats("https://sedgwick.wd1.myworkdayjobs.com/en-US/Sedgwick")[0] == "Workday"
    assert find_ats("https://www.kraken.com/careers") == ("", "")
    assert "welcomepickups" in _slugs("Welcome Pickups", "welcomepickups.com")


def test_find_all_skips_generic_ids():
    from scout import ats
    assert ats.find_ats("https://apply.workable.com/j/ABC123") == ("", "")
    assert ats.find_ats("see https://get.workable.com/demo") == ("", "")
    html = "https://boards.greenhouse.io/digible x https://jobs.ashbyhq.com/remote"
    assert ats.find_all(html) == [("Greenhouse", "digible"), ("Ashby", "remote")]


def test_detect_prefers_boards_with_jobs(monkeypatch):
    from scout import ats
    counts = {("Greenhouse", "digible"): 5, ("Ashby", "remote"): 40, ("Greenhouse", "getyourguide"): 0,
              ("Ashby", "getyourguide"): 60, ("Workable", "zalando"): 0}
    monkeypatch.setattr(ats, "_count", lambda a, b, n: counts.get((a, b), -1))
    monkeypatch.setattr(ats, "_guesses", lambda n, w: [("Ashby", "getyourguide")] if "Guide" in n else [])
    # a careers page that links to someone else's board first
    got = ats.detect("Remote", careers="https://boards.greenhouse.io/digible https://jobs.ashbyhq.com/remote")
    assert got[:2] == ("Ashby", "remote") and got[3] == 40
    # an old empty board loses to a name match that has jobs
    got = ats.detect("GetYourGuide", careers="https://boards.greenhouse.io/getyourguide")
    assert got[:2] == ("Ashby", "getyourguide")
    # a guessed board with no jobs is not accepted
    monkeypatch.setattr(ats.requests, "get", lambda *a, **k: (_ for _ in ()).throw(ats.requests.RequestException()))
    assert ats.detect("Zalando", "zalando.com")[2] == "No feed found"


def test_open_calls_are_removed():
    for title in ("Join our Talent Pool", "Join Skroutz", "Open Application", "Spontaneous application - Athens"):
        _, reason = screen(make(title), S)
        assert reason.startswith("General application"), title
    assert not screen(make("E-commerce Specialist"), S)[1]


def test_pages_tried_when_looking_for_a_company_feed():
    from scout.ats import _looks_like, _pages
    pages = _pages("acme.com", "https://acme.com/work-with-us")
    assert pages[0] == "https://acme.com/work-with-us" and "https://careers.acme.com" in pages
    assert _looks_like("Storytel", "storytel.com", "jobs.storytel.com")
    assert not _looks_like("Storytel", "storytel.com", "otherfirm")


def test_revops_and_customer_success_are_first_class():
    for title in ("Revenue Operations Specialist", "Customer Success Associate", "Account Manager"):
        score, label, why = rate(make(title), "Athens", S, TODAY)
        assert label == "RevOps / Customer Success" and score >= 60, (title, score, label)


def test_country_from_location():
    from scout.extract import country
    assert country("Αθήνα, GRI, Greece") == "Greece" and country("Marousi") == "Greece"
    assert country("Berlin or Barcelona") == "Germany, Spain"
    assert country("Remote, EMEA") == "Europe" and country("Remote") == ""
    assert country("Business Operations") == ""  # "us" inside a word is not a country


class FakeSheet:
    def __init__(self, rows):
        self.id, self.rows, self.cleared, self.appended = 1, rows, [], []

    def get_all_values(self, **kw):
        return self.rows

    def update(self, values, range_name, value_input_option=None):
        self.written = values

    def batch_update(self, updates, value_input_option=None):
        self.updates = updates

    def batch_clear(self, ranges):
        self.cleared = ranges

    def append_rows(self, rows, value_input_option=None):
        self.appended += rows


class FakeBook:
    def __init__(self, jobs):
        self.tabs = {"Jobs": jobs, "Old jobs": FakeSheet([["Key"]])}

    def worksheet(self, name):
        return self.tabs[name]


def _sheet_row(**values):
    from scout.sheet import J, JOBS_HEADER
    row = [""] * len(JOBS_HEADER)
    for name, value in values.items():
        row[J[name]] = value
    return row


def test_closed_jobs_are_marked_and_old_jobs_move_out():
    from datetime import date
    from scout import sheet
    head = sheet.JOBS_HEADER
    rows = [head,
            _sheet_row(Company="Acme", Title="Ops A", Source="Company list (Lever)", Status="New",
                       Found="2026-11-10", Key="acme|ops a", Link="https://a"),
            _sheet_row(Company="Acme", Title="Ops B", Source="Company list (Lever)", Status="New",
                       Found="2026-11-10", Key="acme|ops b", Link="https://b"),
            _sheet_row(Company="Down", Title="Ops C", Source="Company list (Lever)", Status="New",
                       Found="2026-11-10", Key="down|ops c", Link="https://c"),
            _sheet_row(Company="Shop", Title="Ops D", Source="Indeed", Status="Applied",
                       Found="2026-01-01", Key="shop|ops d", Link="https://d")]
    book = FakeBook(FakeSheet(rows))
    closed, moved = sheet.tidy_jobs(book, date(2026, 11, 17), 30, {"acme|ops a"}, {"Acme"})
    assert (closed, moved) == (1, 0)  # only B: C's company could not be read, D is not from a feed
    assert book.tabs["Jobs"].updates == [{"range": "N3", "values": [["Closed"]]}]

    rows[1][sheet.J["Found"]] = "2026-09-01"
    book = FakeBook(FakeSheet(rows))
    closed, moved = sheet.tidy_jobs(book, date(2026, 11, 17), 30, {"acme|ops a", "acme|ops b"}, {"Acme"})
    assert moved == 1 and book.tabs["Old jobs"].appended[0][0] == "acme|ops a"
    kept = book.tabs["Jobs"].written
    assert len(kept) == 3 and kept[-1][sheet.J["Status"]] == "Applied"  # Applied rows never move
    assert kept[0][sheet.J["Title"]].startswith("=HYPERLINK(")
    assert book.tabs["Jobs"].cleared == ["A5:S5"]


def test_greek_capitals_without_accents_still_match():
    from scout.screen import screen
    job = make("ΥΠΕΥΘΥΝΟΣ ΗΛΕΚΤΡΟΝΙΚΟΥ ΚΑΤΑΣΤΗΜΑΤΟΣ", location="ΑΘΗΝΑ")
    bucket, reason = screen(job, S)
    assert (bucket, reason) == ("Athens", "")  # an e-shop job, not store staff
    assert rate(job, bucket, S, TODAY)[1] == "E-commerce"
    assert screen(make("Υπάλληλος Καταστήματος", location="Αθήνα"), S)[1].startswith("Another field")
    assert rate(make("Υπάλληλος Γραφείου"), "Athens", S, TODAY)[1] == "Generalist"


def test_title_check_picks_low_scored_jobs():
    from scout import ai
    jobs = [make(f"Role {i}") for i in range(5)]
    settings = dict(S, ai_titles_per_call=3, ai_calls_per_minute=600)
    answers = iter(["[0, 2]", "nonsense"])
    picked, seen, info = ai.title_check(jobs, settings, call=lambda m, t: next(answers), sleep=lambda s: None)
    assert picked == {0, 2} and seen == {0, 1, 2}  # the second call failed: those stay unchecked


def test_jobfind_feed_is_read(monkeypatch):
    from scout import sources
    feed = ('﻿<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><item>'
            '<title>Υπάλληλος Back Office – Τμήμα Προμηθειών (α/γ) - ΑΘΗΝΑ - ΑΤΤΙΚΗ</title>'
            '<link>https://www.jobfind.gr/JobAd/View/GR/Theseis_Ergasias/454DED45-6CBC</link>'
            '<description><![CDATA[ SAP, back-office ]]></description><region><![CDATA[ΑΤΤΙΚΗ]]></region>'
            '<pubDate>Mon, 16 Nov 2026 21:41:42 GMT</pubDate></item></channel></rss>').encode("utf-8")

    class Reply:
        content = feed

        def raise_for_status(self):
            pass
    monkeypatch.setattr(sources.requests, "get", lambda *a, **k: Reply())
    found = sources.jobfind(S)[0]
    assert found["title"] == "Υπάλληλος Back Office – Τμήμα Προμηθειών (α/γ)"
    assert found["location"] == "ΑΘΗΝΑ, ΑΤΤΙΚΗ, Greece" and found["company"] == "Jobfind ad 454DED45"
    from scout.screen import screen
    assert screen(found, S) == ("Athens", "")
    assert rate(found, "Athens", S, TODAY)[1] == "Operations"


def test_scouted_flag():
    from scout.sheet import scouted
    assert scouted("OK (found on careers page)") == "Yes"
    assert scouted("OK (no open jobs right now)") == "Yes"
    assert scouted("OK (last read failed)") == "No"
    assert scouted("Feed error (HTTPError 429)") == "No"
    assert scouted("No feed found") == "No"


def test_gtm_phrases_protect_titles():
    from scout import settings as settings_mod
    from scout.screen import offfield
    s = settings_mod.load()
    assert offfield("Salesforce Administrator", s) == ""
    assert offfield("Technical Account Manager (Remote Europe)", s) == ""
    assert offfield("Finance Operations Specialist", s) == ""
    assert offfield("Salesforce Developer", s) == "developer"
    assert offfield("Revenue Accountant", s) == "accountant"


def test_same_job_for_several_places_is_listed_once():
    jobs = [make("AI Venture Builder (m/f/d) - Germany remote", company="GoStudent"),
            make("AI Venture Builder (m/f/d) - Italy remote", company="GoStudent"),
            make("Stock Room Employee #JD Glyfada", company="Cosmos"),
            make("Account Manager - Retail"), make("Account Manager - Hospitality")]
    known = ({key_of("Cosmos", "Stock Room Employee")}, set())
    rows, removed, stats, queue, low = process(jobs, S, known, TODAY)
    titles = sorted(r[J["Title"]] for r in rows)
    assert titles == ["AI Venture Builder (m/f/d) - Germany remote", "Account Manager - Hospitality",
                      "Account Manager - Retail"]
    assert stats["duplicates"] == 1 and stats["already_known"] == 1


def test_ai_fit_is_capped_from_the_facts_it_read():
    from scout import ai
    answer = '''[
     {"job_index": 0, "level": "head", "years": 8, "degree": "none", "pay": "salary", "field": "core",
      "eligibility": "eligible", "fit": 80, "note": "Strong AI fit."},
     {"job_index": 1, "level": "junior", "years": 1, "degree": "required", "pay": "salary", "field": "other",
      "eligibility": "eligible", "fit": 75, "note": "Stock room work."},
     {"job_index": 2, "level": "mid", "years": 6, "pay": "commission", "field": "core", "fit": 80, "note": "x"},
     {"job_index": 3, "level": "junior", "years": 2, "degree": "none", "pay": "salary", "field": "core",
      "eligibility": "eligible", "fit": 88, "note": "E-shop admin."},
     {"job_index": 4, "eligibility": "eligible", "fit": 90, "note": "Old prompt, no facts."}]'''
    got = ai.parse(answer, 5)
    assert got[0]["fit"] == 40 and "lead/head" in got[0]["note"]
    assert got[1]["fit"] == 35 and got[1]["eligibility"] == "uncertain" and "Degree asked" in got[1]["note"]
    assert got[2]["fit"] == 30 and "no fixed pay" in got[2]["note"] and "6+ years" not in got[2]["note"]
    assert got[3]["fit"] == 88 and "Capped" not in got[3]["note"]
    assert got[4]["fit"] == 90  # another profile's own prompt: no limits
    long = "Intro. " * 300 + "Requirements: Bachelor's degree required."
    assert ai._description(long).endswith("Bachelor's degree required.") and len(ai._description(long)) < 3600


def test_degree_asked_column():
    flagged = dict(S, remove_degree_required="flag")
    jobs = [make("E-commerce Specialist", description="Requirements:\n- Bachelor's degree in Marketing\n- Excel"),
            make("Operations Assistant")]
    rows, removed, stats, queue, low = process(jobs, flagged, (set(), set()), TODAY)
    by_title = {r[J["Title"]]: r for r in rows}
    assert by_title["E-commerce Specialist"][J["Degree asked"]] == "Yes"
    assert by_title["Operations Assistant"][J["Degree asked"]] == ""
    from scout import ai
    got = ai.parse('[{"job_index": 0, "degree": "required", "fit": 60, "note": "x"}]', 1)
    assert got[0]["degree"] is True


def test_family_words_match_at_word_start_only():
    from scout.rate import _match
    assert _match("Guest Services Agent, Bellman", ["llm"]) == ""
    assert _match("Reseller Partner Development Manager", ["seller"]) == ""
    assert _match("Seller Support Specialist", ["seller"]) == "seller"
    assert _match("LLM Evaluation Specialist", ["llm"]) == "llm"


def test_greek_and_latin_company_suffixes_give_one_key():
    from scout.run import key_of
    assert key_of("EXAMPLE GROUP AEBE", "Category Specialist") == key_of("EXAMPLE GROUP ΑΕΒΕ", "Category Specialist")
