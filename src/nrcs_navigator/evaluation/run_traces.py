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


def _to_bit(score):
    """Normalize a feedback score to a 0/1 pass bit; None stays None."""
    if score is None:
        return None
    return int(round(float(score)))


def _cohen_kappa(pairs: list) -> float:
    """Cohen's kappa for a list of (human_bit, judge_bit) pairs.

    Corrects raw agreement for the agreement expected by chance. Returns nan when
    undefined (no pairs, or both raters never vary).
    """
    n = len(pairs)
    if n == 0:
        return float("nan")
    agree = sum(1 for h, j in pairs if h == j)
    po = agree / n
    h_yes = sum(h for h, _ in pairs) / n
    j_yes = sum(j for _, j in pairs) / n
    pe = h_yes * j_yes + (1 - h_yes) * (1 - j_yes)
    if pe == 1:
        return float("nan")
    return (po - pe) / (1 - pe)


def judge_human_agreement(
    experiment_names,
    client=None,
    human_source_types: tuple = ("app",),
    criteria=None,
):
    """Per criterion agreement between the LLM judge and human annotations.

    Validates the judge: for every run the human annotated in a LangSmith queue,
    line up the human's pass/fail against the judge's on the same criterion and
    report the match rate. High agreement means the judge can be trusted to scale
    to runs the human did not label; low agreement flags a criterion whose
    definition in judge.CRITERIA needs sharpening.

    Reads feedback from the given experiment session name(s). Feedback whose
    source type is in human_source_types (LangSmith app annotations) is the human
    label; any other source (the evaluators) is the judge. Only runs/criteria
    scored by both are compared. Returns a DataFrame: criterion, agreement, kappa,
    n. Empty until annotations exist.
    """
    from collections import defaultdict

    import pandas as pd
    from langsmith import Client

    client = client or Client()
    if isinstance(experiment_names, str):
        experiment_names = [experiment_names]

    run_ids = []
    for name in experiment_names:
        run_ids += [r.id for r in client.list_runs(project_name=name, is_root=True)]
    if not run_ids:
        return pd.DataFrame(columns=["criterion", "agreement", "kappa", "n"])

    human, judge = {}, {}
    for fb in client.list_feedback(run_ids=run_ids):
        source_type = getattr(getattr(fb, "feedback_source", None), "type", None)
        key = (fb.run_id, fb.key)
        if source_type in human_source_types:
            human[key] = fb.score
        else:
            judge[key] = fb.score

    pairs_by_criterion = defaultdict(list)
    for (run_id, crit), h_score in human.items():
        if criteria and crit not in criteria:
            continue
        if (run_id, crit) not in judge:
            continue
        h_bit, j_bit = _to_bit(h_score), _to_bit(judge[(run_id, crit)])
        if h_bit is None or j_bit is None:
            continue
        pairs_by_criterion[crit].append((h_bit, j_bit))

    rows = []
    for crit, pairs in sorted(pairs_by_criterion.items()):
        n = len(pairs)
        agreement = sum(1 for h, j in pairs if h == j) / n if n else float("nan")
        rows.append(
            {
                "criterion": crit,
                "agreement": agreement,
                "kappa": _cohen_kappa(pairs),
                "n": n,
            }
        )
    return pd.DataFrame(rows)


def roi_table(results_by_model: dict, client=None):
    """Per model averages for latency, tokens, and cost, read from LangSmith.

    The in-memory experiment frame does not always carry latency and cost, so
    this reads the root run of each experiment session directly: LangSmith rolls
    token usage and dollar cost up to the root (the agent invocation), and
    start/end times give latency. The judge's calls are separate evaluator runs,
    not under these roots, so this is the agent's cost, which is what the ROI
    argument needs. Returns a DataFrame with one column per model.
    """
    import pandas as pd
    from langsmith import Client

    client = client or Client()
    cols = {}
    for model, exp in results_by_model.items():
        name = getattr(exp, "experiment_name", None)
        if name is None:
            continue
        latencies, tokens, costs = [], [], []
        for run in client.list_runs(project_name=name, is_root=True):
            if run.start_time and run.end_time:
                latencies.append((run.end_time - run.start_time).total_seconds())
            if run.total_tokens is not None:
                tokens.append(run.total_tokens)
            if run.total_cost is not None:
                costs.append(float(run.total_cost))

        col = {}
        if latencies:
            col["avg_latency_s"] = sum(latencies) / len(latencies)
        if tokens:
            col["avg_total_tokens"] = sum(tokens) / len(tokens)
        if costs:
            col["avg_cost_usd"] = sum(costs) / len(costs)
            col["total_cost_usd"] = sum(costs)
        cols[model] = col

    return pd.DataFrame(cols)


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
