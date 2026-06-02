"""Evaluation package (AI Engineer owns).

Everything needed to produce the five required evaluation traces and the
written performance commentary.

    datasets    The eval inputs, including the two out of scope cases.
    judge       LLM as judge scoring functions.
    run_traces  Runs the agent over the dataset and logs traces to LangSmith,
                including at least one trace comparing two different LLMs.

notebooks/03_evaluation_traces.ipynb drives this package.
"""
