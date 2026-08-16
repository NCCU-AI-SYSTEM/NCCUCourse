from bs4 import BeautifulSoup
from time import sleep
import os, json, logging, tqdm, datetime, argparse, csv

import fetcher
from DB import DB

from User import User
import config
from constant import YEAR_SEM, YEAR, SEM, COURSERESULT_YEARSEM
from courseList import readCourseList
from fetchDescription import EMPTY_SYLLABUS, fetchDescription
from fetchRate import fetchRate
# from translateRate import translateRate

allSemesters = config.CRAWL_SEMESTERS

dirPath = os.path.dirname(os.path.realpath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--course", action="store_true", help="Fetch class")
parser.add_argument("--fast", action="store_true", help="Fetch this semester only")
parser.add_argument("--teacher", action="store_true", help="Fetch teacher")
parser.add_argument("--rate", action="store_true", help="Fetch rate")
parser.add_argument("--result", action="store_true", help="Fetch result")
parser.add_argument("--db", help="Database name", default=config.DEFAULT_DB)
args = parser.parse_args()

if __name__ == "__main__":

    # Setup logger
    logging.basicConfig(
        filename="log.log",
        format="%(asctime)s [%(levelname)s] %(message)s",
        encoding="utf-8",
    )

    if os.path.exists(os.path.join(dirPath, "_data")):
        os.makedirs(os.path.join(dirPath, "_data"), exist_ok=True)

    db = DB(args.db)

    # ==============================
    # \ 1. Fetch Classes           \
    # ==============================

    if args.course:
        # fetch all deps first, make a single search less than 500
        try:
            units = fetcher.get("https://qrysub.nccu.edu.tw/assets/api/unit.json")
            units.raise_for_status()
            units = units.json()
        except Exception as e:
            logging.error("Failed to get unit list, falls back to local cache")
            with open(os.path.join(config.DATA_DIR, "unit.json")) as f:
                units = json.load(f)
            
        # Narrowest first, then roll up: a course whose (dp1,dp2,dp3) is missing
        # from unit.json cannot be reached at leaf level but shows up one level
        # broader. "" means the level is left out of the query. Each step only
        # takes courses no earlier step returned, so the dp columns record the
        # narrowest category the course was actually found under.
        categories = list()
        for dp1 in [x for x in units if x["utCodL1"] != "0"]:
            for dp2 in [x for x in dp1["utL2"] if x["utCodL2"] != "0"]:
                for dp3 in [x for x in dp2["utL3"] if x["utCodL3"] != "0"]:
                    categories.append(
                        {
                            "dp1": dp1["utCodL1"],
                            "dp2": dp2["utCodL2"],
                            "dp3": dp3["utCodL3"],
                        }
                    )
                categories.append({"dp1": dp1["utCodL1"], "dp2": dp2["utCodL2"], "dp3": ""})
            categories.append({"dp1": dp1["utCodL1"], "dp2": "", "dp3": ""})
        categories.append({"dp1": "", "dp2": "", "dp3": ""})

        # run through all deps, get their classId
        coursesList = list()
        semesters = [YEAR_SEM] if args.fast else allSemesters
        def alreadyCovered(stored, category):
            """True if this course was stored under `category` or below it.

            A course legitimately belongs to several categories, so a roll-up
            only skips what one of its own descendants already recorded — a hit
            in a different branch is a different membership and still counts.
            """
            for dp1, dp2, dp3 in stored:
                if all(
                    not category[level] or category[level] == found
                    for level, found in (("dp1", dp1), ("dp2", dp2), ("dp3", dp3))
                ):
                    return True
            return False

        for semester in semesters:
            # Per semester: a subNum means a different course in another one.
            seen = dict()
            tqdmCategories = tqdm.tqdm(categories, leave=False)
            for category in tqdmCategories:
                tqdmCategories.set_postfix_str("{} {}".format(semester, category))
                try:
                    sleep(0.1)
                    query = " ".join(
                        [":sem={}".format(semester)]
                        + [
                            ":{}={}".format(level, category[level])
                            for level in ("dp1", "dp2", "dp3")
                            if category[level]
                        ]
                    )
                    res = fetcher.get("https://es.nccu.edu.tw/course/zh-TW/" + query)
                    res.raise_for_status()
                    courses = res.json()
                    # A capped roll-up is expected — it asks for a whole college.
                    # A capped leaf means unit.json no longer splits finely enough
                    # for one query to return everything, and rows are being lost.
                    if category["dp3"] and len(courses) >= 500:
                        raise Exception("{} too large".format(category))

                    # Write to databse
                    fresh = [
                        x for x in courses
                        if not alreadyCovered(seen.get(x["subNum"], ()), category)
                    ]
                    for course in tqdm.tqdm(fresh, leave=False):
                        courseId = "{}{}".format(semester, course["subNum"])
                        try:
                            detail = fetchDescription(courseId)
                            if not detail["qrysub"] or "qrysubEn" not in detail:
                                continue
                            db.addCourse(
                                detail["qrysub"],
                                detail["qrysubEn"],
                                category["dp1"],
                                category["dp2"],
                                category["dp3"],
                                "".join(detail["description"]),
                                "".join(detail["objectives"]),
                                detail["sections"],
                            )
                            # Only on success, so a broader query retries the rest.
                            seen.setdefault(course["subNum"], []).append(
                                (category["dp1"], category["dp2"], category["dp3"])
                            )
                            if semester == YEAR_SEM:
                                coursesList.append(course["subNum"])
                        except Exception as e:
                            logging.error("{}: {}".format(courseId, e))
                except Exception as e:
                    logging.error(e)

        logging.debug(coursesList)

        # Courses filed under no unit in unit.json are unreachable by the loop
        # above, so reconcile against the registrar's list when one is present.
        listPath = config.course_list_path(YEAR_SEM)
        if not listPath:
            print("No course list for {}, skipping reconcile".format(YEAR_SEM))
        else:
            # What actually landed, not coursesList: that is filled from the API
            # response before the write loop, so a course lost to a mid-category
            # failure would still look fetched.
            fetched = set(db.getThisSemesterCourse(YEAR, SEM))
            missing = [x for x in readCourseList(listPath) if x not in fetched]
            print("Course list: {} of {} not reached by the category scan".format(
                len(missing), len(fetched) + len(missing)))
            recovered = 0
            for subNum in tqdm.tqdm(missing, leave=False, desc="Reconciling"):
                try:
                    sleep(0.1)
                    detail = fetchDescription("{}{}".format(YEAR_SEM, subNum))
                    if not detail["qrysub"] or "qrysubEn" not in detail:
                        continue
                    db.addCourse(
                        detail["qrysub"],
                        detail["qrysubEn"],
                        "",
                        "",
                        "",
                        "".join(detail["description"]),
                        "".join(detail["objectives"]),
                        detail["sections"],
                    )
                    recovered += 1
                except Exception as e:
                    logging.error("{}: {}".format(subNum, e))
            print("Recovered {} of {}".format(recovered, len(missing)))

        # Distinct from a failed fetch: NCCU has no syllabus page for these.
        noSyllabus = db.con.execute(
            "SELECT COUNT(DISTINCT id) FROM COURSE WHERE y=? AND s=? "
            "AND teaSchmUrl LIKE ?",
            (YEAR, SEM, "%" + EMPTY_SYLLABUS + "%"),
        ).fetchone()[0]
        if noSyllabus:
            print("{} courses have no syllabus page at NCCU".format(noSyllabus))

        print("Fetch Class done at {}".format(datetime.datetime.now()))
    else:
        print("Skipping Fetch Class")

    # ==============================
    # \ 2. Fetch TeacherId         \
    # ==============================

    if args.teacher:
        # Read course list
        coursesList = db.getThisSemesterCourse(YEAR, SEM)

        user = User()

        # Delete exist track courses before adding
        courses = user.getTrack()
        if len(courses) > 0:
            tqdmCourses = tqdm.tqdm(courses, leave=False)
            for course in tqdmCourses:
                try:
                    sleep(0.2)
                    courseId = str(course["subNum"])
                    tqdmCourses.set_postfix_str("Pre-deleting {}".format(courseId))
                    user.deleteTrack(courseId)
                except Exception as e:
                    logging.error(e)
                    continue

        # Add courses to track list
        tqdmCourses = tqdm.tqdm([*set(coursesList)], leave=False)
        for courseId in tqdmCourses:
            try:
                sleep(0.2)
                tqdmCourses.set_postfix_str("Adding {}".format(courseId))
                user.addTrack(courseId)
            except Exception as e:
                logging.error(e)
                continue

        # get track list and parse out teacher id
        courses = user.getTrack()
        teacherIdDict = dict()
        tqdmCourses = tqdm.tqdm(courses, leave=False)
        for course in tqdmCourses:
            try:
                teacherStatUrl = str(course["teaStatUrl"])
                teacherName = str(course["teaNam"])
                tqdmCourses.set_postfix_str("Processing {}".format(teacherName))
                if teacherStatUrl.startswith(
                    "https://newdoc.nccu.edu.tw/teaschm/{}/statisticAll.jsp".format(
                        YEAR_SEM
                    )
                ):
                    teacherId = teacherStatUrl.split(
                        "https://newdoc.nccu.edu.tw/teaschm/{}/statisticAll.jsp-tnum=".format(
                            YEAR_SEM
                        )
                    )[1].split(".htm")[0]
                    teacherIdDict[teacherName] = teacherId
                    db.addTeacher(teacherId, teacherName)
                elif teacherStatUrl.startswith(
                    "https://newdoc.nccu.edu.tw/teaschm/{}/set20.jsp".format(YEAR_SEM)
                ):
                    # use ip to avoid name resolve error, and add time out
                    res = fetcher.get(
                        teacherStatUrl.replace(
                            "newdoc.nccu.edu.tw", "140.119.229.20"
                        ).replace("https://", "http://"),
                        timeout=10,
                    )
                    res.raise_for_status()
                    sleep(0.2)
                    soup = BeautifulSoup(res.content, "html.parser")
                    rows = soup.find_all("tr")
                    for row in [
                        x.find_all("td")
                        for x in soup.find_all("tr")
                        if x.find_all("td")[1].find("a")
                    ]:
                        teacherName = str(row[0].text)
                        teacherId = (
                            row[-1]
                            .find("a")["href"]
                            .split("statisticAll.jsp-tnum=")[1]
                            .split(".htm")[0]
                        )
                        teacherIdDict[teacherName] = teacherId
                        db.addTeacher(teacherId, teacherName)
            except Exception as e:
                logging.error(e)
                continue

        # Delete courses from track list
        tqdmCourses = tqdm.tqdm(courses, leave=False)
        for course in tqdmCourses:
            try:
                sleep(0.2)
                courseId = str(course["subNum"])
                tqdmCourses.set_postfix_str("Deleting {}".format(courseId))
                user.deleteTrack(courseId)
            except Exception as e:
                logging.error(e)
                continue

        print("Fetch TeacherId done at {}".format(datetime.datetime.now()))
    else:
        print("Skipping Fetch TeacherId")

    # ==============================
    # \ 3. Fetch Rates and Details \
    # ==============================

    if args.rate:
        # Read teacher list
        newTeacherList = db.getTeachers()
        with open(os.path.join(dirPath, "old_data", "1111_teachers.json"), "r") as f:
            oldTeacherList = json.loads(f.read())
        teacherList = {**newTeacherList, **oldTeacherList}
        with open(os.path.join(dirPath, "old_data", "1112_teachers.json"), "r") as f:
            oldTeacherList = json.loads(f.read())
        teacherList = {**newTeacherList, **oldTeacherList}

        # Run through all teacherId, and fetch courses of teachers
        teachers = tqdm.tqdm(teacherList, total=len(teacherList), leave=False)
        for teacher in teachers:
            teacherId = teacherList[teacher]
            teachers.set_postfix_str("processing: {} {}".format(teacherId, teacher))
            semesters = tqdm.tqdm(allSemesters, total=len(allSemesters), leave=False)
            for semester in semesters:
                semesters.set_postfix_str("processing: {}".format(semester))
                try:
                    location = "http://newdoc.nccu.edu.tw/teaschm/{}/statistic.jsp-tnum={}.htm".format(
                        semester, teacherId
                    )
                    res = fetcher.get(location)
                    res.raise_for_status()
                    soup = BeautifulSoup(res.content, "html.parser")
                    courses = soup.find("table", {"border": "1"}).find_all("tr")
                    availableCourses = [
                        x.find_all("td")
                        for x in courses
                        if x.find_all("td")[-1].find("a")
                        and int(x.find_all("td")[0].text) > 100
                    ]
                    tqdmCourses = tqdm.tqdm(
                        availableCourses, total=len(availableCourses), leave=False
                    )

                    for row in tqdmCourses:
                        courseId = "{}{}{}".format(
                            row[0].text, row[1].text, row[2].text
                        )
                        tqdmCourses.set_postfix_str("processing: {}".format(courseId))
                        if db.isRateExist(courseId):
                            continue
                        sleep(0.2)
                        rates = fetchRate(
                            "http://newdoc.nccu.edu.tw/teaschm/{}/{}".format(
                                semester, row[-1].find("a")["href"]
                            )
                        )

                        # Write to database
                        tqdmRates = tqdm.tqdm(rates, total=len(rates), leave=False)
                        for index, rate in enumerate(tqdmRates):
                            # rateEn = translateRate(str(rate))
                            rateEn = ""
                            db.addRate(index, courseId, teacherId, str(rate), rateEn)

                except Exception as e:
                    logging.error(e)
                    continue

        print("Fetch Rates and Details done at {}".format(datetime.datetime.now()))
    else:
        print("Skipping Fetch Rate")

    # ==============================
    # \ 4. Course Result           \
    # ==============================
    if args.result:
        for sem in COURSERESULT_YEARSEM:
            csvPath = config.course_result_csv(sem)
            # utf-8-sig: three of the exports carry a BOM that would otherwise
            # end up inside the first row's course id.
            row_count = sum(1 for line in open(csvPath, "r", encoding="utf-8-sig"))
            with open(csvPath, "r", encoding="utf-8-sig") as f:
                lines = [line for line in f]
                i = 0
                reader = tqdm.tqdm(csv.reader(lines), total=len(lines))
                for row in reader:
                    courseid = str(row[0])
                    try:
                        sleep(0.2)
                        res = fetcher.get(
                            "https://es.nccu.edu.tw/course/zh-TW/:sem="
                            + sem
                            + "%20"
                            + str(courseid)
                            + "%20/"
                        ).json()
                        db.addResult(
                            sem,
                            courseid,
                            res[0]["subNam"],
                            res[0]["teaNam"],
                            res[0]["subTime"],
                            int(row[3]),
                            int(row[4]),
                            -1 if row[5] == "" else int(row[5]),
                        )
                    except Exception as err:
                        logging.error(err)
                        continue
                    i += 1
