"""Work out which ATS each curated company uses and write it to the sheet.

    python -m scout.detect              # fills the Scout Companies tab (new rows only)
    python -m scout.detect --all        # re-check every company
    python -m scout.detect --retry      # new rows, plus every company that has no readable feed yet
    python -m scout.detect --dry-run    # no sheet: checks data/extra_companies.csv, prints the result
"""
import argparse
import csv
import os
import sys
from collections import Counter
from datetime import date

from . import profile as profile_mod
from .ats import detect_many

# a profile's own companies.csv replaces the default list
EXTRA = (profile_mod.path("companies.csv", default_dir=None)
         or os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "extra_companies.csv"))


def extra_companies():
    with open(EXTRA, encoding="utf-8") as handle:
        return [(r["Company"].strip(), r["Website"].strip()) for r in csv.DictReader(handle)]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--retry", action="store_true")
    args = parser.parse_args(argv)
    today = date.today().isoformat()

    if args.dry_run:
        rows = [[n, w, "", "", "", "", "", ""] for n, w in extra_companies()]
        ws = None
    else:
        from . import sheet
        ws, rows = sheet.load_companies(sheet.open_book(), extra_companies())

    todo = [i for i, r in enumerate(rows) if r[0].strip() and
            (args.all or not r[5].strip() or (args.retry and not str(r[5]).startswith("OK")))]
    results = detect_many([(rows[i][0], rows[i][1], rows[i][2]) for i in todo])
    for i, (ats, board, status, count) in zip(todo, results):
        rows[i][3:8] = [ats, board, status, count, today]

    if ws is not None:
        from . import sheet
        sheet.save_companies(ws, rows)

    done = [rows[i] for i in todo]
    ok = [r for r in done if str(r[5]).startswith("OK")]
    lines = ["## Company check", "",
             f"- {len(done)} companies checked, **{len(ok)} have a readable feed** "
             f"({sum(int(r[6] or 0) for r in ok)} open jobs in total)",
             f"- By ATS: {dict(Counter(r[3] for r in ok))}",
             f"- No feed: {len(done) - len(ok)}"]
    text = "\n".join(lines)
    print(text)
    if args.dry_run:
        for r in done:
            print(" | ".join(str(x) for x in (r[0], r[3], r[4], r[5], r[6])))
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
