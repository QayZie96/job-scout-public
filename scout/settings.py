"""Default settings. The Settings tab in the sheet overrides any of these.

Lists are stored in the sheet as comma-separated text, numbers as numbers.
A profile (SCOUT_PROFILE, see scout/profile.py) changes these defaults first.
"""
from . import profile as profile_mod

DEFAULTS = {
    # --- Workable search (jobs.workable.com). One request per keyword per location.
    "workable_keywords": [
        "ecommerce", "e-commerce", "eshop", "marketplace", "catalog", "product data",
        "content", "operations", "assistant", "coordinator", "specialist", "automation",
        "AI", "data entry", "back office", "logistics", "supply chain", "customer success",
        "account manager", "category", "merchandising", "pricing", "CRM", "analyst",
        "project", "administrator", "junior", "support", "sales operations", "order",
        # added by the 2026-11-18 coverage audit
        "revops", "revenue operations", "renewals", "onboarding", "implementation", "merchant",
        "partner", "seller", "vendor", "key account", "procurement", "purchasing", "buyer",
        "inventory", "trading", "product specialist", "customer operations", "business analyst",
        "no-code", "n8n", "AI operations", "amazon", "shopify", "skroutz",
    ],
    # Cyprus: Greek-speaking, no visa, many e-commerce, fintech and operations jobs
    "workable_locations": ["Athens, Greece", "Greece", "Cyprus"],

    # --- Indeed Greece search. One request per keyword. Jobs older than indeed_hours_old are skipped.
    "indeed_keywords": [
        "e-commerce", "e-shop", "marketplace", "operations", "sales operations", "back office",
        "automation", "AI", "product data", "catalog", "pricing", "data entry",
        "customer success", "account manager", "ηλεκτρονικό κατάστημα", "υπάλληλος γραφείου", "εξυπηρέτηση πελατών", "υποστήριξη πωλήσεων",
        "revenue operations", "key account", "onboarding", "procurement", "buyer", "logistics",
        "category", "e-shop administrator", "τμήμα αγορών", "προμηθειών", "τιμολόγηση", "διαχείριση παραγγελιών",
    ],
    "indeed_location": "Athens",
    "indeed_results_per_search": 30,
    "indeed_hours_old": 96,

    # --- Role families. A match in the title gives title points; only in the
    # description gives description points. First family that matches is the label.
    # "families" lists them in order as name=Label; each one's words are in family_<name>.
    # The family called "generalist" gets the smaller generalist points.
    "families": ["ecommerce=E-commerce", "ai_automation=AI / Automation",
                 "gtm=RevOps / Customer Success", "operations=Operations", "generalist=Generalist"],
    # yes = remove every job whose title matches none of the families
    "title_must_match_family": "no",
    "family_ecommerce": [
        "e-commerce", "ecommerce", "e-shop", "eshop", "online store", "marketplace",
        "catalog", "catalogue", "product data", "product content", "product listing", "listings",
        "merchandising", "category manag", "category specialist", "category assistant", "pricing", "amazon",
        "ebay", "shopify", "skroutz", "woocommerce", "magento", "pim",
        "master data", "product information", "online sales", "digital commerce", "ηλεκτρονικού καταστήματος", "ηλεκτρονικό κατάστημα",
        "ηλεκτρονικού εμπορίου",
        "ηλεκτρονικό εμπόριο", "ηλεκτρονικών πωλήσεων", "διαχείριση προϊόντων", "διαχείρισης προϊόντων", "καταχώρηση προϊόντων", "καταχώρησης προϊόντων", "καταχώριση προϊόντων", "κατηγορίας προϊόντων", "e-commerce manager",
        "assortment", "promotions", "merchant", "seller", "vendor manag", "content operations",
    ],
    "family_operations": [
        "operations", " ops ", "back office", "backoffice", "order management", "order processing",
        "fulfilment", "fulfillment", "logistics", "supply chain", "inventory", "revops",
        "revenue operations", "sales operations", "business operations", "renewals", "onboarding specialist", "partner success",
        "partner operations", "seller support", "seller operations", "merchant operations", "merchant success", "vendor operations",
        "process improvement", "finance operations", "financial operations", "λειτουργιών", "εφοδιαστικ", "παραγγελιών",
        "διαχείριση παραγγελιών", "εξυπηρέτηση παραγγελιών", "υποστήριξη λειτουργιών", "υποστήριξης λειτουργιών", "λειτουργίας", "αποθεμάτων", "διεκπεραίωση",
        "trading operations", "operations analyst", "data quality",
        "buyer", "purchasing", "procurement", "sourcing", "αγορών", "προμηθειών",
    ],
    "family_ai_automation": [
        " ai ", "a.i.", "artificial intelligence", "automation", "automations", "no-code",
        "no code", "low-code", "low code", "n8n", "zapier", "make.com",
        "prompt", "llm", "genai", "generative ai", "chatbot", "conversational",
        "agent flow", "ai agent", "αυτοματοποίηση", "τεχνητή νοημοσύνη", "τεχνητής νοημοσύνης",
        "αυτοματοποίησης", "ψηφιακού μετασχηματισμού", "ai automation",
        "ai trainer", "ai operations", "workflow automation",
    ],
    "family_gtm": [
        "revops", "revenue operations", "sales operations", "sales ops", "gtm operations", "go-to-market",
        "customer success", "account manager", "account management", "renewals", "sales enablement",
        "revenue enablement", "crm specialist", "crm operations", "crm administrator", "crm manager",
        "customer onboarding", "partner success", "hubspot",
        # these also keep a title that has "salesforce", "technical account" or "finance" in it
        "salesforce administrator", "salesforce admin", "salesforce consultant", "salesforce analyst",
        "salesforce specialist", "revenue systems", "business systems", "gtm systems", "technical account manager",
        "client success", "customer experience", "implementation specialist", "implementation consultant",
        "implementation manager",
        "διαχείριση πελατών", "διαχείρισης πελατών", "υποστήριξη πωλήσεων", "υποστήριξης πωλήσεων", "επιτυχίας πελατών", "ανανεώσεων",
        "key account", "account coordinator", "customer operations", "client services", "partner manager",
    ],
    "family_generalist": [
        "assistant", "coordinator", "specialist", "associate", "administrator", "administrative",
        "generalist", "officer", "data entry", "analyst", "junior", "project coordinator",
        "account manager", "customer success", "βοηθός", "υπάλληλος γραφείου", "συντονιστ", "γραμματ",
        "διοικητικ", "στέλεχος",
        "εξυπηρέτηση πελατών", "εξυπηρέτησης πελατών", "καταχώρηση δεδομένων", "καταχώρησης δεδομένων", "υπεύθυνος", "υπεύθυνη", "διαχειριστής", "υποστήριξη", "υποστήριξης", "γραφείου",
    ],
    "points_family_title": 45,
    "points_generalist_title": 15,
    "points_family_description": 15,
    # how many different family words the description needs before it counts
    "description_min_hits": 3,

    # --- Location points
    "points_athens": 20,
    "points_remote_greece": 20,
    "points_remote_eu": 15,
    "points_relocation": 10,
    "points_greece_other": -10,  # on-site in Greece outside Attica means moving inside Greece
    "points_remote_unclear": 5,

    # --- Tools the user really has
    "tools": [
        "google sheets", "ebay", "amazon seller", "seller central", "hubspot", "n8n",
        "shopify", "zapier", "looker", "power bi", "chatgpt", "claude",
        "woocommerce", "magento", "skroutz",  # "excel" left out: nearly every office ad names it
    ],
    "points_per_tool": 5,
    "points_tools_max": 10,

    # --- Seniority and freshness
    "senior_words": [
        "senior", "sr.", "sr ", "lead", "head of", "director", "principal", "vp ",
        "vice president", "chief", "staff ", "διευθυντ", "προϊστάμεν",
    ],
    "points_senior": -15,
    # an ad asking for at least this many years counts as senior
    "senior_years_min": 5,
    "fresh_days": 3,
    "points_fresh": 5,

    # --- Clearly another field (title only). Removed, shown in Filtered out.
    "offfield_titles": [
        "engineer", "developer", "programmer", "devops", "sre", "architect",
        "software", "frontend", "front-end", "backend", "back-end", "full stack",
        "fullstack", "data scientist", "machine learning", "ml ", "qa ", "tester",
        "cyber", "security", "database", "sysadmin", "system administrator", "systems administrator",
        "it support", "it project", "it consultant", "it helpdesk", "helpdesk", "network",
        "sap ", "oracle", "servicenow", "salesforce", "technical support", "technical account",
        "nurse", "doctor", "physician", "pharmacist", "dentist", "therapist",
        "medical", "clinical", "health coach", "accountant", "accounting", "auditor",
        "tax ", "payroll", "finance", "financial", "treasury", "credit collection",
        "mortgage", "lawyer", "legal", "counsel", "attorney", "paralegal",
        "driver", "chef", "cook", "waiter", "barista", "bartender",
        "housekeep", "cleaner", "electrician", "plumber", "mechanic", "technician",
        "welder", "warehouse worker", "fiber", "ftth", "construction", "civil",
        "mep ", "teacher", "professor", "tutor", "designer", "ux ",
        "ui ", "animator", "video editor", "copywriter", "translator", "interpreter",
        "recruiter", "recruiting", "talent acquisition", "hr ", "human resources", "sales representative",
        "sales development", "sales associate", "sales executive", "sales advisor", "sales manager", "sales account",
        "business development", "sdr", "bdr", "account executive", "telesales", "call center",
        "call centre", "appointment setter", "store manager", "in store", "in-store", "visual merchandis",
        "public area", "front office", "receptionist", "intern", "internship", "trainee",
        "stage ", "stagiaire", "werkstudent", "praktikum", "alternance", "working student",
        "μηχανικ", "προγραμματιστ", "λογιστ", "οδηγός", "νοσηλευτ", "πωλητ",
        "ταμίας", "αποθήκης", "αποθηκάρι", "σερβιτόρ", "μάγειρ", "τεχνικός",
        "δικηγόρ", "πρακτική άσκηση", "καταστήματος", "τηλεφωνικής",
        "stock room", "stockroom", "groom", "καθαριότητ", "προσωπικό ασφαλείας", "φύλακ",
    ],

    # A title with an off-field word ("engineer", "driver", "legal") stays in the list, with
    # points_offfield_rescued, when it also has one of these words (the AI then judges it).
    "offfield_rescue_words": [],
    # the off-field words that a rescue word can outweigh (never intern, working student, recruiter...)
    "offfield_rescuable": [],
    "points_offfield_rescued": 0,
    # job-board ads (not company feeds, which are re-checked daily) older than this are removed; 0 = off
    "max_ad_age_days": 0,

    # --- Other filters
    # job types (Athens, Greece (other), Remote GR, Remote EU, Remote (unclear), Relocation,
    # Location unclear) that are removed
    "removed_types": [],
    # yes = remove the job; flag = keep it, add points_degree_asked and say so in Why this score; no = ignore
    "remove_degree_required": "yes",
    "points_degree_asked": 0,
    # languages besides English and Greek that do not get a job removed
    "ok_languages": [],

    # --- Housekeeping
    "filtered_out_days": 14,
    # jobs still New (or Closed) this many days after they were found move to the Old jobs tab
    "jobs_keep_days": 30,
    # the Best tab shows jobs with at least this AI fit, found in the last best_days days
    "best_min_ai_fit": 70,
    "best_days": 3,

    # --- AI check (Gemini). Runs only when the GEMINI_API_KEY secret is set.
    "ai_enabled": "yes",
    "ai_model": "gemini-3.5-flash-lite",
    # most jobs sent to the AI in one run, best scores first
    "ai_max_jobs_per_run": 100,
    # jobs scoring below this are not sent to the AI
    "ai_min_score": 20,
    # jobs below ai_min_score get a cheap "title check": the AI sees only titles, many per call,
    # and picks the ones worth a full read. This many titles per run at most (0 = off).
    "ai_title_check_per_run": 600,
    "ai_titles_per_call": 60,
    "ai_jobs_per_call": 5,
    "ai_calls_per_minute": 10,
}


# Defaults for the original (no SCOUT_PROFILE) search only, from the 2026-11-18 audit.
# Other profiles keep the neutral values above unless their settings.json sets them.
OWN_PROFILE_DEFAULTS = {
    "offfield_rescue_words": [
        "automation", "no-code", "low-code", "n8n", "zapier", "prompt", "workflow", "operations",
        " ops ", "implementation", "onboarding", "customer", "revops", "gtm",
        "e-commerce", "ecommerce", "marketplace", "merchant", "seller", "λειτουργιών",
    ],
    "offfield_rescuable": ["engineer", "driver", "legal", "finance", "financial", "technical support",
                           "technical account", "salesforce"],
    "points_offfield_rescued": -15,
    "max_ad_age_days": 45,
    "remove_degree_required": "flag",
    "points_degree_asked": -10,
}
if not profile_mod.NAME:
    DEFAULTS.update(OWN_PROFILE_DEFAULTS)

for _key, _value in profile_mod.settings_changes().items():
    if _value is None:
        DEFAULTS.pop(_key, None)
    else:
        DEFAULTS[_key] = _value


def families(settings):
    """[(settings key, label), ...] in order."""
    out = []
    for item in settings.get("families") or []:
        name, _, label = str(item).partition("=")
        name = name.strip().replace(" ", "_")
        if name and f"family_{name}" in settings:
            out.append((f"family_{name}", label.strip() or name))
    return out


def parse_sheet_rows(rows):
    """Turn Settings tab rows [[key, value], ...] into overrides."""
    out = {}
    for row in rows:
        if len(row) < 2 or not str(row[0]).strip() or str(row[0]).startswith("#"):
            continue
        key, raw = str(row[0]).strip(), str(row[1]).strip()
        if key not in DEFAULTS:
            continue
        default = DEFAULTS[key]
        if isinstance(default, list):
            # keep leading/trailing spaces inside quotes out of the picture: items
            # written like "ai " in the sheet use _ for a space (e.g. "_ai_").
            sep = ";" if ";" in raw else ","
            out[key] = [i.strip() if key == "families" else i.strip().replace("_", " ")
                        for i in raw.split(sep) if i.strip()]
        elif isinstance(default, str):
            if raw:
                out[key] = raw
        else:
            try:
                out[key] = int(float(raw))
            except ValueError:
                pass
    return out


def to_sheet_rows(settings):
    rows = []
    for key, value in settings.items():
        if isinstance(value, list):
            sep = "; " if any("," in v for v in value) else ", "
            value = sep.join(("_" if v[0] == " " else "") + v.strip()
                             + ("_" if v[-1] == " " else "") for v in value)
        rows.append([key, value])
    return rows


def load(overrides=None):
    settings = dict(DEFAULTS)
    settings.update(overrides or {})
    return settings
