"""Regression tests for mapping syllabus sections to columns.

The April 2026 crawl of 114-2 located sections by substring ('AI' in h2 text,
'評量' or 'Evaluation' in h2 text) and took the first match, which on these
pages is the course-title h2. 35 rows ended up with ai_policy or evaluation set
to the title's "Course Name: ..." line. Sections must be found by their exact
English heading only.

Run: uv run --with pytest pytest tests
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

import fetchDescription as fd

FIXTURE = Path(__file__).parent / "fixtures" / "syllabus_title_with_ai.html"
COURSE_ID = "1142000000001"


@pytest.fixture
def soup():
    return BeautifulSoup(FIXTURE.read_bytes(), "html.parser")


def test_title_heading_maps_to_no_column(soup):
    # The title h2 has no .En span, so it must not claim any column even
    # though its text contains both "AI" and "評量".
    assert set(fd._sectionHeadings(soup)) == {
        "syllabus", "objective", "evaluation", "ai_policy",
    }


def test_sections_come_from_their_own_headings(soup):
    sections = fd._extract_sections(soup)
    assert sections["ai_policy"] == "有條件開放使用:Only for grammar check|Conditional Permitted to Use"
    assert sections["evaluation"] == "Participation|：|20%|Final Paper|：|80%"
    for column, text in sections.items():
        assert "Course Name" not in text, column


class _Response:
    def __init__(self, payload=None, content=b""):
        self._payload = payload
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_description_end_to_end(monkeypatch):
    page_url = "http://newdoc.nccu.edu.tw/teaschm/1142/fixture.html"
    qrysub = {"teaSchmUrl": page_url, "subNam": "AI輔助學習評量"}

    def fake_get(url, **kwargs):
        if url.startswith("http://es.nccu.edu.tw/course/"):
            return _Response(payload=[qrysub])
        assert url == page_url
        return _Response(content=FIXTURE.read_bytes())

    monkeypatch.setattr(fd.fetcher, "get", fake_get)
    result = fd.fetchDescription(COURSE_ID)

    assert result["description"] == ["How generative AI changes classroom assessment."]
    assert result["objectives"] == ["Design a test with AI tools."]
    assert set(result["sections"]) == {"evaluation", "ai_policy"}
    assert result["sections"]["ai_policy"].startswith("有條件開放使用")
    assert result["sections"]["evaluation"].startswith("Participation")
