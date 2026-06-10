"""Run the evaluation and produce the LangSmith traces.

Orchestrates datasets + agent + judge to generate the graded evaluation
artifacts. This is the caller that finally supplies `run` and `example` to the
evaluators in judge.py: LangSmith's evaluate() runs the target over every
dataset example, wraps each result as a run, and invokes each evaluator as
evaluator(run, example).

Flow:
    - Build the agent (agent/graph.py) on a given model.
    - Define a target that invokes the agent on an example's question and
      reduces the result to the {answer, tool_calls, tool_results} shape the
      evaluators read (via judge.summarize_agent_output), plus token usage so
      the notebook can compare cost.
    - evaluate() runs the target over the dataset with tracing on (every run is
      captured as a LangSmith trace) and applies judge.EVALUATORS.
    - run_comparison runs the same dataset through the premier and the cheaper
      model so the side by side comparison is one call; this is the multiple
      model requirement.

The numbers for the ROI discussion (token usage, latency) come from the traces;
summarize_results pulls per model averages the notebook can render. The written
commentary lives in the notebook.
"""

import uuid

from langsmith import evaluate

from nrcs_navigator import config
from nrcs_navigator.agent.graph import build_agent
from nrcs_navigator.evaluation import judge
from nrcs_navigator.evaluation.datasets import DATASET_NAME


def _total_tokens(messages: list) -> int:
    """Sum total tokens across the run's messages.

    LangChain attaches usage_metadata to assistant messages; missing on tool or
    human messages, so we sum what is present.
    """
    total = 0
    for msg in messages:
        usage = getattr(msg, "usage_metadata", None)
        if isinstance(usage, dict):
            total += usage.get("total_tokens", 0)
    return total


def _make_target(model_name: str):
    """Build the agent once and return a target callable for evaluate().

    The target receives an example's inputs dict and returns the run outputs the
    evaluators consume. Each call uses a fresh thread_id so the checkpointer does
    not bleed conversation state between examples.
    """
    agent = build_agent(model_name)

    def target(inputs: dict) -> dict:
        question = inputs["question"]
        result = agent.invoke(
            {"messages": [("user", question)]},
            config={"configurable": {"thread_id": str(uuid.uuid4())}},
        )
        messages = result["messages"]
        summary = judge.summarize_agent_output(messages)
        summary["total_tokens"] = _total_tokens(messages)
        return summary

    return target


def run_for_model(
    model_name: str,
    dataset_name: str = DATASET_NAME,
    experiment_prefix: str | None = None,
):
    """Evaluate one model over the dataset and return the ExperimentResults.

    Runs serially (max_concurrency=1): the program_availability tool drives a
    headless browser via Playwright, which is not safe to fan out, and each
    agent holds one Postgres checkpointer connection.
    """
    target = _make_target(model_name)
    return evaluate(
        target,
        data=dataset_name,
        evaluators=judge.EVALUATORS,
        experiment_prefix=experiment_prefix or f"nrcs-{model_name}",
        metadata={"model": model_name},
        max_concurrency=1,
    )


def run_comparison(models: list[str] | None = None) -> dict:
    """Run the premier and cheaper models over the dataset for comparison.

    Returns {model_name: ExperimentResults}. Defaults to the two configured
    models so the notebook gets the side by side comparison in one call.
    """
    models = models or [config.PREMIER_MODEL, config.CHEAP_MODEL]
    return {model: run_for_model(model) for model in models}


def summarize_results(results_by_model: dict):
    """Per model mean of every numeric feedback score, as a DataFrame.

    Reads each ExperimentResults into a pandas frame, keeps the feedback columns
    (LangSmith prefixes them "feedback.") plus token usage, and averages across
    examples. The notebook renders this for the cost vs. effectiveness writeup.
    """
    import pandas as pd

    rows = {}
    for model, results in results_by_model.items():
        df = results.to_pandas()
        feedback_cols = [c for c in df.columns if c.startswith("feedback.")]
        means = df[feedback_cols].mean(numeric_only=True)
        means.index = [c.replace("feedback.", "") for c in means.index]

        # token usage lives under the target outputs column
        token_col = next(
            (c for c in df.columns if c.endswith("total_tokens")), None
        )
        if token_col is not None:
            means["avg_total_tokens"] = df[token_col].mean()

        rows[model] = means

    return pd.DataFrame(rows)
