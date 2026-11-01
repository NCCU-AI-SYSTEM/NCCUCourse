"""Repair COURSE rows whose evaluation / ai_policy hold the course-title line.

The April 2026 crawl found sections by substring ('AI', '評量', 'Evaluation'
in the h2 text) and took the course-title h2, storing its "Course Name: ..."
sibling instead of the section. This re-fetches only those courses, finds the
section by its exact English heading (fetchDescription._sectionHeadings),
and writes the text in the format the rest of the column already uses:
per-block get_text(strip=True) joined with '|'.

Usage:
  uv run python repair_course_name_sections.py 1142.db [--write]
Without --write it only prints what would change. Back up the DB first.
"""

import argparse
import sqlite3
import time

from bs4 import BeautifulSoup

import fetchDescription as fd
import fetcher

COLUMNS = ("evaluation", "ai_policy")
BAD_PREFIX = "Course Name:"
SLEEP = 0.15  # same pacing as backfill_syllabus.py


def affected_rows(con):
    rows = []
    for column in COLUMNS:
        for r in con.execute(
                'SELECT id, dp1, dp2, dp3, teaSchmUrl, "{0}" FROM COURSE WHERE "{0}" LIKE ?'.format(column),
                (BAD_PREFIX + "%",)):
            rows.append({"id": r[0], "key": r[1:4], "url": r[4], "column": column, "old": r[5]})
    return rows


def legacy_section(soup, column):
    heading = fd._sectionHeadings(soup).get(column)
    if heading is None:
        return None
    return "|".join(fd._sectionParts(heading, ""))


def fetch_sections(urls):
    pages = {}
    for course_id, url in sorted(urls.items()):
        time.sleep(SLEEP)
        try:
            res = fetcher.get(url.replace("https://", "http://"))
            res.raise_for_status()
            pages[course_id] = BeautifulSoup(res.content, "html.parser")
        except Exception as e:
            print("fetch failed", course_id, e)
    return pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    rows = affected_rows(con)
    print("affected rows:", len(rows), "distinct courses:", len({r["id"] for r in rows}))
    pages = fetch_sections({r["id"]: r["url"] for r in rows})

    updates, skipped = [], []
    for r in rows:
        soup = pages.get(r["id"])
        new = legacy_section(soup, r["column"]) if soup is not None else None
        if not new or new.startswith(BAD_PREFIX):
            skipped.append((r["id"], r["column"], "no section on page" if soup is not None else "fetch failed"))
            continue
        updates.append((r, new))
        print("{} {} {}\n  old: {!r}\n  new: {!r}".format(r["id"], "/".join(r["key"]), r["column"], r["old"], new[:160]))

    print("repairable:", len(updates), "skipped:", len(skipped))
    for s in skipped:
        print("  skipped", s)

    if args.write and updates:
        with con:
            for r, new in updates:
                con.execute(
                    'UPDATE COURSE SET "{}"=? WHERE id=? AND dp1=? AND dp2=? AND dp3=? AND "{}"=?'.format(
                        r["column"], r["column"]),
                    (new, r["id"], *r["key"], r["old"]))
        print("written:", len(updates))
    con.close()


if __name__ == "__main__":
    main()
