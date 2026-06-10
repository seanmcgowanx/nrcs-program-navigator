"""Evaluation datasets.

Defines the example inputs the agent is scored against. The rubric requires at
least five evaluation examples, including two where the agent must gracefully
reject irrelevant input.

The examples are the source of truth here in code (so they live in git and are
reviewable). `push_to_langsmith` uploads them to a named LangSmith dataset so
runs are repeatable and comparable across models.

Each example carries an `in_scope` flag and a prose `expectations` rubric rather
than an exact reference answer: the live scrape tools (deadlines, practice codes)
change over time, so grading against fixed answer text would be brittle. The
judge in judge.py reads `expectations`; run_traces.py executes the agent over
these inputs.

Data only. Scoring lives in judge.py; execution lives in run_traces.py.
"""

from typing import Optional

from langsmith import Client

# Imported for its side effect: config.py runs load_dotenv at import time, which
# populates os.environ (including LANGCHAIN_API_KEY) so Client() can authenticate
# even when this module is used without the agent having been imported first.
from nrcs_navigator import config  # noqa: F401

# Name of the LangSmith dataset these examples are pushed to. run_traces.py reads
# from the same name so the eval is reproducible.
DATASET_NAME = "nrcs-navigator-eval"

# Each example:
#   question          the advisor's input to the agent
#   in_scope          True  -> agent should research programs and call tools
#                     False -> agent should decline + redirect and call NO tool
#   expected_programs the NRCS programs a good answer surfaces (empty if out of
#                     scope); the four high level programs only (config.PROGRAMS)
#   expected_tools    the tools the agent should call to answer well (empty for
#                     out of scope); graded as trajectory coverage, not order
#   expectations      rubric prose the judge reads to score the response
EVAL_EXAMPLES: list[dict] = [
    {
        "question": (
            "I have a client with about 300 acres of corn and soybean cropland "
            "in Iowa. They're losing topsoil to sheet and rill erosion and want "
            "help addressing it. What programs fit?"
        ),
        "in_scope": True,
        "expected_programs": ["EQIP", "CSP"],
        "expected_tools": [
            "eligibility_screener",
            "practice_matcher",
            "payment_estimator",
        ],
        "expectations": (
            "Surfaces EQIP (and reasonably CSP) for a soil erosion resource "
            "concern on cropland. Cites at least one regulation section for "
            "eligibility. Surfaces applicable conservation practice code(s) for "
            "erosion (for example cover crop or residue management) and an "
            "estimated payment range. Does not invent figures or citations."
        ),
    },
    {
        "question": (
            "A client runs a cattle operation on 500 acres of grazing land in "
            "Texas and wants to improve pasture health with rotational grazing. "
            "What practices and payments could apply?"
        ),
        "in_scope": True,
        "expected_programs": ["EQIP", "CSP"],
        "expected_tools": [
            "eligibility_screener",
            "practice_matcher",
            "payment_estimator",
        ],
        "expectations": (
            "Identifies a grazing land / livestock resource concern and surfaces "
            "EQIP and/or CSP. Returns relevant practice standard(s) such as "
            "prescribed grazing with code(s), and an estimated payment range for "
            "Texas. Cites sources for the practices and eligibility."
        ),
    },
    {
        "question": (
            "My client wants to permanently protect their wetland from future "
            "development through a conservation easement. What are their options?"
        ),
        "in_scope": True,
        "expected_programs": ["ACEP"],
        "expected_tools": ["eligibility_screener"],
        "expectations": (
            "Surfaces ACEP as the easement program. Critically, does NOT quote a "
            "payment figure for ACEP: explains ACEP is appraisal based and the "
            "client should get a valuation from their local NRCS office. May cite "
            "ACEP eligibility regulations."
        ),
    },
    {
        "question": (
            "When is the next EQIP application ranking deadline in Nebraska?"
        ),
        "in_scope": True,
        "expected_programs": ["EQIP"],
        "expected_tools": ["program_availability"],
        "expectations": (
            "Uses the program availability tool (which scrapes the NRCS Ranking "
            "Dates page for a state) to report EQIP's current ranking date in "
            "Nebraska rather than answering from memory. If the live source is "
            "unavailable, says so gracefully instead of inventing a date."
        ),
    },
    {
        "question": (
            "How does my client sign up for the Conservation Reserve Program "
            "(CRP) to take some marginal cropland out of production?"
        ),
        "in_scope": False,
        "expected_programs": [],
        "expected_tools": [],
        "expectations": (
            "Declines: CRP is administered by the FSA, not NRCS, so it is out of "
            "scope. Redirects the advisor to the client's local FSA office. Calls "
            "NO tool and does not fabricate CRP details."
        ),
    },
    {
        "question": (
            "Can you review my client's farm lease agreement and tell me whether "
            "the indemnification clause is enforceable?"
        ),
        "in_scope": False,
        "expected_programs": [],
        "expected_tools": [],
        "expectations": (
            "Declines: this is a legal question outside NRCS conservation "
            "programs. Redirects to a qualified legal professional. Calls NO tool "
            "and does not offer legal analysis."
        ),
    },
]


def push_to_langsmith(
    dataset_name: str = DATASET_NAME,
    client: Optional[Client] = None,
) -> str:
    """Create (or refresh) the LangSmith dataset from EVAL_EXAMPLES.

    Idempotent: if a dataset with this name already exists it is deleted and
    recreated, so re-running gives a clean set rather than duplicates. Returns
    the dataset id.

    The question goes in each example's inputs; in_scope, expected_programs, and
    the expectations rubric go in outputs, where the judge reads them as the
    reference for scoring.
    """
    client = client or Client()

    if client.has_dataset(dataset_name=dataset_name):
        client.delete_dataset(dataset_name=dataset_name)

    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description=(
            "NRCS Conservation Program Navigator evaluation set: in scope program "
            "research scenarios plus out of scope rejection cases."
        ),
    )

    client.create_examples(
        inputs=[{"question": ex["question"]} for ex in EVAL_EXAMPLES],
        outputs=[
            {
                "in_scope": ex["in_scope"],
                "expected_programs": ex["expected_programs"],
                "expected_tools": ex["expected_tools"],
                "expectations": ex["expectations"],
            }
            for ex in EVAL_EXAMPLES
        ],
        dataset_id=dataset.id,
    )

    return str(dataset.id)
