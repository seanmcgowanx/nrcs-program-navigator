"""Evaluation datasets.

Defines the example inputs the agent is scored against. The rubric requires at
least five evaluation examples, including two where the agent must gracefully
reject irrelevant input.

Intended contents:
    - A set of realistic in scope farmer scenarios (varied commodity, acreage,
      state, and goals) that exercise all five tools.
    - At least two out of scope inputs (for example a CRP question, which is
      FSA administered, and an unrelated request) to test graceful rejection.
    - Optional reference answers or rubric notes per example for the judge.
    - A helper to push this set to a LangSmith dataset so runs are repeatable.

Data only. Scoring lives in judge.py; execution lives in run_traces.py.
"""
