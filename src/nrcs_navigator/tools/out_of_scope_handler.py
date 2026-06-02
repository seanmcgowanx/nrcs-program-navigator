"""Tool: out_of_scope_handler (logic only).

Lets the agent gracefully decline input that falls outside NRCS conservation
program guidance and redirect the user, instead of hallucinating an answer.
This is what satisfies the rubric requirement to gracefully handle out of
scope queries, and supplies the two required graceful rejection examples.

Type: logic only. No data retrieval, no network, no LLM.

Intended responsibilities:
    - Provide a structured polite decline the agent can return for irrelevant
      requests (for example: unrelated chit chat, CRP questions which are FSA
      administered, legal or tax advice, anything off topic).
    - Optionally redirect: point the user to the correct resource (for CRP,
      the local FSA office; for general help, the local NRCS service center).
    - Keep the message tone helpful so the rejection still feels useful.

Exposes a LangChain tool object for agent/graph.py to bind.
"""
