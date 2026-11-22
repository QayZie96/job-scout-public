"""Job Scout: collect -> remove deal-breakers -> rate -> write to the sheet.

    python -m scout.run             # real run (needs SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON)
    python -m scout.run --dry-run   # no sheet; writes out/jobs.csv and out/filtered.csv
"""
import argparse
import csv
import os
import re
import sys
import unicodedata
from datetime import date

from . import settings as settings_mod
from .rate import rate
from .extract import arrangement, find_salary, country
from .screen import screen
from .sheet import J, JOBS_HEADER
from .sources import collect
from .text import base_title


def key_of(company, title):
    def norm(text):
        text = unicodedata.normalize("NFKD", str(text or "").lower())
        text = re.sub(r"\b(?:s\.?a\.?|ltd|gmbh|inc|llc|ae|a\.e\.|aebe|abee|epe|ike|b\.v\.|group|limited|"
                      r"αε|α\.ε\.|αεβε|αβεε|επε|ικε|οε|ομιλος)\b", " ", text)
        return re.sub(r"[^a-z0-9α-ω]+", " ", text).strip()
    return f"{norm(company)}|{norm(title)}"


def process(jobs, settings, known=(set(), set()), today=None, waiting=()):
    """Returns (job_rows, removed_rows_by_key, stats, ai_queue).

    ai_queue lists the jobs worth an AI check, best score first:
    (key, job, row or None). `row` is the new sheet row to fill in; it is None for
    a job that is already in the Jobs tab and still has no AI fit (`waiting`)."""
    today = today or date.today()
    keys, links, waiting = set(known[0]), set(known[1]), set(waiting)
    passed, removed, stats = [], {}, {"duplicates": 0, "already_known": 0}
    seen, queue = set(), []
    for job in jobs:
        key = key_of(job["company"], job["title"])
        base = key_of(job["company"], base_title(job["title"]))
        if key in seen or base in seen:  # also the same job posted for several places
            stats["duplicates"] += 1
            continue
        seen.update((key, base))
        is_known = key in keys or job["url"] in links or base in keys
        if is_known:
            stats["already_known"] += 1
            if key not in waiting:
                continue
        bucket, reason = screen(job, settings)
        if reason:
            if not is_known:
                removed[key] = [today.isoformat(), reason, job["title"], job["company"],
                                job["location"], job["source"], job["url"], today.isoformat(), key]
            continue
        score, label, why = rate(job, bucket, settings, today)
        if is_known:
            queue.append((score, key, job, None))
            continue
        text = f"{job['title']}\n{job.get('description') or ''}"
        row = [""] * len(JOBS_HEADER)
        for name, value in (("Score", score), ("Label", label), ("Title", job["title"]),
                            ("Company", job["company"]), ("Location", job["location"]),
                            ("Country", country(job["location"])),
                            ("Work", arrangement(job)), ("Type", bucket),
                            ("Salary", job.get("salary") or find_salary(text)),
                            ("Source", job["source"]), ("Posted", job["posted"]),
                            ("Found", today.isoformat()), ("Status", "New"),
                            ("Why this score", why), ("Link", job["url"]), ("Key", key),
                            ("Degree asked", "Yes" if any(k == "degree" for k, _ in job.get("flags") or []) else "")):
            row[J[name]] = value
        passed.append(row)
        queue.append((score, key, job, row))
    passed.sort(key=lambda r: r[J["Score"]], reverse=True)
    # new jobs before the backlog, best score first
    queue.sort(key=lambda q: (q[3] is None, -q[0]))
    low = [(k, j, r) for s, k, j, r in queue if s < settings["ai_min_score"]]
    queue = [(k, j, r) for s, k, j, r in queue if s >= settings["ai_min_score"]]
    stats.update(new=len(passed), removed=len(removed),
                 strong=sum(1 for r in passed if r[J["Score"]] >= 70),
                 good=sum(1 for r in passed if 50 <= r[J["Score"]] < 70))
    return passed, removed, stats, queue, low


NOT_READ = "Title check: looks like another kind of job, so the ad was not read in full."


def ai_check(queue, settings, low=()):
    """Fill AI fit, note, salary and work on new rows; return results for listed jobs.

    `low` are jobs under the score line. The AI first looks at their titles only and
    the ones it picks join the end of the queue; the others get a note saying so."""
    from . import ai
    if not ai.enabled(settings):
        return {}, "AI check: off (no GEMINI_API_KEY secret, or ai_enabled is not yes)"
    listed, title_info = {}, ""
    if low and int(settings["ai_title_check_per_run"]) > 0:
        picked, seen, title_info = ai.title_check([j for _, j, _ in low], settings)
        for position in sorted(seen):
            key, _, row = low[position]
            if position in picked:
                queue = queue + [low[position]]
            elif row is None:
                listed[key] = {"fit": "", "note": NOT_READ, "salary": "", "work": ""}
            else:
                row[J["AI note"]] = NOT_READ
    queue = queue[:int(settings["ai_max_jobs_per_run"])]
    results, info = ai.evaluate([j for _, j, _ in queue], settings)
    info += f"\n\n{title_info}" if title_info else ""
    for position, found in results.items():
        key, _, row = queue[position]
        if row is None:
            listed[key] = found
            continue
        row[J["AI fit"]], row[J["AI note"]] = found["fit"], found["note"]
        row[J["Salary"]] = row[J["Salary"]] or found["salary"]
        row[J["Work"]] = row[J["Work"]] or found["work"]
        if found.get("degree"):
            row[J["Degree asked"]] = "Yes"
    return listed, info


def summary(stats, counts, errors, rows):
    lines = ["## Job Scout run", "",
             f"- **{stats['new']} new jobs** ({stats['strong']} rated 70+, {stats['good']} rated 50-69)",
             f"- {stats['removed']} removed by the filters, {stats['already_known']} already in the sheet, "
             f"{stats['duplicates']} duplicates across sources", "", "| Source | Ads read |", "| --- | --- |"]
    lines += [f"| {name} | {count}{' (FAILED: ' + errors[name] + ')' if name in errors else ''} |"
              for name, count in counts.items()]
    lines += ["", "Top of today's list:", ""]
    lines += [f"- {r[J['Score']]} · {r[J['Title']]} · {r[J['Company']]} · {r[J['Type']]}"
              + (f" · AI {r[J['AI fit']]}" if r[J['AI fit']] != "" else "") for r in rows[:15]]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", help="comma-separated source names")
    parser.add_argument("--rerate", action="store_true",
                        help="ask the AI again about every job still New, not only the unrated ones")
    args = parser.parse_args(argv)
    today = date.today()

    book = None
    if args.dry_run:
        settings, known, waiting = settings_mod.load(), (set(), set()), set()
    else:
        from . import sheet
        book = sheet.open_book()
        settings = sheet.load_settings(book)
        *known, waiting = sheet.known_keys(book, key_of, rerate=args.rerate)
        if args.rerate:  # a one-off catch-up: bigger batches, a higher cap
            settings.update(ai_max_jobs_per_run=700, ai_jobs_per_call=10, ai_calls_per_minute=15)

    jobs, counts, errors = collect(settings, only=args.only.split(",") if args.only else None)

    # curated companies, through their ATS feeds
    from . import ats
    if args.dry_run:
        from .detect import extra_companies
        sample = extra_companies()[:40]
        found = ats.detect_many([(n, w, "") for n, w in sample])
        boards = [(n, a, b) for (n, _), (a, b, status, _) in zip(sample, found) if status.startswith("OK")]
        company_ws = None
    else:
        company_ws, company_rows = sheet.load_companies(book)
        boards = [(r[0], r[3], r[4]) for r in company_rows if str(r[5]).startswith("OK") and r[3] in ats.FETCHERS]
    company_jobs, company_counts, company_errors = ats.fetch_many(boards)
    jobs = company_jobs + jobs  # the company's own ad wins over a job board's copy
    counts[f"Company list ({len(boards)} companies)"] = len(company_jobs)
    if company_errors:
        errors[f"Company list ({len(boards)} companies)"] = f"{len(company_errors)} companies failed: " + ", ".join(list(company_errors)[:8])
    if company_ws is not None:
        for r in company_rows:
            if r[0] in company_counts:
                r[6] = company_counts[r[0]]
                r[7] = today.isoformat()
                if r[0] in company_errors:
                    r[5] = "OK (last read failed)"
                elif str(r[5]).startswith("OK (last read failed)"):
                    r[5] = "OK"
        sheet.save_companies(company_ws, company_rows)
    rows, removed, stats, queue, low = process(jobs, settings, known, today, waiting)
    listed, ai_info = ai_check(queue, settings, low)

    if args.dry_run:
        os.makedirs("out", exist_ok=True)
        from .sheet import FILTERED_HEADER
        for name, header, data in (("jobs", JOBS_HEADER, rows),
                                   ("filtered", FILTERED_HEADER, list(removed.values()))):
            with open(f"out/{name}.csv", "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(header)
                writer.writerows(data)
        # the log is the easiest place to review a dry run
        from collections import Counter
        print("\n=== PASSED (" + " | ".join(JOBS_HEADER[:11]) + ") ===")
        for r in rows[:150]:
            print(" | ".join(str(x) for x in r[:11]))
        print(f"... {max(0, len(rows) - 150)} more")
        print("\n=== LABELS ===", Counter(r[J["Label"]] for r in rows).most_common())
        print("=== TYPES ===", Counter(r[J["Type"]] for r in rows).most_common())
        print("=== SOURCES (passed) ===", Counter(r[J["Source"]] for r in rows).most_common())
        reasons = Counter(re.sub(r"[:(“].*", "", r[1]).strip() for r in removed.values())
        print("=== WORK ===", Counter(r[J["Work"]] for r in rows).most_common())
        print("=== WITH SALARY ===", sum(1 for r in rows if r[J["Salary"]]), "of", len(rows))
        for r in [r for r in rows if r[J["Salary"]]][:40]:
            print("   salary:", r[J["Salary"]], "|", r[J["Title"]], "|", r[J["Source"]])
        print("\n=== REMOVED, by reason ===", reasons.most_common())
        shown = Counter()
        for r in removed.values():
            group = re.sub(r"[:(“].*", "", r[1]).strip()
            if shown[group] < 12:
                shown[group] += 1
                print(" | ".join(str(x) for x in r[1:6]))
    else:
        open_keys = {key_of(j["company"], j["title"]) for j in company_jobs}
        readable = {c for c, n in company_counts.items()  # very long feeds are cut off, so not trusted here
                    if 0 < n < 450 and c not in company_errors}
        closed, moved = sheet.tidy_jobs(book, today, settings["jobs_keep_days"], open_keys, readable)
        tidy_info = f"Housekeeping: {closed} jobs marked Closed, {moved} old jobs moved to the Old jobs tab"
        sheet.add_jobs(book, rows)
        sheet.update_ai(book, listed)
        sheet.write_filtered(book, removed, today, settings["filtered_out_days"])
        sheet.write_best(book, settings["best_min_ai_fit"], settings["best_days"])

    text = summary(stats, counts, errors, rows) + f"\n\n{ai_info}"
    if not args.dry_run:
        text += f"\n\n{tidy_info}"
    print(text)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    # fail loudly only if every source failed
    return 1 if counts and all(v == 0 for v in counts.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
