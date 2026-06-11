"""
Tool: practice_matcher (live web scrape)

Retrieves the current NRCS Conservation Practice Standards directly from
the NRCS website at runtime so the application always uses the latest
published practice standards and codes.

Type:
    Live web scrape

Data source:
    NRCS Conservation Practice Standards index
    https://www.nrcs.usda.gov/resources/guides-and-instructions/conservation-practice-standards

Responsibilities:
    - Load the NRCS Practice Standards page using Playwright.
    - Extract conservation practice names, practice codes, and URLs.
    - Normalize relative URLs into absolute NRCS URLs.
    - Return structured practice data for downstream matching logic.

Output:
    {
        "status": "success",
        "practice_count": 167,
        "practices": [
            {
                "name": "Conservation Cover",
                "code": "327",
                "url": "https://www.nrcs.usda.gov/..."
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

from urllib.parse import urljoin, urlparse

from nrcs_navigator import config

# The practice standards index page, configured in one place (config reads it
# from .env). BASE_URL is its scheme + host, used to resolve relative hrefs.
NRCS_URL = config.NRCS_PRACTICE_STANDARDS_URL

_parsed = urlparse(NRCS_URL)
BASE_URL = f"{_parsed.scheme}://{_parsed.netloc}"


def get_practice_standards(
    save_html: bool = False,
    open_html: bool = False,
    html_path: str = "nrcs_debug.html",
) -> dict:
    """
    Scrape the NRCS Conservation Practice Standards index and return
    the complete catalog of current conservation practice standards,
    including practice names, codes, and URLs.
    """

    try:
        with sync_playwright() as p:

            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            print("Matching practices...")

            page.goto(
                NRCS_URL,
                wait_until="networkidle",
                timeout=120000,
            )

            page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )
            page.wait_for_timeout(2000)

            html = page.content()

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

        practices = []

        for a in soup.find_all("a", href=True):

            text = " ".join(a.get_text().split())
            href = a["href"]

            if not text:
                continue

            if "/resources/guides-and-instructions/" not in href:
                continue

            match = re.search(r"\b(\d{3})\b", text)

            if not match:
                continue

            practices.append(
                {
                    "name": text.split("(")[0].strip(),
                    "code": match.group(1),
                    "url": urljoin(BASE_URL, href),
                }
            )

        return {
            "status": "success",
            "practice_count": len(practices),
            "practices": practices,
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
            "practice_count": 0,
            "practices": [],
        }


@tool
def practice_matcher() -> dict:
    """
    Retrieve the current NRCS conservation practice standards index,
    including practice names, practice codes, and source URLs.

    Returns the complete practice catalog for downstream matching
    and recommendation logic.
    """

    return get_practice_standards()


if __name__ == "__main__":

    data = get_practice_standards()

    print(
        json.dumps(
            {
                "status": data["status"],
                "practice_count": data["practice_count"],
                "sample_practices": data["practices"][:3],
            },
            indent=2,
        )
    )

    print(f"\nTotal practices: {data['practice_count']}")