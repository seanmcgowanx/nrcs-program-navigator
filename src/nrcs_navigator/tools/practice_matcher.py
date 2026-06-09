"""Tool: practice_matcher (live web scrape).

Maps a farmer's stated conservation goals to applicable NRCS practice
standards and their codes by scraping the live NRCS Practice Standards index
at query time, so results reflect the current published standards.

Type: live web scrape.
Data source: NRCS Practice Standards index (URL in config / .env).

Intended responsibilities:
    - Fetch the practice standards index (requests).
    - Parse it (beautifulsoup) into practice name, practice code, and summary.
    - Match against the agent supplied goals or keywords and return the most
      relevant practices with codes.
    - Handle network or parsing failures gracefully and return a clear error
      message the agent can recover from rather than raising.

Exposes a LangChain tool object for agent/graph.py to bind.
"""

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import re
import os
import webbrowser
from urllib.parse import urljoin

NRCS_URL = "https://www.nrcs.usda.gov/resources/guides-and-instructions/conservation-practice-standards"


def fetch(save_html=False, open_html=False, html_path="nrcs_debug.html"):

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Navigating...")

        page.goto(
            NRCS_URL,
            wait_until="networkidle",
            timeout=120000
        )

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)

        html = page.content()

        print("HTML length:", len(html))

        # Optional: Save HTML Locally
        if save_html:

            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)

            print(f"Saved HTML → {html_path}")

            if open_html:
                webbrowser.open(f"file://{os.path.abspath(html_path)}")

        browser.close()

    soup = BeautifulSoup(html, "html.parser")

    all_links = []

    for a in soup.find_all("a", href=True):

        text = " ".join(a.get_text().split())

        if text:
            all_links.append({
                "text": text,
                "href": a["href"]
            })

    practices = []

    for item in all_links:

        text = item["text"]
        href = item["href"]

        if "/resources/guides-and-instructions/" not in href:
            continue

        match = re.search(r"\b(\d{3})\b", text)

        if not match:
            continue

        BASE_URL = "https://www.nrcs.usda.gov"

        practices.append({
            "name": text.split("(")[0].strip(),
            "code": match.group(1),
            "url": urljoin(BASE_URL, href)
        })

    return practices


def print_formatted(practices):

    print("\n" + "=" * 60)
    print("NRCS PRACTICE STANDARDS")
    print("=" * 60 + "\n")

    for p in practices:

        print(f"TEXT: {p['name']}")
        print(f"CODE: {p['code']}")
        print(f"URL:  {p['url']}")
        print("-" * 60)


if __name__ == "__main__":

    # HTML saving optional (default OFF)
    data = fetch(save_html=False, open_html=False)

    print_formatted(data)

    print(f"\nTotal practices: {len(data)}")