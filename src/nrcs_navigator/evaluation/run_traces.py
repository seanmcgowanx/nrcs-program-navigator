"""Run the evaluation and produce the five LangSmith traces.

Orchestrates datasets + agent + judge to generate the graded evaluation
artifacts.

Intended responsibilities:
    - Build the agent (agent/graph.py) and run it over the eval dataset, with
      LangSmith tracing on so every run is captured as a trace.
    - Produce at least one trace that runs the same input through two different
      LLMs (premier vs. cheaper) for side by side comparison; this counts as
      one of the five traces.
    - Apply the judge from judge.py to score each run.
    - Collect the numbers the ROI calculation needs: token usage and latency
      per model, so cost vs. effectiveness can be compared in the notebook.
    - Print or return a summary the notebook can render and the human reviewer
      can comment on.

This module produces evidence; the written commentary lives in the notebook.
"""
