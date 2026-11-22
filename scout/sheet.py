"""Google Sheet reader/writer. Only touches the tabs this tool owns
(Jobs, Filtered out, Settings, Scout Companies). It reads Applications but never writes to it."""
import json
import os
import re

import gspread

from . import settings as settings_mod
from .extract import country
from .text import base_title

JOBS, FILTERED, SETTINGS, APPLICATIONS = "Jobs", "Filtered out", "Settings", "Applications"
JOBS_HEADER = ["Company", "Title", "Location", "Country", "Work", "Salary", "Score", "AI fit", "Label",
               "Type", "Source", "Posted", "Found", "Status", "Degree asked", "AI note", "Why this score", "Link", "Key"]
JOBS_WIDTHS = [170, 320, 190, 110, 80, 170, 55, 55, 170, 110, 150, 85, 85, 80, 70, 380, 330, 120, 120]
J = {name: i for i, name in enumerate(JOBS_HEADER)}
FILTERED_HEADER = ["First removed", "Reason", "Title", "Company", "Location", "Source", "Link",
                   "Last seen", "Key"]
STATUSES = ["New", "Applied", "Skip", "Closed"]
BEST, OLD_JOBS = "Best", "Old jobs"
BEST_COLUMNS = ["Company", "Title", "Location", "Country", "Work", "Salary", "AI fit", "Score", "Label",
                "Type", "Posted", "Found", "AI note"]
BEST_WIDTHS = [170, 340, 190, 110, 80, 170, 55, 55, 170, 110, 85, 85, 420]
OLD_HEADER = ["Key", "Company", "Title", "Link", "Found", "Status", "Moved here"]
COMPANIES, OLD_COMPANIES = "Scout Companies", "Companies"
COMPANIES_HEADER = ["Company", "Website", "Careers page", "ATS", "Board ID", "Status",
                    "Jobs read", "Last checked", "Scouted now?", "Why added",
                    "To add a company: type its name and website in a new row. The rest fills in by itself."]


def open_book():
    if not os.getenv("SHEET_ID", "").strip():
        # never fall back to another person's sheet
        raise SystemExit("SHEET_ID is empty: add this profile's sheet ID as a repository secret.")
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    client = gspread.service_account_from_dict(info)
    return client.open_by_key(os.environ["SHEET_ID"])


def _tab(book, title, header, cols=None):
    try:
        return book.worksheet(title), False
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=title, rows=200, cols=cols or len(header))
        ws.update(values=[header], range_name="A1")
        ws.freeze(rows=1)
        ws.format("1:1", {"textFormat": {"bold": True}})
        return ws, True


def load_settings(book):
    ws, created = _tab(book, SETTINGS, ["Setting", "Value", "Lists are comma-separated. "
                                        "Use _ for a space at the start or end of a word."])
    if created:
        ws.update(values=settings_mod.to_sheet_rows(settings_mod.DEFAULTS), range_name="A2")
        return settings_mod.load()
    rows = ws.get_all_values()[1:]
    known = {r[0] for r in rows if r}
    missing = [r for r in settings_mod.to_sheet_rows(settings_mod.DEFAULTS) if r[0] not in known]
    if missing:  # new settings added by a later version
        ws.append_rows(missing)
    return settings_mod.load(settings_mod.parse_sheet_rows(rows))


def safe(value):
    """Text that Sheets will not mistake for a formula."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def title_link(title, url):
    quote = lambda text: str(text).replace('"', '""')  # noqa: E731
    return f'=HYPERLINK("{quote(url)}","{quote(title)}")' if url else safe(title)


def _jobs_tab(book):
    """The Jobs tab in the current layout. An older layout is converted in place:
    every row and its Status is kept, new columns are added empty."""
    ws, created = _tab(book, JOBS, JOBS_HEADER)
    values = ws.get_all_values()
    head = values[0] if values else []
    if head[:len(JOBS_HEADER)] == JOBS_HEADER:
        if created:  # a brand-new tab (a new person's sheet) gets the colours, filter and widths too
            ws.resize(rows=200, cols=len(JOBS_HEADER))
            _style_jobs(book, ws)
        return ws, values[1:]
    old = {h.strip(): i for i, h in enumerate(head)}
    why_col = old.get("Why this score")
    formulas = ws.get_all_values(value_render_option="FORMULA") if why_col is not None else []
    rows = []
    for n, row in enumerate(values[1:], start=1):
        get = lambda name: row[old[name]] if name in old and old[name] < len(row) else ""  # noqa: E731
        why = get("Why this score")
        if why.startswith("#") and n < len(formulas) and why_col < len(formulas[n]):
            why = str(formulas[n][why_col]).lstrip("=")  # the text had been read as a formula
        why = "; ".join(part.strip().lstrip("+") for part in why.split(";"))
        new = [""] * len(JOBS_HEADER)
        for name in ("Score", "Label", "Company", "Location", "Type", "Source", "Posted", "Found",
                     "Status", "Link", "Key", "AI fit", "Work", "Salary", "AI note", "Degree asked"):
            new[J[name]] = safe(get(name))
        new[J["Title"]] = title_link(get("Title"), get("Link"))
        new[J["Country"]] = get("Country") or country(get("Location"))
        new[J["Why this score"]] = why
        try:
            new[J["Score"]] = int(float(new[J["Score"]]))
        except (TypeError, ValueError):
            pass
        rows.append(new)
    ws.clear()
    ws.resize(rows=max(len(rows) + 50, 200), cols=len(JOBS_HEADER))
    ws.update(values=[JOBS_HEADER] + rows, range_name="A1", value_input_option="USER_ENTERED")
    _style_jobs(book, ws)
    return ws, [[_plain(c) for c in r] for r in rows]


_LINK = re.compile(r'^=HYPERLINK\("(?:[^"]|"")*","((?:[^"]|"")*)"\)$', re.S)


def _plain(cell):
    """Displayed text of a title cell written as a HYPERLINK formula."""
    match = _LINK.match(cell) if isinstance(cell, str) else None
    return match.group(1).replace('""', '"') if match else cell


def _style_jobs(book, ws):
    sid, n = ws.id, len(JOBS_HEADER)
    col = lambda name: {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": J[name],  # noqa: E731
                        "endColumnIndex": J[name] + 1}
    green, yellow, red = ({"red": 0.72, "green": 0.88, "blue": 0.75}, {"red": 1, "green": 0.95, "blue": 0.76},
                          {"red": 0.96, "green": 0.8, "blue": 0.8})
    gradient = lambda name: {"addConditionalFormatRule": {"index": 0, "rule": {  # noqa: E731
        "ranges": [col(name)], "gradientRule": {
            "minpoint": {"colorStyle": {"rgbColor": red}, "type": "NUMBER", "value": "20"},
            "midpoint": {"colorStyle": {"rgbColor": yellow}, "type": "NUMBER", "value": "50"},
            "maxpoint": {"colorStyle": {"rgbColor": green}, "type": "NUMBER", "value": "80"}}}}}
    status = chr(ord("A") + J["Status"])
    status_rule = lambda word, colour: {"addConditionalFormatRule": {"index": 0, "rule": {  # noqa: E731
        "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": n}],
        "booleanRule": {"condition": {"type": "CUSTOM_FORMULA",
                                      "values": [{"userEnteredValue": f'=${status}2="{word}"'}]},
                        "format": {"backgroundColorStyle": {"rgbColor": colour}}}}}}
    meta = book.fetch_sheet_metadata()
    mine = next(s for s in meta["sheets"] if s["properties"]["sheetId"] == sid)
    requests_ = [{"deleteConditionalFormatRule": {"sheetId": sid, "index": 0}}
                 for _ in mine.get("conditionalFormats", [])]
    requests_ += [
        {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {
            "frozenRowCount": 1, "frozenColumnCount": J["Title"] + 1}},
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}},
        {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColorStyle": {
                            "rgbColor": {"red": 0.9, "green": 0.93, "blue": 0.98}}}},
                        "fields": "userEnteredFormat.textFormat.bold,userEnteredFormat.backgroundColorStyle"}},
        {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 1},
                        "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP", "verticalAlignment": "MIDDLE"}},
                        "fields": "userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment"}},
        gradient("Score"), gradient("AI fit"),
        status_rule("Applied", green), status_rule("Skip", red),
        status_rule("Closed", {"red": 0.85, "green": 0.85, "blue": 0.85}),
        {"setBasicFilter": {"filter": {"range": {"sheetId": sid, "startRowIndex": 0,
                                                 "startColumnIndex": 0, "endColumnIndex": n},
                                       # keep the user's sort (column order of the sorted ones is unchanged)
                                       **({"sortSpecs": mine["basicFilter"]["sortSpecs"]}
                                          if mine.get("basicFilter", {}).get("sortSpecs") else {})}}},
    ]
    requests_ += [{"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
        "properties": {"pixelSize": width}, "fields": "pixelSize"}} for i, width in enumerate(JOBS_WIDTHS)]
    book.batch_update({"requests": requests_})


def known_keys(book, key_fn, rerate=False):
    """Keys and links of everything already applied to or already listed, plus
    the keys of listed jobs that are still New and have no AI fit yet."""
    keys, links, waiting = set(), set(), set()
    try:
        rows = book.worksheet(APPLICATIONS).get_all_values()
        if rows:
            head = [h.strip().lower() for h in rows[0]]
            c, t, u = head.index("company name"), head.index("job title"), head.index("job url")
            for row in rows[1:]:
                row += [""] * (len(head) - len(row))
                keys.add(key_fn(row[c], row[t]))
                keys.add(key_fn(row[c], base_title(row[t])))
                if row[u].strip():
                    links.add(row[u].strip())
    except (gspread.WorksheetNotFound, ValueError):
        pass
    _, rows = _jobs_tab(book)
    for row in rows:
        row += [""] * (len(JOBS_HEADER) - len(row))
        key = row[J["Key"]] or key_fn(row[J["Company"]], row[J["Title"]])
        keys.add(key)
        keys.add(key_fn(row[J["Company"]], base_title(row[J["Title"]])))
        links.add(row[J["Link"]])
        unrated = not str(row[J["AI fit"]]).strip() and not str(row[J["AI note"]]).strip()
        if (unrated or rerate) and str(row[J["Status"]]).strip() in ("", "New"):
            waiting.add(key)
    try:  # jobs moved out of the Jobs tab stay known, so they are not listed again
        for row in book.worksheet(OLD_JOBS).get_all_values()[1:]:
            row += [""] * (4 - len(row))
            keys.add(row[0])
            links.add(row[3])
    except gspread.WorksheetNotFound:
        pass
    links.discard("")
    return keys, links, waiting


def add_jobs(book, rows):
    """Insert new rows under the header, best score first."""
    ws, _ = _jobs_tab(book)
    if rows:
        out = []
        for row in rows:
            row = [safe(c) for c in row]
            row[J["Title"]] = title_link(str(row[J["Title"]]).lstrip("'"), row[J["Link"]])
            out.append(row)
        ws.insert_rows(out, row=2, value_input_option="USER_ENTERED")
    # Status dropdown on the whole column (cheap to re-apply, keeps new rows covered)
    book.batch_update({"requests": [{"setDataValidation": {
        "range": {"sheetId": ws.id, "startRowIndex": 1, "startColumnIndex": J["Status"],
                  "endColumnIndex": J["Status"] + 1},
        "rule": {"condition": {"type": "ONE_OF_LIST",
                               "values": [{"userEnteredValue": s} for s in STATUSES]},
                 "showCustomUi": True, "strict": False}}}]})


def tidy_jobs(book, today, keep_days, open_keys, readable):
    """Housekeeping on the Jobs tab, before today's jobs are added.

    1. A job from a company feed that is no longer in that feed gets Status "Closed"
       (only when the company's feed was read fine today: `readable`).
    2. Jobs still New or Closed that were found more than `keep_days` days ago move
       to the Old jobs tab. Applied and Skip rows always stay.
    Returns (closed, moved)."""
    from datetime import date
    ws, rows = _jobs_tab(book)
    closed, keep, old = [], [], []
    for n, row in enumerate(rows, start=2):
        row += [""] * (len(JOBS_HEADER) - len(row))
        status = str(row[J["Status"]]).strip()
        if status in ("", "New") and str(row[J["Source"]]).startswith("Company list") \
                and row[J["Company"]] in readable and row[J["Key"]] and row[J["Key"]] not in open_keys:
            row[J["Status"]] = status = "Closed"
            closed.append(n)
        try:
            age = today.toordinal() - date.fromisoformat(str(row[J["Found"]])[:10]).toordinal()
        except ValueError:
            age = 0
        (old if status in ("", "New", "Closed") and age > keep_days else keep).append(row)
    if old:
        archive, _ = _tab(book, OLD_JOBS, OLD_HEADER)
        archive.append_rows([[r[J["Key"]], r[J["Company"]], r[J["Title"]], r[J["Link"]], r[J["Found"]],
                              r[J["Status"]], today.isoformat()] for r in old], value_input_option="RAW")
        out = []
        for r in keep:
            r = [safe(c) for c in r]
            r[J["Title"]] = title_link(str(r[J["Title"]]).lstrip("'"), r[J["Link"]])
            out.append(r)
        if out:  # write the shorter list first, then blank what is left below it
            ws.update(values=out, range_name="A2", value_input_option="USER_ENTERED")
        last = chr(ord("A") + len(JOBS_HEADER) - 1)
        ws.batch_clear([f"A{len(out) + 2}:{last}{len(rows) + 1}"])
    elif closed:
        letter = chr(ord("A") + J["Status"])
        ws.batch_update([{"range": f"{letter}{n}", "values": [["Closed"]]} for n in closed])
    return len(closed), len(old)


def write_best(book, min_fit, days):
    """The Best tab: a live view of the Jobs tab. Jobs found in the last `days` days
    with an AI fit of `min_fit` or more that are not Applied, Skip or Closed and that the AI did not call ineligible, best first."""
    ws, _ = _tab(book, BEST, BEST_COLUMNS)
    col = lambda name: f"{JOBS}!{chr(ord('A') + J[name])}2:{chr(ord('A') + J[name])}"  # noqa: E731
    fit, found, status = col("AI fit"), col("Found"), col("Status")
    cond = (f"ISNUMBER({fit})*({fit}>={int(min_fit)})*ISNUMBER({found})*({found}>=TODAY()-{int(days)})"
            f'*({status}<>"Applied")*({status}<>"Skip")*({status}<>"Closed")'
            f'*(LEFT({col("AI note")},10)<>"Ineligible")')
    pick = lambda name: f"INDEX(SORT(FILTER({{{col(name)},{fit}}},{cond}),2,FALSE),,1)"  # noqa: E731
    formulas = []
    for name in BEST_COLUMNS:
        if name == "Title":
            formulas.append(f'=IFERROR(ARRAYFORMULA(HYPERLINK({pick("Link")},{pick("Title")})),'
                            f'"No job matches right now")')
        else:
            formulas.append(f'=IFERROR(ARRAYFORMULA({pick(name)}),"")')
    note = (f"This tab fills itself: jobs found in the last {int(days)} days with AI fit {int(min_fit)}+, "
            "best first. Mark Applied or Skip in the Jobs tab. Change the numbers in Settings "
            "(best_min_ai_fit, best_days).")
    ws.batch_clear(["A2:N"])
    ws.update(values=[BEST_COLUMNS + [note], formulas], range_name="A1", value_input_option="USER_ENTERED")
    sid = ws.id
    requests_ = [
        {"updateSheetProperties": {"properties": {"sheetId": sid, "index": 1, "gridProperties": {
            "frozenRowCount": 1, "frozenColumnCount": 2}},
            "fields": "index,gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}},
        {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColorStyle": {
                            "rgbColor": {"red": 0.85, "green": 0.94, "blue": 0.87}}}},
                        "fields": "userEnteredFormat.textFormat.bold,userEnteredFormat.backgroundColorStyle"}},
        {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 1},
                        "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP"}},
                        "fields": "userEnteredFormat.wrapStrategy"}},
        {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 1,
                                  "startColumnIndex": BEST_COLUMNS.index("Posted"),
                                  "endColumnIndex": BEST_COLUMNS.index("Found") + 1},
                        "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}}},
                        "fields": "userEnteredFormat.numberFormat"}},
    ]
    requests_ += [{"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
        "properties": {"pixelSize": width}, "fields": "pixelSize"}} for i, width in enumerate(BEST_WIDTHS)]
    meta = book.fetch_sheet_metadata()
    mine = next(s for s in meta["sheets"] if s["properties"]["sheetId"] == sid)
    if "basicFilter" not in mine:  # filter buttons on every header; a filter already set is left as it is
        requests_.append({"setBasicFilter": {"filter": {"range": {
            "sheetId": sid, "startRowIndex": 0, "startColumnIndex": 0, "endColumnIndex": len(BEST_COLUMNS)}}}})
    book.batch_update({"requests": requests_})


def update_ai(book, results):
    """results: {key: {"fit", "note", "salary", "work"}} for jobs already in the Jobs tab."""
    if not results:
        return 0
    ws, rows = _jobs_tab(book)
    letter = lambda name: chr(ord("A") + J[name])  # noqa: E731
    updates = []
    for n, row in enumerate(rows, start=2):
        row += [""] * (len(JOBS_HEADER) - len(row))
        found = results.get(row[J["Key"]])
        if not found:
            continue
        updates.append({"range": f"{letter('AI fit')}{n}", "values": [[found["fit"]]]})
        updates.append({"range": f"{letter('AI note')}{n}", "values": [[safe(found["note"])]]})
        if found.get("salary") and not row[J["Salary"]]:
            updates.append({"range": f"{letter('Salary')}{n}", "values": [[safe(found["salary"])]]})
        if found.get("degree") and not row[J["Degree asked"]]:
            updates.append({"range": f"{letter('Degree asked')}{n}", "values": [["Yes"]]})
        if found.get("work") and not row[J["Work"]]:
            updates.append({"range": f"{letter('Work')}{n}", "values": [[found["work"]]]})
    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")
    return len(updates)


def write_filtered(book, removed, today, keep_days):
    """Rewrite the Filtered out tab: everything removed that was seen in the
    last `keep_days` days, keeping the date each job was first removed."""
    ws, _ = _tab(book, FILTERED, FILTERED_HEADER)
    old = {}
    for row in ws.get_all_values()[1:]:
        row += [""] * (len(FILTERED_HEADER) - len(row))
        old[row[8]] = row
    for key, row in removed.items():
        if key in old:
            row[0] = old[key][0] or row[0]
        old[key] = row
    cutoff = today.toordinal() - keep_days
    keep = []
    for row in old.values():
        try:
            from datetime import date
            if date.fromisoformat(row[7]).toordinal() >= cutoff:
                keep.append(row)
        except ValueError:
            continue
    keep.sort(key=lambda r: (r[0], r[1]), reverse=True)
    ws.batch_clear(["A2:I"])
    if keep:
        if ws.row_count < len(keep) + 1:
            ws.add_rows(len(keep) + 1 - ws.row_count)
        ws.update(values=keep, range_name="A2", value_input_option="RAW")
    return len(keep)


def load_companies(book, extra=()):
    """Rows of the Scout Companies tab. On first use the tab is filled from the
    old Companies tab plus the extra list kept in the repository."""
    ws, created = _tab(book, COMPANIES, COMPANIES_HEADER)
    rows = [r + [""] * (8 - len(r)) for r in ws.get_all_values()[1:]]
    have = {r[0].strip().lower() for r in rows}
    new = []
    if created or not rows:
        try:
            old = book.worksheet(OLD_COMPANIES).get_all_values()
            head = [h.strip().lower() for h in old[0]]
            n, w, c = head.index("company name"), head.index("website / domain"), head.index("careers url")
            for r in old[1:]:
                r += [""] * (len(head) - len(r))
                clean = [("" if "not provided" in x.lower() else x.strip()) for x in (r[n], r[w], r[c])]
                if clean[0] and clean[0].lower() not in have:
                    have.add(clean[0].lower())
                    new.append(clean + [""] * 5)
        except (gspread.WorksheetNotFound, ValueError, IndexError):
            pass
    for name, website in extra:  # companies added in the repository's list
        if name.lower() not in have:
            have.add(name.lower())
            new.append([name, website, "", "", "", "", "", ""])
    if new:
        ws.append_rows(new, value_input_option="RAW")
        rows += new
    return ws, rows


def scouted(status):
    """Yes when the company's jobs were read on the last check."""
    status = str(status)
    return "Yes" if status.startswith("OK") and "failed" not in status else "No"


def save_companies(ws, rows):
    if not rows:
        return
    if ws.col_count < len(COMPANIES_HEADER):
        ws.add_cols(len(COMPANIES_HEADER) - ws.col_count)
    ws.update(values=[COMPANIES_HEADER[8:]], range_name="I1")  # column J (Why added) is never overwritten
    ws.update(values=[r[:8] + [scouted(r[5])] for r in rows], range_name="A2", value_input_option="RAW")
    _style_companies(ws)


def _style_companies(ws):
    """Filter buttons (Company to Why added), frozen header and company column, Scouted now? in green or grey."""
    sid = ws.id
    meta = ws.spreadsheet.fetch_sheet_metadata()
    mine = next(s for s in meta["sheets"] if s["properties"]["sheetId"] == sid)
    flag = {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 8, "endColumnIndex": 9}
    rule = lambda word, colour: {"addConditionalFormatRule": {"index": 0, "rule": {  # noqa: E731
        "ranges": [flag], "booleanRule": {
            "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": word}]},
            "format": {"backgroundColorStyle": {"rgbColor": colour}}}}}}
    requests_ = [{"deleteConditionalFormatRule": {"sheetId": sid, "index": 0}}
                 for _ in mine.get("conditionalFormats", [])]
    requests_ += [
        {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {
            "frozenRowCount": 1, "frozenColumnCount": 1}},
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}},
        {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat.textFormat.bold"}},
        rule("Yes", {"red": 0.72, "green": 0.88, "blue": 0.75}),
        rule("No", {"red": 0.9, "green": 0.9, "blue": 0.9}),
    ]
    if "basicFilter" not in mine:  # a filter the user has set is left as it is
        requests_.append({"setBasicFilter": {"filter": {"range": {
            "sheetId": sid, "startRowIndex": 0, "startColumnIndex": 0, "endColumnIndex": 10}}}})
    ws.spreadsheet.batch_update({"requests": requests_})
