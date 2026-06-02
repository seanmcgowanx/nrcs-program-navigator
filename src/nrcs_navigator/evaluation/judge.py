"""LLM as judge scoring functions.

Scores agent responses for the evaluation. The rubric strongly encourages an
LLM judge over manual scoring, and also asks that a human be involved in the
evaluation process (described in the video).

Intended responsibilities:
    - Define scoring criteria: factual correctness against the regulations,
      whether the right programs were surfaced, whether payment ranges and
      deadlines are reasonable, citation quality, and correct handling of out
      of scope input.
    - Implement one or more judge functions (a judge model prompted to score
      each criterion) compatible with the LangSmith evaluation interface.
    - Return structured scores plus a short rationale so the human reviewer can
      sanity check and override the judge where needed.

The judge model itself comes from agent/llms.py.
"""
