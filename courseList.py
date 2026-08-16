"""Read 科目代號 from the registrar's published course list (data/course_list/<yearsem>.ods).

The category scan in main.py cannot reach courses that belong to no unit in
unit.json, so this list is the only way to notice they are missing.
"""

from odf.opendocument import load
from odf.table import Table, TableRow, TableCell
from odf.text import P

# 科目代號 is the first column; the two rows above it are the title and headers.
SUBNUM_COLUMN = 0
HEADER_ROWS = 2


def _cells(row):
  values = []
  for cell in row.getElementsByType(TableCell):
    repeated = int(cell.getAttribute("numbercolumnsrepeated") or 1)
    text = "".join(str(p) for p in cell.getElementsByType(P))
    values.extend([text] * min(repeated, 30))
  return values


def readCourseList(path: str) -> list[str]:
  sheet = load(path).spreadsheet.getElementsByType(Table)[0]
  subNums = []
  for row in sheet.getElementsByType(TableRow)[HEADER_ROWS:]:
    values = _cells(row)
    if len(values) <= SUBNUM_COLUMN:
      continue
    subNum = values[SUBNUM_COLUMN].strip()
    if subNum:
      subNums.append(subNum)
  return subNums


if __name__ == "__main__":
  import sys
  nums = readCourseList(sys.argv[1])
  print("{} courses, first 5: {}".format(len(nums), nums[:5]))
