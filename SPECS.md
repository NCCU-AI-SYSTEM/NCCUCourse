# NCCU Course Crawler - Flag & API Specification

## Environment Variables (`.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `YEAR` | Academic year (last 3 digits) | `114` |
| `SEM` | Semester (1 or 2) | `2` |
| `STUDENTID` | NCCU student ID | `111xxxxxx` |
| `STUDENTPWD` | NCCU student password | `xxxxxx` |

**Computed:**
- `YEAR_SEM` = `YEAR` + `SEM` = `"1142"` (current semester)

---

## Flags Overview

### `--course`

Fetches course catalog/syllabus data from NCCU API.

| Aspect | Details |
|--------|---------|
| **API Endpoints** | 1. `https://qrysub.nccu.edu.tw/assets/api/unit.json` (department list)<br>2. `https://es.nccu.edu.tw/course/zh-TW/:sem={sem} :dp1={dp1} :dp2={dp2} :dp3={dp3}` (course list)<br>3. `http://es.nccu.edu.tw/course/zh-TW/{courseId}/` (course details)<br>4. `http://es.nccu.edu.tw/course/en/{courseId}/` (English details)<br>5. `{teaSchmUrl}` from course data (syllabus HTML) |
| **Semesters Affected** | `allSemesters` = `1011` to `1142` (`len(allSemesters)` = 39 semesters)<br>With `--fast`: **only last semester** (`1142`)<br>Without `--fast`: **all semesters in `allSemesters`** |
| **Departments** | Iterates through all `dp1/dp2/dp3` combinations from unit.json |
| **Database Table** | `COURSE` |
| **Data Stored** | Course name, English name, teacher, credits, time, classroom, department codes (dp1/dp2/dp3), syllabus/description, objectives, etc. |

---

### `--teacher`

Fetches teacher IDs using NCCU's course tracking system.

| Aspect | Details |
|--------|---------|
| **API Endpoints** | 1. `TRACE_API` - Add/Delete/Get track list (`es.nccu.edu.tw/tracing/`)<br>2. Teacher page URLs from course data |
| **Source Courses** | From `COURSE` table filtered by current semester (`YEAR` + `SEM`) |
| **Teacher IDs From** | Parsed from `teaStatUrl` in course data:<br>- `https://newdoc.nccu.edu.tw/teaschm/{year_sem}/statisticAll.jsp-tnum={teacherId}.htm`<br>- `https://newdoc.nccu.edu.tw/teaschm/{year_sem}/set20.jsp` |
| **Database Table** | `TEACHER` |
| **Data Stored** | Teacher ID, Teacher Name |

**Requires:** `.env` credentials (`STUDENTID`, `STUDENTPWD`) to use the tracking API.

---

### `--rate`

Fetches teaching evaluation ratings for all teachers.

| Aspect | Details |
|--------|---------|
| **API Endpoints** | 1. `http://newdoc.nccu.edu.tw/teaschm/{semester}/statistic.jsp-tnum={teacherId}.htm`<br>2. `http://newdoc.nccu.edu.tw/teaschm/{semester}/{detailPage}` (individual course rates) |
| **Semesters Affected** | **`len(allSemesters)`** (always 39 semesters) — `--fast` does NOT affect this! |
| **Teacher Source** | Merged from:<br>1. `TEACHER` table (newly fetched)<br>2. `old_data/1111_teachers.json`<br>3. `old_data/1112_teachers.json` |
| **Database Table** | `RATE` |
| **Data Stored** | Course ID, row index, teacher ID, rating content |

**Note:** This is the **slowest** operation as it iterates through ALL semesters for ALL teachers.

---

### `--result`

Fetches course enrollment results from local CSV files.

| Aspect | Details |
|--------|---------|
| **Data Source** | Local CSV files in `./data/` (NOT an API) |
| **Semesters Affected** | `COURSERESULT_YEARSEM` = `["1102", "1111", "1112", "1121"]` (`len(COURSERESULT_YEARSEM)` = 4)<br>**Does NOT include current semester (1142)!** |
| **CSV Files Required** | `./data/1102CourseResult.csv`<br>`./data/1111CourseResult.csv`<br>`./data/1112CourseResult.csv`<br>`./data/1121CourseResult.csv`<br><br>**NOTE:** These CSV files MUST exist in `./data/` directory for `--result` to work. The code reads from local files, not an API. |
| **API Called** | `https://es.nccu.edu.tw/course/zh-TW/:sem={sem}%20{courseid}%20/` (to enrich CSV data) |
| **Database Table** | `RESULT` |
| **Data Stored** | Semester, course ID, course name, teacher, time, capacity, enrolled count, last enrollment |

---

## Summary Table

| Flag | Data Source | # Semesters | Affected by `--fast`? | Requires Auth? |
|------|-------------|-------------|----------------------|----------------|
| `--course` | NCCU API | 1 (`--fast`) or `len(allSemesters)` | **YES** | No |
| `--teacher` | NCCU API + TRACE | 1 (current semester) | **YES** | **YES** |
| `--rate` | NCCU olddoc | `len(allSemesters)` (always) | **NO** | No |
| `--result` | Local CSV + NCCU API | `len(COURSERESULT_YEARSEM)` | NO | No |

---

## Key Constants

### `allSemesters` (main.py:12-41)
```python
allSemesters = ["1011", "1012", "1021", ..., "1141", "1142"]
```
All 39 semesters from academic year 101 to 114.

### `COURSERESULT_YEARSEM` (constant.py:40)
```python
COURSERESULT_YEARSEM = ["1102", "1111", "1112", "1121"]
```
Hardcoded semesters for `--result` flag. Does NOT include current semester.

---

## Database Schemas

### COURSE Table
```sql
COURSE (
  id TEXT PRIMARY KEY, y TEXT, s TEXT, subNum TEXT, name TEXT, nameEn TEXT,
  teacher TEXT, teacherEn TEXT, kind INTEGER, time TEXT, timeEn TEXT,
  lmtKind TEXT, lmtKindEn TEXT, core INTEGER, lang TEXT, langEn TEXT,
  smtQty INTEGER, classroom TEXT, classroomId TEXT, unit TEXT, unitEn TEXT,
  dp1 TEXT, dp2 TEXT, dp3 TEXT, point REAL, subRemainUrl TEXT, subSetUrl TEXT,
  subUnitRuleUrl TEXT, teaExpUrl TEXT, teaSchmUrl TEXT, tranTpe TEXT,
  tranTpeEn TEXT, info TEXT, infoEn TEXT, note TEXT, noteEn TEXT,
  syllabus TEXT, objective TEXT
)
```

### TEACHER Table
```sql
TEACHER ( id TEXT, name TEXT )
```

### RATE Table
```sql
RATE ( courseId TEXT, rowId TEXT, teacherId TEXT, content TEXT, contentEn TEXT )
```

### RESULT Table
```sql
RESULT (
  courseId TEXT PRIMARY KEY, yearsem TEXT, name TEXT, teacher TEXT,
  time TEXT, studentLimit INTEGER, studentCount INTEGER, lastEnroll INTEGER
)
```

---

## Important Notes

1. `--fast` only affects `--course` and `--teacher`, NOT `--rate` or `--result`
2. `COURSERESULT_YEARSEM` is hardcoded in `constant.py:40` and does NOT include the current semester (1142)
3. `--rate` will crawl **ALL semesters in `allSemesters`** regardless of `--fast` flag
4. `--teacher` requires valid `.env` credentials for the NCCU tracking system
