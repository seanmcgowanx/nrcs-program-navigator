"""Unit tests for the four agent tools.

Each tool is pure data retrieval or logic, so it can be tested without an LLM.
Planned coverage:
    - payment_estimator returns a sensible range for a known practice code and
      redirects (does not invent a number) for ACEP.
    - eligibility_screener returns relevant chunks for an in scope query.
    - practice_matcher and deadline_lookup parse a saved sample of the scraped
      page (fixture) and fail gracefully on a bad response.

Out of scope handling is not a tool, so it is covered in test_agent.py
(the system prompt makes the agent decline), not here.

No tests implemented yet; this is a scaffold.
"""
