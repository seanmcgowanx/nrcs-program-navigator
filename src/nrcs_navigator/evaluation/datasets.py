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
#                     None  -> ambiguous (e.g. a clarifying follow up is the
#                              right move); scope_adherence skips these
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
            "program_availability"
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
            "Texas. Their primary resource concern is degraded grazing land "
            "health (overgrazed pasture and poor forage), and they want to "
            "improve it with rotational grazing. What practices and payments "
            "could apply?"
        ),
        "in_scope": True,
        "expected_programs": ["EQIP", "CSP"],
        "expected_tools": [
            "eligibility_screener",
            "practice_matcher",
            "payment_estimator",
            "program_availability"
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
            "My client in Louisiana owns 80 acres of wetland and wants to "
            "permanently protect it from future development through a "
            "conservation easement. Their primary resource concern is wetland "
            "habitat loss. What are their options and expected payouts?"
        ),
        "in_scope": True,
        "expected_programs": ["ACEP"],
        "expected_tools": ["eligibility_screener"],
        "expectations": (
            "Surfaces ACEP as the easement program. Critically, does NOT quote a "
            "payment figure for ACEP: any specific easement dollar amount is "
            "unsupported, because ACEP is appraisal based and the client should "
            "get a valuation from their local NRCS office. A good answer redirects "
            "to the local NRCS office for valuation. May cite ACEP eligibility "
            "regulations."
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
            "Nebraska. If the live source is "
            "unavailable, says so gracefully instead of inventing a date."
        ),
    },
    {
        "question": (
            "A group of landowners in the Chesapeake Bay watershed"
            "want to coordinate on a partnership led conservation project to "
            "improve water quality. Is there an NRCS program built for that kind "
            "of partnership effort?"
        ),
        "in_scope": True,
        "expected_programs": ["RCPP"],
        "expected_tools": ["eligibility_screener"],
        "expectations": (
            "Surfaces RCPP as the partnership / watershed program (NRCS works "
            "with partners on locally led projects). Cites RCPP eligibility "
            "regulation(s). May note RCPP delivers assistance through programs "
            "like EQIP and CSP. Does not invent figures or citations."
        ),
    },
    {
        "question": (
            "California"
        ),
        # None = ambiguous: too underspecified to be in or out of scope. The
        # agent should ask a clarifying follow up (no tool, no decline), so the
        # binary scope_adherence check does not apply and skips this example.
        "in_scope": None,
        "expected_programs": [],
        "expected_tools": [],
        "expectations": (
            "Responds with a follow up question asking about the conservation "
            "project issues "
        ),
    },
    {
        "question": (
            "What is the typical EQIP payment for cover crop (practice code 340) "
            "in Iowa?"
        ),
        "in_scope": True,
        "expected_programs": ["EQIP"],
        "expected_tools": ["payment_estimator"],
        "expectations": (
            "Uses the payment estimator to report a payment range (low, typical, "
            "high) for the EQIP cover crop practice in Iowa from the historical "
            "payment data, with the source noted. Does not invent a figure; if no "
            "matching rate exists, says so clearly."
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
    {
        "question": (
            "My client donated a conservation easement last year. How should they "
            "claim the federal tax deduction for it on their return?"
        ),
        "in_scope": False,
        "expected_programs": [],
        "expected_tools": [],
        "expectations": (
            "Declines: tax treatment is outside NRCS conservation program scope. "
            "Redirects to a qualified tax professional. Calls NO tool and does "
            "not offer tax advice."
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
