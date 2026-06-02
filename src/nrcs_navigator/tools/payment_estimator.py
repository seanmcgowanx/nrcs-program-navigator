"""Tool: payment_estimator (table query).

Returns estimated payment ranges for a given practice code, program, and state
by querying the payment_rates table prepared by the data pipeline.

Type: SQL query (no live network, no LLM).
Data source: payment_rates table in Postgres (loaded by data/fips_payments.py).

Intended responsibilities:
    - Accept practice code(s), program, and state from the agent.
    - Look up matching payment rates across FY2023 to FY2025 and summarize a
      range (low, typical, high).
    - For ACEP requests, return the correct answer that ACEP payments are
      appraisal based and the farmer should contact their local NRCS office;
      do not fabricate a number.
    - Return a clear message when no matching rate exists.

Exposes a LangChain tool object for agent/graph.py to bind.
"""
