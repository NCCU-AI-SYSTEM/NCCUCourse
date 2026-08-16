import csv, os, json

import fetcher
from tqdm import tqdm
from constant import COURSERESULT_YEARSEM
import config
import shutil

def main():
  for sem in COURSERESULT_YEARSEM:
    i = 0
    csvPath = config.course_result_csv(sem)
    # utf-8-sig: three of the exports carry a BOM that would otherwise end up
    # inside the first row's course id.
    row_count = sum(1 for line in open(csvPath, 'r', encoding='utf-8-sig'))
    with open(csvPath, 'r', encoding='utf-8-sig') as f:
      reader = tqdm(csv.reader(f), total=row_count)
      for row in reader:
        courseid = str(row[0])
        try:
          res = fetcher.get("https://es.nccu.edu.tw/course/zh-TW/:sem=" + sem + "%20" + str(courseid) + "%20/").json()
          result = dict({
            "yearsem": sem,
            "time": res[0]["subTime"],
            "courseId": courseid,
            "studentLimit": str(row[3]),
            "studentCount": str(row[4]),
            "lastEnroll": str(row[5])
          })
          dataPath= "./result/" + res[0]["teaNam"] + "/" + res[0]["subNam"]
          if not os.path.exists(dataPath):
            os.makedirs(dataPath)
          if not os.path.exists(dataPath + "/courseResult"):
            os.makedirs(dataPath + "/courseResult")
          if not os.path.exists(dataPath + "/courseResult/" + sem + ".json"):
            with open(dataPath + "/courseResult/" + sem + ".json", "w") as file:
              json.dump(list(), file)
          
          with open(dataPath + "/courseResult/" + sem + ".json", 'r') as file:
            originalData = json.loads(file.read())
          originalData.append(result)
          with open(dataPath + "/courseResult/" + sem + ".json", "w") as file:
            json.dump(originalData, file)
        except BaseException as err:
          print(courseid + ": ", err)
        i += 1
      
  
if __name__ == "__main__":
  main()