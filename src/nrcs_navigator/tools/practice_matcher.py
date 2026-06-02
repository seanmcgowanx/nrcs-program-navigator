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
