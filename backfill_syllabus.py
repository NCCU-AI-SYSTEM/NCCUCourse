"""Backfill schedule/evaluation/textbook/teaching_approach/ai_policy for existing 1142 courses."""

import sqlite3
import sys
import time

from tqdm import tqdm

from fetchDescription import fetchDescription


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else "1142.db"
    conn = sqlite3.connect(db_path)

    rows = conn.execute(
        "SELECT DISTINCT id FROM COURSE "
        "WHERE y='114' AND s='2' "
        "AND (schedule IS NULL OR schedule = '') "
        "AND teaSchmUrl IS NOT NULL AND teaSchmUrl != ''"
    ).fetchall()

    print(f"Courses to backfill: {len(rows)}")

    success = 0
    errors = 0

    for (course_id,) in tqdm(rows, desc="Backfilling syllabus"):
        try:
            time.sleep(0.15)
            detail = fetchDescription(course_id)

            if any([detail["schedule"], detail["evaluation"], detail["textbook"],
                    detail["teaching_approach"], detail["ai_policy"]]):
                conn.execute(
                    "UPDATE COURSE SET schedule=?, evaluation=?, textbook=?, "
                    "teaching_approach=?, ai_policy=? WHERE id=?",
                    (
                        detail["schedule"],
                        detail["evaluation"],
                        detail["textbook"],
                        detail["teaching_approach"],
                        detail["ai_policy"],
                        course_id,
                    ),
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
