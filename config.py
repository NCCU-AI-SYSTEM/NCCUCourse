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


def _semesters_from(pattern: str, regex: str) -> list[str]:
    found = set()
    for path in glob.glob(os.path.join(DATA_DIR, pattern)):
        m = re.match(regex, os.path.basename(path))
        if m:
            found.add(m.group(1))
    return sorted(found)


def course_result_semesters() -> list[str]:
    """Semesters with a data/<sem>CourseResult.csv on disk."""
    return _semesters_from("*CourseResult.csv", r"(\d{4})CourseResult\.csv$")


def pe_ge_semesters() -> list[str]:
    """Semesters with a data/<sem>_pe_ge.pdf on disk."""
    return _semesters_from("*_pe_ge.pdf", r"(\d{4})_pe_ge\.pdf$")
