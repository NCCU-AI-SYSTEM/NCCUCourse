"""Backfill syllabus sections for courses that were crawled without them."""

import config
import sys
import time

from tqdm import tqdm

from DB import DB
from fetchDescription import SECTION_COLUMNS, fetchDescription


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else config.DEFAULT_DB
    db = DB(db_path)
    conn = db.con

    # Databases predating the syllabus fields lack the columns queried below.
    db.ensureCourseColumns(SECTION_COLUMNS.values())

    rows = conn.execute(
        "SELECT DISTINCT id FROM COURSE "
        "WHERE y=? AND s=? "
        "AND (schedule IS NULL OR schedule = '') "
        "AND teaSchmUrl IS NOT NULL AND teaSchmUrl != ''",
        (config.YEAR, config.SEM),
    ).fetchall()

    print(f"Courses to backfill: {len(rows)}")

    success = 0
    errors = 0

    for (course_id,) in tqdm(rows, desc="Backfilling syllabus"):
        try:
            time.sleep(0.15)
            detail = fetchDescription(course_id)
            sections = {k: v for k, v in detail["sections"].items() if v}

            if sections:
                db.ensureCourseColumns(sections.keys())
                columns = list(sections.keys())
                conn.execute(
                    "UPDATE COURSE SET {} WHERE id=?".format(
                        ", ".join('"{}"=?'.format(x) for x in columns)
                    ),
                    [sections[x] for x in columns] + [course_id],
                )
                conn.commit()
                success += 1
            else:
                errors += 1
        except Exception as e:
            errors += 1
            print(f"\nError {course_id}: {e}")

    conn.close()
    print(f"\nDone! Success: {success}, Skipped/Errors: {errors}")


if __name__ == "__main__":
    main()
