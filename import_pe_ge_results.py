"""Import PE & General Education enrollment data from registrar PDFs into RESULT table."""

import sqlite3
import sys

import pdfplumber


SEMESTERS = ["1122", "1131", "1132", "1141"]


def parse_pdf(path: str) -> list[dict]:
    results = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue
            for row in table:
                if not row or not row[0] or not row[0][0].isdigit():
                    continue
                if len(row) < 6:
                    continue
                course_code = row[0].strip()
                name = row[1].strip() if row[1] else ""
                time_str = row[2].strip() if row[2] else ""
                try:
                    limit = int(row[3]) if row[3] and row[3].strip().lstrip("-").isdigit() else 0
                except ValueError:
                    limit = 0
                try:
                    count = int(row[4]) if row[4] and row[4].strip().lstrip("-").isdigit() else 0
                except ValueError:
                    count = 0
                last_enroll = limit - count
                results.append({
                    "subNum": course_code,
                    "name": name,
                    "time": time_str,
                    "studentLimit": limit,
                    "studentCount": count,
                    "lastEnroll": last_enroll,
                })
    return results


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else "1142.db"
    conn = sqlite3.connect(db_path)

    total_inserted = 0
    total_skipped = 0

    for sem in SEMESTERS:
        pdf_path = f"data/{sem}_pe_ge.pdf"
        try:
            courses = parse_pdf(pdf_path)
        except FileNotFoundError:
            print(f"{sem}: PDF not found at {pdf_path}, skipping")
            continue

        inserted = 0
        for c in courses:
            course_id = sem + c["subNum"]
            teacher = ""
            cur = conn.execute(
                "SELECT teacher FROM COURSE WHERE id=? LIMIT 1", (course_id,)
            )
            row = cur.fetchone()
            if row:
                teacher = row[0] or ""

            conn.execute(
                "INSERT OR IGNORE INTO RESULT "
                "(courseId, yearsem, name, teacher, time, studentLimit, studentCount, lastEnroll) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    course_id,
                    sem,
                    c["name"],
                    teacher,
                    c["time"],
                    c["studentLimit"],
                    c["studentCount"],
                    c["lastEnroll"],
                ),
            )
            inserted += 1

        conn.commit()
        total_inserted += inserted
        print(f"{sem}: {inserted} courses imported from PDF")

    total_skipped = 0
    for sem in SEMESTERS:
        cur = conn.execute("SELECT COUNT(*) FROM RESULT WHERE yearsem=?", (sem,))
        count = cur.fetchone()[0]
        print(f"  RESULT {sem}: {count} rows")

    conn.close()
    print(f"\nDone! Total imported: {total_inserted}")


if __name__ == "__main__":
    main()
