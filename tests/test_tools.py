"""Unit tests for the four agent tools.

Each tool is pure data retrieval or logic, so it can be tested without an LLM.
The external dependencies (Postgres for payment_estimator, the pgvector store
for eligibility_screener, and Playwright-driven scrapes for practice_matcher and
program_availability) are stubbed, so the whole module runs on a bare checkout
with no database, network, or API key.

Coverage:
    - payment_estimator groups rows by program and fiscal year, title-cases the
      state, and returns clear not_found / error envelopes.
    - eligibility_screener deduplicates retrieved chunks by section, caps the
      result, formats citations, ignores an unrecognized program, and reports
      when nothing matches.
    - practice_matcher parses a saved sample of the scraped page and fails
      gracefully into a structured error when the scrape raises.
    - program_availability normalizes state input and fails gracefully.

Out of scope handling is not a tool, so it is covered in test_agent.py (the
system prompt makes the agent decline), not here.
"""

from decimal import Decimal

import pytest

from nrcs_navigator.tools import payment_estimator as pe
from nrcs_navigator.tools import eligibility_screener as es
from nrcs_navigator.tools import practice_matcher as pm
from nrcs_navigator.tools import program_availability as pa


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class _FakeResult:
    """Stands in for a SQLAlchemy result; mappings().all() yields dict rows."""

    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeConn:
    """Context-managed connection that records the params it was executed with."""

    def __init__(self, rows, captured):
        self._rows = rows
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self._captured["params"] = params
        return _FakeResult(self._rows)


class _FakeEngine:
    def __init__(self, rows, captured):
        self._rows = rows
        self._captured = captured

    def connect(self):
        return _FakeConn(self._rows, self._captured)


class _FakePage:
    def __init__(self, html):
        self._html = html

    def goto(self, *a, **k):
        pass

    def evaluate(self, *a, **k):
        pass

    def wait_for_timeout(self, *a, **k):
        pass

    def content(self):
        return self._html


class _FakeBrowser:
    def __init__(self, html):
        self._page = _FakePage(html)

    def new_page(self):
        return self._page

    def close(self):
        pass


class _FakeChromium:
    def __init__(self, html):
        self._html = html

    def launch(self, **k):
        return _FakeBrowser(self._html)


class _FakePlaywright:
    """Context manager mimicking sync_playwright() serving fixed page HTML."""

    def __init__(self, html):
        self.chromium = _FakeChromium(html)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# --------------------------------------------------------------------------- #
# payment_estimator
# --------------------------------------------------------------------------- #


class TestPaymentEstimator:
    def test_groups_by_program_and_fiscal_year(self, monkeypatch):
        rows = [
            {
                "program": "EQIP",
                "fiscal_year": 2023,
                "total_dollars_obligated": Decimal("100.00"),
                "total_instances": 4,
                "average_payment_per_instance": Decimal("25.00"),
            },
            {
                "program": "EQIP",
                "fiscal_year": 2024,
                "total_dollars_obligated": Decimal("200.00"),
                "total_instances": 5,
                "average_payment_per_instance": Decimal("40.00"),
            },
            {
                "program": "CSP",
                "fiscal_year": 2024,
                "total_dollars_obligated": Decimal("90.00"),
                "total_instances": 3,
                "average_payment_per_instance": Decimal("30.00"),
            },
        ]
        monkeypatch.setattr(pe.db, "get_engine", lambda: _FakeEngine(rows, {}))

        result = pe.get_payment_estimate_by_state("iowa")

        assert result["status"] == "success"
        assert result["source"] == pe.SOURCE
        assert set(result["programs"]) == {"EQIP", "CSP"}
        assert len(result["programs"]["EQIP"]) == 2
        first = result["programs"]["EQIP"][0]
        # Values are coerced to plain JSON-friendly numbers.
        assert first == {
            "fiscal_year": 2023,
            "total_dollars_obligated": 100.0,
            "total_instances": 4,
            "average_payment_per_instance": 25.0,
        }
        assert isinstance(first["fiscal_year"], int)
        assert isinstance(first["total_dollars_obligated"], float)

    def test_state_is_title_cased_in_query(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(pe.db, "get_engine", lambda: _FakeEngine([], captured))

        pe.get_payment_estimate_by_state("NEW mexico")

        assert captured["params"] == {"state": "New Mexico"}

    def test_not_found_when_no_rows(self, monkeypatch):
        monkeypatch.setattr(pe.db, "get_engine", lambda: _FakeEngine([], {}))

        result = pe.get_payment_estimate_by_state("Nowhere")

        assert result["status"] == "not_found"
        assert result["programs"] == {}
        assert "message" in result

    def test_error_envelope_on_db_failure(self, monkeypatch):
        def boom():
            raise RuntimeError("connection refused")

        monkeypatch.setattr(pe.db, "get_engine", boom)

        result = pe.get_payment_estimate_by_state("Iowa")

        assert result["status"] == "error"
        assert "connection refused" in result["message"]
        assert result["programs"] == {}

    def test_tool_wrapper_delegates(self, monkeypatch):
        monkeypatch.setattr(pe.db, "get_engine", lambda: _FakeEngine([], {}))

        result = pe.payment_estimator.invoke({"state": "Iowa"})

        assert result["status"] == "not_found"


# --------------------------------------------------------------------------- #
# eligibility_screener
# --------------------------------------------------------------------------- #


class _Doc:
    def __init__(self, part, section, citation, heading, program, text):
        self.page_content = text
        self.metadata = {
            "part": part,
            "section": section,
            "citation": citation,
            "heading": heading,
            "program": program,
        }


class TestEligibilityScreener:
    def test_dedupes_by_section_and_caps_result(self, monkeypatch):
        # Two chunks of section 1466.6 (the first should win), plus three more
        # distinct sections. With TOP_SECTIONS == 4 only four blocks come back.
        hits = [
            _Doc("1466", "1466.6", "7 CFR 1466.6", "Eligibility", "EQIP", "best chunk"),
            _Doc("1466", "1466.6", "7 CFR 1466.6", "Eligibility", "EQIP", "dup chunk"),
            _Doc("1466", "1466.7", "7 CFR 1466.7", "Payments", "EQIP", "b"),
            _Doc("1470", "1470.3", "7 CFR 1470.3", "Definitions", "CSP", "c"),
            _Doc("1468", "1468.5", "7 CFR 1468.5", "Easements", "ACEP", "d"),
            _Doc("1464", "1464.2", "7 CFR 1464.2", "Partners", "RCPP", "e"),
        ]
        monkeypatch.setattr(es.vectorstore, "similarity_search", lambda *a, **k: hits)

        out = es.eligibility_screener.func("query about erosion")

        blocks = out.split("\n\n")
        assert len(blocks) == es.TOP_SECTIONS == 4
        # First block is the best-ranked chunk of the deduped section.
        assert blocks[0] == "[7 CFR 1466.6] Eligibility (EQIP)\nbest chunk"
        # The duplicate section text never reappears.
        assert "dup chunk" not in out

    def test_no_hits_message(self, monkeypatch):
        monkeypatch.setattr(es.vectorstore, "similarity_search", lambda *a, **k: [])

        out = es.eligibility_screener.func("anything")

        assert out == "No matching regulation sections found."

    def test_valid_program_passed_through(self, monkeypatch):
        captured = {}

        def fake_search(query, k, program):
            captured["program"] = program
            return []

        monkeypatch.setattr(es.vectorstore, "similarity_search", fake_search)

        es.eligibility_screener.func("q", program="eqip")

        assert captured["program"] == "EQIP"

    def test_unrecognized_program_ignored(self, monkeypatch):
        captured = {}

        def fake_search(query, k, program):
            captured["program"] = program
            return []

        monkeypatch.setattr(es.vectorstore, "similarity_search", fake_search)

        es.eligibility_screener.func("q", program="CRP")

        # An out-of-scope program is dropped rather than narrowing to nothing.
        assert captured["program"] is None


# --------------------------------------------------------------------------- #
# practice_matcher
# --------------------------------------------------------------------------- #


class TestPracticeMatcher:
    def test_parses_practices_from_sample_html(self, monkeypatch):
        html = """
        <html><body>
          <a href="/resources/guides-and-instructions/conservation-cover">
            Conservation Cover (327)
          </a>
          <a href="/resources/guides-and-instructions/cover-crop">Cover Crop (340)</a>
          <a href="/about/contact">Contact Us</a>
          <a href="/resources/guides-and-instructions/overview">Overview</a>
        </body></html>
        """
        monkeypatch.setattr(pm, "sync_playwright", lambda: _FakePlaywright(html))

        result = pm.get_practice_standards()

        assert result["status"] == "success"
        assert result["source"] == pm.NRCS_URL
        # Only the two anchors that are under guides-and-instructions AND carry a
        # three-digit code qualify; "Contact Us" and "Overview" are skipped.
        assert result["practice_count"] == 2
        by_code = {p["code"]: p for p in result["practices"]}
        assert set(by_code) == {"327", "340"}
        assert by_code["327"]["name"] == "Conservation Cover"
        assert by_code["327"]["url"].startswith(pm.BASE_URL)
        assert by_code["327"]["url"].endswith("/conservation-cover")

    def test_error_envelope_when_scrape_fails(self, monkeypatch):
        def boom():
            raise RuntimeError("browser launch failed")

        monkeypatch.setattr(pm, "sync_playwright", boom)

        result = pm.get_practice_standards()

        assert result["status"] == "error"
        assert result["practice_count"] == 0
        assert result["practices"] == []
        assert "browser launch failed" in result["message"]


# --------------------------------------------------------------------------- #
# program_availability
# --------------------------------------------------------------------------- #


class TestProgramAvailability:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("IA", "Iowa"),
            ("ia", "Iowa"),
            ("Iowa", "Iowa"),
            ("new mexico", "New Mexico"),  # unknown to the map -> title-cased
        ],
    )
    def test_normalize_state(self, raw, expected):
        assert pa.normalize_state(raw) == expected

    def test_parses_ranking_dates_for_state(self, monkeypatch):
        html = """
        <html><body>
          <p>Iowa</p>
          <p>EQIP: January 25, 2026</p>
          <p>CSP: March 14, 2026</p>
          <p>Kansas</p>
          <p>EQIP: April 1, 2026</p>
        </body></html>
        """
        monkeypatch.setattr(pa, "sync_playwright", lambda: _FakePlaywright(html))

        result = pa.get_program_availability("IA")

        assert result["status"] == "success"
        assert result["state"] == "Iowa"
        assert result["source"] == pa.RANKING_DATES_URL
        # Both of Iowa's program dates are picked up, and the section stops at
        # the next state heading so Kansas's April date is excluded.
        dates = {p["ranking_date"] for p in result["programs"]}
        assert "January 25, 2026" in dates
        assert "March 14, 2026" in dates
        assert "April 1, 2026" not in dates
        # CSP parses cleanly to a single-word name, so it surfaces as a code.
        assert "CSP" in result["available_program_codes"]

    def test_error_envelope_when_scrape_fails(self, monkeypatch):
        def boom():
            raise RuntimeError("timeout")

        monkeypatch.setattr(pa, "sync_playwright", boom)

        result = pa.get_program_availability("Iowa")

        assert result["status"] == "error"
        assert result["program_count"] == 0
        assert result["programs"] == []
        assert "timeout" in result["message"]
