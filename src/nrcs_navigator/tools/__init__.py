"""Agent tools package (AI Engineer owns).

The five tools the LLM can call during the ReAct loop. None of these tools
call an LLM themselves; they are pure data retrieval or logic. The LLM reads
their output and decides what to do next.

    eligibility_screener   RAG over eCFR regulations (vector search).
    practice_matcher       Live scrape of the NRCS Practice Standards index.
    payment_estimator      Query the cleaned FIPS payment table.
    deadline_lookup        Live scrape of the NRCS Ranking Dates page.
    out_of_scope_handler   Politely decline irrelevant input and redirect.

Each module is expected to expose a LangChain tool object (name, description,
args schema) that agent/graph.py binds to the model.
"""
