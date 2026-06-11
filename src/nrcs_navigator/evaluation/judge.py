"""LLM as judge plus deterministic scoring functions.

Scores agent responses for the evaluation. The rubric strongly encourages an
LLM judge over manual scoring, and also asks that a human be involved in the
evaluation process (described in the video).

Two kinds of evaluator live here, by design:
    - Deterministic Python checks for the crisp, cheap criteria: did an out of
      scope request call zero tools, and did an in scope answer mention the
      programs we expect. No LLM call needed, so these are fast and reliable.
    - An LLM judge for the criteria that need reading the answer: fabrication,
      citation, whether the need was addressed, and correct redirects. The judge
      grades each criterion as a pass/fail boolean, not a 1-5 score: a numeric
      scale has no anchored definition of a 3 vs a 4, so it is noisy and not
      reproducible, whereas a boolean has a concrete, answerable boundary. Each
      criterion is scored and returned separately so a failure is diagnosable.

Each evaluator follows the LangSmith evaluate() interface: it takes the agent
`run` and the dataset `example`, and returns a feedback dict (or a list of them
under "results"). run.outputs is the shape produced by summarize_agent_output;
example.outputs carries in_scope, expected_programs, and expectations from
datasets.py.
"""

from typing import Optional

from pydantic import BaseModel, Field

from nrcs_navigator import config
from nrcs_navigator.agent.llms import get_model


# --- Shared shape -----------------------------------------------------------
# run_traces.py runs the agent and passes its raw message list through this so
# every evaluator reads the same simple dict instead of re-parsing messages.
def _get(msg, attr):
    """Read an attribute from a message object or a serialized dict."""
    val = getattr(msg, attr, None)
    if val is None and isinstance(msg, dict):
        val = msg.get(attr)
    return val


def summarize_agent_output(messages: list) -> dict:
    """Reduce an agent message list to {"answer", "tool_calls", "tool_results"}.

    answer is the final assistant text the advisor would see; tool_calls is the
    list of tool names the agent invoked over the whole run (order preserved);
    tool_results is one {name, status, content} per tool message, so an evaluator
    can tell whether a tool errored. Note: tools that fail "gracefully" by
    returning an error string still have status "success" (they did not raise);
    status "error" catches unhandled exceptions surfaced by the tool node.
    Handles LangChain message objects and already-serialized dicts.
    """
    answer = ""
    tool_calls: list[str] = []
    tool_results: list[dict] = []

    for msg in messages:
        msg_type = _get(msg, "type")

        calls = _get(msg, "tool_calls")
        if calls:
            for call in calls:
                name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
                if name:
                    tool_calls.append(name)

        # tool result message: capture name, status, and content
        if msg_type in ("tool", "ToolMessage"):
            tool_results.append(
                {
                    "name": _get(msg, "name"),
                    "status": _get(msg, "status") or "success",
                    "content": _get(msg, "content"),
                }
            )

        # the final assistant message with text content is the answer
        if msg_type in ("ai", "AIMessageChunk", "AIMessage"):
            content = _get(msg, "content")
            if isinstance(content, str) and content.strip():
                answer = content

    return {"answer": answer, "tool_calls": tool_calls, "tool_results": tool_results}


# --- Deterministic evaluators ----------------------------------------------
def scope_adherence(run, example) -> Optional[dict]:
    """Out of scope requests must call zero tools; in scope ones must use a tool.

    This is the crisp test of the system prompt's scope guard, so it is pure
    Python, not an LLM call.

    Only examples with a boolean in_scope are graded. An in_scope of None marks
    an ambiguous request (e.g. one that warrants a clarifying follow up), where
    the binary tool / no-tool rule does not apply; returning None skips it.
    """
    in_scope = example.outputs["in_scope"]
    if in_scope is None:
        # Ambiguous example (e.g. clarifying follow up expected); null score = skip.
        return {"key": "scope_adherence", "score": None, "comment": "n/a (ambiguous scope)"}

    tool_calls = run.outputs.get("tool_calls", [])
    used_a_tool = len(tool_calls) > 0

    if in_scope:
        passed = used_a_tool
        comment = (
            f"In scope: agent used tool(s) {tool_calls}."
            if passed
            else "In scope but the agent called no tool; it likely answered from memory."
        )
    else:
        passed = not used_a_tool
        comment = (
            "Out of scope: agent correctly declined with no tool call."
            if passed
            else f"Out of scope but the agent called tool(s) {tool_calls}; it should decline."
        )

    return {"key": "scope_adherence", "score": int(passed), "comment": comment}


def tool_trajectory(run, example) -> Optional[dict]:
    """Did the agent call the tools the example expects?

    Coverage score: fraction of expected_tools that were actually called
    (1.0 = all). Order and extra calls are not penalized here; this measures
    whether the agent reached for the right tools, not efficiency. Returns None
    for out of scope examples, which expect no tools (scope_adherence covers
    those).
    """
    expected = example.outputs.get("expected_tools") or []
    if not expected:
        # Not applicable (out of scope expects no tools); null score = skip.
        return {"key": "tool_trajectory", "score": None, "comment": "n/a (no expected tools)"}

    called = set(run.outputs.get("tool_calls", []))
    hits = [t for t in expected if t in called]
    score = len(hits) / len(expected)
    missing = [t for t in expected if t not in called]

    comment = (
        f"Called all expected tools {expected}."
        if not missing
        else f"Called {sorted(called)}; missing expected {missing}."
    )
    return {"key": "tool_trajectory", "score": score, "comment": comment}


def tools_succeeded(run, example) -> Optional[dict]:
    """Did every tool the agent called return without erroring?

    Fails if any tool message has status "error" (an unhandled exception
    surfaced by the tool node). Returns None when no tools were called, so it
    does not score out of scope declines. Caveat: tools that fail gracefully by
    returning an error string keep status "success"; those degrade the answer
    rather than erroring, and the llm_judge criteria catch the downstream effect.
    """
    results = run.outputs.get("tool_results", [])
    if not results:
        # No tools called (e.g. out of scope decline); null score = skip.
        return {"key": "tools_succeeded", "score": None, "comment": "n/a (no tools called)"}

    errored = [r["name"] for r in results if r.get("status") == "error"]
    passed = not errored
    comment = (
        "All tool calls returned successfully."
        if passed
        else f"Tool(s) errored: {errored}."
    )
    return {"key": "tools_succeeded", "score": int(passed), "comment": comment}


def program_match(run, example) -> Optional[dict]:
    """In scope: did the answer mention every program we expect?

    Score is the fraction of expected programs named in the answer (1.0 = all).
    Returns None for out of scope examples, which have no expected programs.
    """
    expected = example.outputs.get("expected_programs") or []
    if not expected:
        # Not applicable (out of scope has no expected programs); null score = skip.
        return {"key": "program_match", "score": None, "comment": "n/a (no expected programs)"}

    answer = (run.outputs.get("answer") or "").upper()
    hits = [p for p in expected if p.upper() in answer]
    score = len(hits) / len(expected)
    missing = [p for p in expected if p not in hits]

    comment = (
        f"Mentioned all expected programs {expected}."
        if not missing
        else f"Mentioned {hits}; missing {missing}."
    )
    return {"key": "program_match", "score": score, "comment": comment}


# --- LLM judge: pass/fail checklist -----------------------------------------
# Each criterion is a named pass/fail check with a concrete boundary the judge
# can answer reliably. Which checks apply depends on the example, so they are
# selected per example below rather than all run every time.
CRITERIA: dict[str, str] = {
    "no_fabrication": (
        "The answer does not state any regulation, payment figure, practice "
        "code, or deadline that is not supported by the tool results. PASS if "
        "nothing is invented; FAIL if any unsupported claim is asserted."
    ),
    "claims_cited": (
        "Every factual claim is attributed to a source, and the source matches "
        "the tool that produced it. For claims from the eligibility_screener "
        "(eligibility rules, program definitions), the source is the cited "
        "regulation section of the retrieved document (such as 7 CFR 1466.x). "
        "For claims from the other three tools (practice_matcher, "
        "payment_estimator, program_availability), the source is the link in "
        "that tool result's `source` field (the page the data came from). Note "
        "a practice's own `url` is its detail page, not the source. PASS if "
        "claims are cited this way; FAIL if material claims have no source or "
        "cite the wrong kind of source."
    ),
    "addresses_question": (
        "The answer surfaces conservation program(s) that fit the client's "
        "stated resource concern as described in the expectations. PASS if the "
        "fitting program(s) are surfaced; FAIL if it misses them or answers off "
        "target."
    ),
    "correct_redirect": (
        "The out of scope request is declined and redirected to the correct "
        "place per the expectations (for example CRP to the FSA, legal or tax to "
        "a qualified professional). PASS if it declines and redirects correctly; "
        "FAIL otherwise."
    ),
}


def _applicable_criteria(example) -> list[str]:
    """Pick which checklist items apply to this example.

    correct_redirect is an out of scope only criterion; the in scope set is
    no_fabrication / claims_cited / addresses_question. The ACEP "no payment figure"
    rule is not its own criterion: it lives in the ACEP example's expectations,
    so no_fabrication (a quoted appraisal figure is unsupported) and
    addresses_question (the right redirect to the local NRCS office) catch it.
    """
    in_scope = example.outputs["in_scope"]

    if not in_scope:
        return ["correct_redirect"]

    return ["no_fabrication", "claims_cited", "addresses_question"]


class _Check(BaseModel):
    name: str = Field(description="The criterion name being judged.")
    passed: bool = Field(description="True if the answer passes this criterion.")
    rationale: str = Field(description="One sentence justifying the pass/fail.")


class _JudgeVerdict(BaseModel):
    checks: list[_Check] = Field(
        description="One entry per requested criterion, using the exact names given."
    )


_JUDGE_PROMPT = """\
You are grading an AI assistant that helps agricultural advisors research NRCS \
conservation programs. Grade only against the criteria and expectations \
provided; do not impose outside knowledge.

Advisor question:
{question}

Expectations (what a good response should do):
{expectations}

Assistant's answer:
{answer}

Judge the answer on exactly these criteria, returning one pass/fail entry per \
criterion using the exact names given:
{criteria}\
"""


def _judge_model_name() -> str:
    """Model the judge grades with.

    Defaults to config.JUDGE_MODEL (gpt-4o-mini) so the judge does not share the
    premier agent leg's gpt-4o token budget and rate limit it. Validated against
    human annotation, so the cheaper judge is a deliberate, checked choice.
    """
    return config.JUDGE_MODEL


def llm_judge(run, example) -> dict:
    """LLM graded pass/fail checklist against the rubric.

    Selects the criteria that apply to this example, asks the judge to mark each
    pass or fail, and returns one feedback entry per criterion under "results"
    so each shows as a separate score in LangSmith.
    """
    names = _applicable_criteria(example)
    criteria_text = "\n".join(f"- {n}: {CRITERIA[n]}" for n in names)

    model = get_model(_judge_model_name()).with_structured_output(_JudgeVerdict)
    prompt = _JUDGE_PROMPT.format(
        question=example.inputs["question"],
        expectations=example.outputs["expectations"],
        answer=run.outputs.get("answer", ""),
        criteria=criteria_text,
    )
    verdict: _JudgeVerdict = model.invoke(prompt)

    # Map the judge's checks back by name so we only emit the ones we asked for.
    by_name = {c.name: c for c in verdict.checks}
    results = []
    for name in names:
        check = by_name.get(name)
        if check is None:
            # Judge omitted a requested criterion; record as a failure to surface it.
            results.append(
                {"key": name, "score": 0, "comment": "Judge did not return this criterion."}
            )
        else:
            results.append(
                {"key": name, "score": int(check.passed), "comment": check.rationale}
            )

    return {"results": results}


# Convenience: the full evaluator set run_traces.py passes to evaluate().
EVALUATORS = [
    scope_adherence,
    tool_trajectory,
    tools_succeeded,
    program_match,
    llm_judge,
]
