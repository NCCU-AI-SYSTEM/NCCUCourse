"""Semester settings from config.yaml, plus lists derived from data/.

See config.yaml for what each block means and which code reads it.
"""

import os
import re
import glob

import yaml

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(REPO_ROOT, "config.yaml")
DATA_DIR = os.path.join(REPO_ROOT, "data")
COURSE_LIST_DIR = os.path.join(DATA_DIR, "course_list")
COURSE_RESULT_DIR = os.path.join(DATA_DIR, "course_result")

with open(CONFIG_PATH, encoding="utf-8") as _f:
    CONFIG = yaml.safe_load(_f)

YEAR = str(CONFIG["target"]["year"])
SEM = str(CONFIG["target"]["semester"])
YEAR_SEM = YEAR + SEM

CRAWL_SEMESTERS = [str(s) for s in CONFIG["crawl"]["semesters"]]
REMAIN_SEMESTER = str(CONFIG["remain"]["semester"])

DEFAULT_DB = f"{YEAR_SEM}.db"

# Without this, a full --course run iterates every crawl semester, the
# `semester == YEAR_SEM` guard in main.py never fires, and coursesList stays
# empty - the rate pass then silently does nothing.
if YEAR_SEM not in CRAWL_SEMESTERS:
    raise ValueError(
        f"target {YEAR}-{SEM} ({YEAR_SEM}) is not in crawl.semesters. "
        f"Add it to config.yaml, or set target to one of "
        f"{CRAWL_SEMESTERS[-3:]}..."
    )


def _semesters_from(directory: str, pattern: str, regex: str) -> list[str]:
    found = set()
    for path in glob.glob(os.path.join(directory, pattern)):
        m = re.match(regex, os.path.basename(path))
        if m:
            found.add(m.group(1))
    return sorted(found)


def course_result_semesters() -> list[str]:
    """Semesters with a data/course_result/<sem>CourseResult.csv on disk."""
    return _semesters_from(COURSE_RESULT_DIR, "*CourseResult.csv", r"(\d{4})CourseResult\.csv$")


def pe_ge_semesters() -> list[str]:
    """Semesters with a data/course_result/<sem>_pe_ge.pdf on disk."""
    return _semesters_from(COURSE_RESULT_DIR, "*_pe_ge.pdf", r"(\d{4})_pe_ge\.pdf$")


def course_list_semesters() -> list[str]:
    """Semesters with a data/course_list/<sem>.ods on disk."""
    return _semesters_from(COURSE_LIST_DIR, "*.ods", r"(\d{4})\.ods$")


def course_result_csv(sem: str) -> str:
    return os.path.join(COURSE_RESULT_DIR, f"{sem}CourseResult.csv")


def pe_ge_pdf(sem: str) -> str:
    return os.path.join(COURSE_RESULT_DIR, f"{sem}_pe_ge.pdf")


def course_list_path(yearsem: str) -> str | None:
    """The registrar's published course list, or None if none was downloaded."""
    path = os.path.join(COURSE_LIST_DIR, f"{yearsem}.ods")
    return path if os.path.exists(path) else None


def course_list_ods(sem: str) -> str:
    return os.path.join(COURSE_LIST_DIR, f"{sem}.ods")
