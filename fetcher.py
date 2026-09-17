"""Shared HTTP GET with retries and a timeout.

The NCCU hosts drop connections mid-crawl. A single reset used to cost either one
course's syllabus or the rest of a category, depending on which of the three
requests it hit — and nothing retried. Measured over 9,016 probe requests, one
failed and succeeded immediately on retry, so these are transient.

GET is idempotent, so urllib3 can safely replay it.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TIMEOUT = 30

_retry = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=1,  # waits 0s, 2s, 4s
    status_forcelist=(500, 502, 503, 504),
    allowed_methods=("GET",),
)

_session = requests.Session()
_adapter = HTTPAdapter(max_retries=_retry)
_session.mount("http://", _adapter)
_session.mount("https://", _adapter)


def get(url, **kwargs):
    # requests.Session has no default timeout, so it has to be applied per call.
    kwargs.setdefault("timeout", TIMEOUT)
    return _session.get(url, **kwargs)
