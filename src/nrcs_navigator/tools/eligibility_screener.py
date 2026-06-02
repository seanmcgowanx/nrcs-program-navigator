"""Tool: eligibility_screener (RAG over eCFR regulations).

Given a description of a farmer's operation, retrieves the most relevant
eligibility provisions from the eCFR vector index and returns them so the
agent can reason about which programs the farmer may qualify for.

Type: retrieval augmented generation via vector search.
Data source: pgvector store built by data/vectorstore.py from the four eCFR PDFs.

Intended responsibilities:
    - Accept a natural language query about the operation (commodity, acreage,
      land type, conservation goals, state).
    - Run similarity_search against the vector store.
    - Return the matching regulation excerpts with citations (CFR part,
      program) for the agent to weigh.

This is where ACEP eligibility gets screened even though ACEP has no payment
table; payment questions are redirected by payment_estimator.

Exposes a LangChain tool object for agent/graph.py to bind.
"""
