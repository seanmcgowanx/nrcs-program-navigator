"""Tool: deadline_lookup (live web scrape).

Returns current application and ranking deadlines for the relevant programs by
scraping the live NRCS Ranking Dates page at query time, so deadlines are
never stale.

Type: live web scrape.
Data source: NRCS Ranking Dates page (URL in config / .env).

Intended responsibilities:
    - Fetch the ranking dates page (requests).
    - Parse it (beautifulsoup) into program, state, and sign up / ranking date.
    - Filter to the program(s) and state the agent asks about and return the
      next applicable deadline(s).
    - Handle network or parsing failures gracefully with a clear message.

Exposes a LangChain tool object for agent/graph.py to bind.
"""
