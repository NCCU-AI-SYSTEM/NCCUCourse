"""Fetch 1142 course enrollment results from subRemainUrl pages."""

import sqlite3
import sys
import time

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


def parse_remain_page(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    info: dict = {}
    for t in tables:
        rows = t.find_all("tr")
        for r in rows:
            cells = r.find_all(["td", "th"])
            texts = [c.text.strip() for c in cells]
            if len(texts) >= 2:
                if "科目代號" in texts[0]:
                    info["subNum"] = texts[1]
                elif "科目名稱" in texts[0]:
                    info["name"] = texts[1]
                elif "授課教師" in texts[0]:
                    info["teacher"] = texts[1]
                elif "上課時間" in texts[0]:
                    info["time"] = texts[1]
                elif "限制人數" in texts[0]:
                    info["studentLimit"] = int(texts[-1]) if texts[-1].lstrip("-").isdigit() else 0
                elif "選課人數" in texts[0]:
                    info["studentCount"] = int(texts[-1]) if texts[-1].lstrip("-").isdigit() else 0
                elif "餘額" in texts[0]:
                    info["lastEnroll"] = int(texts[-1]) if texts[-1].lstrip("-").isdigit() else 0

    if "studentLimit" in info and "studentCount" in info:
        return info
    return None


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else "1142.db"
    conn = sqlite3.connect(db_path)

    rows = conn.execute(
        "SELECT DISTINCT id, subRemainUrl, name, teacher, time "
        "FROM COURSE WHERE y='114' AND s='2' AND subRemainUrl IS NOT NULL AND subRemainUrl != ''"
    ).fetchall()

    existing = {r[0] for r in conn.execute("SELECT courseId FROM RESULT WHERE yearsem='1142'").fetchall()}

    to_fetch = [(r[0], r[1], r[2], r[3], r[4]) for r in rows if r[0] not in existing]
    print(f"Total: {len(rows)}, Already exists: {len(existing)}, To fetch: {len(to_fetch)}")

    success = 0
    errors = 0

    for course_id, url, name, teacher, course_time in tqdm(to_fetch, desc="Fetching remain"):
        try:
            time.sleep(0.15)
            res = requests.get(url, timeout=15)
            res.raise_for_status()
            info = parse_remain_page(res.text)
            if info:
                conn.execute(
                    "INSERT OR IGNORE INTO RESULT (courseId, yearsem, name, teacher, time, studentLimit, studentCount, lastEnroll) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        course_id,
                        "1142",
                        info.get("name", name),
                        info.get("teacher", teacher),
                        info.get("time", course_time),
                        info.get("studentLimit", 0),
                        info.get("studentCount", 0),
                        info.get("lastEnroll", 0),
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
    print(f"\nDone! Success: {success}, Errors: {errors}")


if __name__ == "__main__":
    main()
