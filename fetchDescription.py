from bs4 import BeautifulSoup
import re, requests, logging

def _extract_schedule(soup):
  for h2 in soup.find_all('h2'):
    if '每周' in h2.get_text() or 'Schedule' in h2.get_text():
      parent = h2.find_parent('div', class_=True)
      if parent:
        return parent.get_text(separator='|', strip=True)
  return ""

def _extract_evaluation(soup):
  for h2 in soup.find_all('h2'):
    if '評量' in h2.get_text() or 'Evaluation' in h2.get_text():
      parts = []
      sibling = h2.find_next_sibling()
      while sibling and sibling.name != 'h2':
        text = sibling.get_text(strip=True)
        if text:
          parts.append(text)
        sibling = sibling.find_next_sibling()
      return '|'.join(parts)
  return ""

def _extract_textbook(soup):
  for h2 in soup.find_all('h2'):
    if '書目' in h2.get_text() or 'Textbook' in h2.get_text():
      parts = []
      sibling = h2.find_next_sibling()
      while sibling and sibling.name != 'h2':
        text = sibling.get_text(strip=True)
        if text:
          parts.append(text)
        sibling = sibling.find_next_sibling()
      return '|'.join(parts)
  return ""

def _extract_teaching_approach(soup):
  for h2 in soup.find_all('h2'):
    if '授課方式' in h2.get_text() or 'Teaching Approach' in h2.get_text():
      parent = h2.find_parent('div', class_=True)
      if parent:
        return parent.get_text(separator='|', strip=True)
  return ""

def _extract_ai_policy(soup):
  for h2 in soup.find_all('h2'):
    if 'AI' in h2.get_text():
      parts = []
      sibling = h2.find_next_sibling()
      while sibling and sibling.name != 'h2':
        text = sibling.get_text(strip=True)
        if text:
          parts.append(text)
        sibling = sibling.find_next_sibling()
      return '|'.join(parts)
  return ""

def fetchDescription(courseId: str):
  if len(courseId) != 13:
    raise Exception("Wrong courseId format")
  result = {
    "description": list(),
    "objectives": list(),
    "schedule": "",
    "evaluation": "",
    "textbook": "",
    "teaching_approach": "",
    "ai_policy": "",
    "qrysub": dict(),
  }

  try:
    response = requests.get("http://es.nccu.edu.tw/course/zh-TW/{} /".format(courseId))
    response.raise_for_status()
    if len(response.json()) != 1:
      raise Exception("No matched course")
    result["qrysub"] = response.json()[0]
    response = requests.get("http://es.nccu.edu.tw/course/en/{} /".format(courseId))
    response.raise_for_status()
    if len(response.json()) != 1:
      raise Exception("No matched course")
    result["qrysubEn"] = response.json()[0]
    location = str(result["qrysub"]["teaSchmUrl"]).replace("https://", "http://")

    res = requests.get(location)
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
      descriptionTitle = soap.find("div", {"class": "col-sm-7 sylview--mtop col-p-6"}).find("h2", {"class": "text-primary"})
      descriptions = descriptionTitle.find_next_siblings(True)
      for description in descriptions:
        if description.attrs and description.attrs.get("class") and ["row", "sylview-mtop", "fa-border"] == description.attrs["class"]:
          break
        for line in [x for x in re.split(r'[\n\r]+', description.get_text(strip=True)) if len(x) > 0 and x != " "]:
          result["description"].append(line)

      objectives = soap.find("div", {"class": "container sylview-section"}).select_one(".col-p-8")
      for objective in objectives:
        for line in [x for x in re.split(r'[\n\r]+', objective.get_text(strip=True)) if len(x) > 0 and x != " "]:
          result["objectives"].append(line)

      result["schedule"] = _extract_schedule(soap)
      result["evaluation"] = _extract_evaluation(soap)
      result["textbook"] = _extract_textbook(soap)
      result["teaching_approach"] = _extract_teaching_approach(soap)
      result["ai_policy"] = _extract_ai_policy(soap)

  except Exception as e:
    logging.error(courseId)
    logging.error(e)

  return result

if __name__ == "__main__":
  r = fetchDescription("1142000348021")
  print("=== Description ===")
  print("\n".join(r["description"][:3]))
  print("=== Schedule ===")
  print(r["schedule"][:300])
  print("=== Evaluation ===")
  print(r["evaluation"][:300])
  print("=== Textbook ===")
  print(r["textbook"][:300])
  print("=== AI Policy ===")
  print(r["ai_policy"][:300])
