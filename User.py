from constant import USERNAME, PASSWORD
import requests
from util import get_login_url, get_addtrack_url, get_deltrack_url, get_track_url

class User:
  _username: str
  _password: str
  _token: str

  def __init__(self) -> None:
    self._username = USERNAME
    self._password = PASSWORD
    res = requests.post(get_login_url(self._username, self._password))
    res = res.json()
    print(res)
    try:
      self._token = res[0]["encstu"]
    except:
      raise Exception("token error")
  
  def addTrack(self, courseId: str):
    addres = requests.post(get_addtrack_url(self._token, courseId)).json()
    if addres[0]["procid"] == "3":
      addres = requests.post(get_addtrack_url(self._token, courseId, priority="3")).json()
    if addres[0]["procid"] != "1":
      raise Exception("Add fail: " + courseId + " " + addres[0].get("procmsg", ""))
  
  def deleteTrack(self, courseId: str):
    deleteres = requests.post(get_deltrack_url(self._token, courseId)).json()
    if(deleteres[0]["procid"] != "9"): raise Exception("Delete fail: " + courseId)
    
  def getTrack(self):
    courseres = requests.post(get_track_url(self._token)).json()
    return courseres
