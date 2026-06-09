"""
Tool: program_availability (live web scrape)

Determines which NRCS conservation programs currently have ranking
dates published for a specific state by scraping the NRCS Ranking Dates page.

Type:
    Live web scrape

Data source:
    https://www.nrcs.usda.gov/ranking-dates

Responsibilities:
    - Load the NRCS Ranking Dates page using Playwright.
    - Locate the requested state's ranking-date section.
    - Extract available conservation program names.
    - Extract ranking dates associated with each program.
    - Return structured program availability data.

Input:
    {
        "state": "Iowa"
    }

Output:
    {
        "status": "success",
        "state": "Iowa",
        "program_count": 5,
        "available_program_codes": [
            "ACEP",
            "CSP",
            "EQIP",
            "RCPP",
            "RPP"
        ],
        "programs": [
            {
                "name": "ACEP",
                "ranking_date": "January 25, 2026"
            }
        ]
    }
"""

from langchain_core.tools import tool

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

import json
import os
import re
import webbrowser

RANKING_DATES_URL = "https://www.nrcs.usda.gov/ranking-dates"


def normalize_state(state: str) -> str:
    """
    Normalize state input for matching.
    """

    state = state.strip()

    state_map = {
        "AL": "Alabama",
        "AK": "Alaska",
        "AZ": "Arizona",
        "AR": "Arkansas",
        "CA": "California",
        "CO": "Colorado",
        "CT": "Connecticut",
        "DE": "Delaware",
        "FL": "Florida",
        "GA": "Georgia",
        "HI": "Hawaii",
        "ID": "Idaho",
        "IL": "Illinois",
        "IN": "Indiana",
        "IA": "Iowa",
        "KS": "Kansas",
        "KY": "Kentucky",
        "LA": "Louisiana",
        "ME": "Maine",
        "MD": "Maryland",
        "MA": "Massachusetts",
        "MI": "Michigan",
        "MN": "Minnesota",
        "MS": "Mississippi",
        "MO": "Missouri",
        "MT": "Montana",
        "NE": "Nebraska",
        "NV": "Nevada",
        "NH": "New Hampshire",
        "NJ": "New Jersey",
        "NM": "New Mexico",
        "NY": "New York",
        "NC": "North Carolina",
        "ND": "North Dakota",
        "OH": "Ohio",
        "OK": "Oklahoma",
        "OR": "Oregon",
        "PA": "Pennsylvania",
        "RI": "Rhode Island",
        "SC": "South Carolina",
        "SD": "South Dakota",
        "TN": "Tennessee",
        "TX": "Texas",
        "UT": "Utah",
        "VT": "Vermont",
        "VA": "Virginia",
        "WA": "Washington",
        "WV": "West Virginia",
        "WI": "Wisconsin",
        "WY": "Wyoming",
    }

    upper = state.upper()

    if upper in state_map:
        return state_map[upper]

    return state.title()


def get_program_availability(
    state: str,
    save_html: bool = False,
    open_html: bool = False,
    html_path: str = "ranking_dates_debug.html",
) -> dict:
    """
    Scrape NRCS ranking dates page and return programs available
    for the specified state.
    """

    try:

        state = normalize_state(state)

        with sync_playwright() as p:

            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            print("Navigating...")

            page.goto(
                RANKING_DATES_URL,
                wait_until="networkidle",
                timeout=120000,
            )

            page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )

            page.wait_for_timeout(2000)

            html = page.content()

            print("HTML length:", len(html))

            if save_html:

                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html)

                print(f"Saved HTML → {html_path}")

                if open_html:
                    webbrowser.open(
                        f"file://{os.path.abspath(html_path)}"
                    )

            browser.close()

        soup = BeautifulSoup(html, "html.parser")

        page_text = soup.get_text("\n", strip=True)

        # Find requested state section
        state_pattern = rf"\b{re.escape(state)}\b"

        state_match = re.search(
            state_pattern,
            page_text,
            flags=re.IGNORECASE,
        )

        if not state_match:

            return {
                "status": "error",
                "state": state,
                "message": f"State '{state}' not found.",
                "program_count": 0,
                "available_program_codes": [],
                "programs": [],
            }

        start = state_match.start()

        remaining_text = page_text[start:]

        # Stop at next state heading if possible.
        next_state_match = re.search(
            r"\n[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\n",
            remaining_text[10:],
        )

        if next_state_match:
            state_section = remaining_text[
                : next_state_match.start() + 10
            ]
        else:
            state_section = remaining_text

        programs = []

        pattern = re.compile(
            r"([A-Za-z0-9\s\-&]+?)\s*:\s*"
            r"([A-Za-z]+\s+\d{1,2},\s+\d{4})"
        )

        for match in pattern.finditer(state_section):

            program_name = match.group(1).strip()
            ranking_date = match.group(2).strip()

            programs.append(
                {
                    "name": program_name,
                    "ranking_date": ranking_date,
                }
            )

        available_program_codes = []

        for program in programs:

            words = program["name"].split()

            if len(words) == 1:
                available_program_codes.append(words[0])

        return {
            "status": "success",
            "state": state,
            "program_count": len(programs),
            "available_program_codes": sorted(
                set(available_program_codes)
            ),
            "programs": programs,
        }

    except Exception as e:

        return {
            "status": "error",
            "state": state,
            "message": str(e),
            "program_count": 0,
            "available_program_codes": [],
            "programs": [],
        }


@tool
def program_availability(state: str) -> dict:
    """
    Retrieve NRCS conservation programs currently available
    in the specified state.
    """

    return get_program_availability(state)


if __name__ == "__main__":

    data = get_program_availability(
        state="Iowa",
        save_html=False,
        open_html=False,
    )

    print(
        json.dumps(
            data,
            indent=2,
        )
    )