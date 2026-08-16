from bs4 import BeautifulSoup
import re, logging, unicodedata

import fetcher

# English headings that already have a column; everything else gets columnName().
SECTION_COLUMNS = {
  "Course Description": "syllabus",
  "Course Objectives & Learning Outcomes": "objective",
  "Course Schedule & Requirements": "schedule",
  "Teaching Approach": "teaching_approach",
  "Evaluation Criteria": "evaluation",
  "Textbook & References": "textbook",
  "Course Policies on the Use of Generative AI Tools": "ai_policy",
}

CHART_BLOCK = {"row", "sylview-mtop", "fa-border"}

# Prefixed so a heading can never slug onto a fixed column such as info or teacher.
def columnName(heading: str):
  name = unicodedata.normalize("NFKD", heading).replace("&", " and ")
  name = "".join(x for x in name if not unicodedata.combining(x))
  name = re.sub(r'[^0-9A-Za-z]+', '_', name).strip('_').lower()
  if not name:
    return None
  return "detail_" + name

def _sectionHeadings(soup):
  headings = dict()
  for h2 in soup.find_all('h2'):
    # The course-title h2 and the trailing icon h2 carry no .En span.
    en = h2.find(class_='En')
    if not en:
      continue
    heading = en.get_text(strip=True)
    if not heading:
      continue
    column = SECTION_COLUMNS.get(heading) or columnName(heading)
    if column:
      headings[column] = h2
  return headings

def _sectionParts(h2, separator):
  parts = []
  for sibling in h2.find_next_siblings():
    # 核心能力分析圖 trails the description with no heading of its own.
    if sibling.name == 'h2' or CHART_BLOCK.issubset(sibling.get('class') or []):
      break
    text = sibling.get_text(separator=separator, strip=True)
    if text:
      parts.append(text)
  return parts

def _extract_sections(soup):
  return {c: '|'.join(_sectionParts(h, '|')) for c, h in _sectionHeadings(soup).items()}

def fetchDescription(courseId: str):
  if len(courseId) != 13:
    raise Exception("Wrong courseId format")
  result = {
    "description": list(),
    "objectives": list(),
    "sections": dict(),
    "qrysub": dict(),
  }

  try:
    response = fetcher.get("http://es.nccu.edu.tw/course/zh-TW/{} /".format(courseId))
    response.raise_for_status()
    if len(response.json()) != 1:
      raise Exception("No matched course")
    result["qrysub"] = response.json()[0]
    response = fetcher.get("http://es.nccu.edu.tw/course/en/{} /".format(courseId))
    response.raise_for_status()
    if len(response.json()) != 1:
      raise Exception("No matched course")
    result["qrysubEn"] = response.json()[0]
    location = str(result["qrysub"]["teaSchmUrl"]).replace("https://", "http://")

    res = fetcher.get(location)
    soap = BeautifulSoup(res.content, "html.parser")
    isOld = soap.find("title").text == "教師資訊整合系統"

    if isOld:
      contents = soap.find("div", {"class": "accordionPart"}).find_all("span")
      for objective in contents[0].find("div", {"class": "qa_content"}):
        for line in [x for x in re.split(r'[\n\r]+', objective.get_text(strip=True)) if len(x) > 0 and x != " "]:
          result["description"].append(line)
      for objective in contents[1].find("div", {"class": "qa_content"}):
        for line in [x for x in re.split(r'[\n\r]+', objective.get_text(strip=True)) if len(x) > 0 and x != " "]:
          result["objectives"].append(line)
    else:
      headings = _sectionHeadings(soap)
      # Kept out of `sections` so both page layouts expose them the same way.
      # No separator here: these are joined with "" by the caller, and a '|'
      # would be indistinguishable from one occurring in the text itself.
      for key, column in (("description", "syllabus"), ("objectives", "objective")):
        if column in headings:
          result[key] = _sectionParts(headings.pop(column), '')
      result["sections"] = {c: '|'.join(_sectionParts(h, '|')) for c, h in headings.items()}

  except Exception as e:
    logging.error(courseId)
    logging.error(e)

  return result

if __name__ == "__main__":
  r = fetchDescription("1142000348021")
  print("=== Description ===")
  print("\n".join(r["description"][:3]))
  for column, text in r["sections"].items():
    print("=== {} ===".format(column))
    print(text[:300])
