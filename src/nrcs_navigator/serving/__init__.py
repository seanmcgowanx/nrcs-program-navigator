"""Serving layer package (optional for grading).

Wraps the LangGraph agent in a small FastAPI service so it can be exercised
as an HTTP API (POST /chat) in addition to the graded notebooks. This is the
deployment shape described in the architecture spec; it is not required for
the rubric but demonstrates the agent running as a service.
"""
