"""Tool: eligibility_screener (RAG over eCFR regulations).

Given a description of a farmer's operation, retrieves the most relevant
eligibility provisions from the eCFR vector store and returns them so the agent
can reason about which programs the farmer may qualify for.

Type: retrieval augmented generation via vector search.
Data source: pgvector store built by data/vectorstore.py from the four eCFR
parts (EQIP, ACEP, CSP, RCPP) fetched from the eCFR API.

The tool retrieves and returns regulation excerpts with citations; it does not
decide eligibility. Keeping the judgment in the model is deliberate (tools
return data, the model reasons). ACEP eligibility is screened here even though
ACEP has no payment table; payment questions are redirected by payment_estimator.

Retrieval is deduplicated by section: a long regulation section is split across
several chunks, so a raw similarity search can return multiple chunks of the
same section and crowd out other relevant provisions. We over-fetch candidates,
keep the best-ranked chunk per distinct section, and return the top distinct
sections, so the model sees a breadth of provisions rather than repeats of one.

Exposes a LangChain tool object (eligibility_screener) for agent/graph.py to bind.
"""

from langchain_core.tools import tool

from nrcs_navigator import config
from nrcs_navigator.data import vectorstore

# The four high-level programs, from the single source of truth in config, used
# to validate the optional scope argument the model may pass.
VALID_PROGRAMS = set(config.PROGRAMS)

# Over-fetch chunks, then collapse to distinct sections. CANDIDATE_CHUNKS is the
# raw vector hits to consider; TOP_SECTIONS is how many distinct sections to
# return after deduplication.
CANDIDATE_CHUNKS = 12
TOP_SECTIONS = 4


@tool
def eligibility_screener(query: str, program: str | None = None) -> str:
    """Look up NRCS conservation program eligibility rules from federal regulations.

    Searches the eCFR regulations for EQIP, ACEP, CSP, and RCPP and returns the
    most relevant excerpts (eligibility provisions, definitions, program
    requirements) with their CFR citations. Reason over the returned text to
    judge which programs a farmer may qualify for; this tool retrieves the
    regulations, it does not decide eligibility.

    Args:
        query: A plain-language description of the farmer's operation or
            question (commodity, acreage, land type, land tenure, conservation
            goal, state).
        program: Optional. One of "EQIP", "ACEP", "CSP", or "RCPP" to limit the
            search to that program's regulations. Omit to search all four.

    Returns:
        Up to four distinct regulation sections, each prefixed with its citation
        and section heading, or a message if nothing relevant was found.
    """

    print("Screening eligibility...")

    program = program.strip().upper() if program else None
    if program not in VALID_PROGRAMS:
        program = None  # ignore an unrecognized program rather than return nothing

    hits = vectorstore.similarity_search(query, k=CANDIDATE_CHUNKS, program=program)
    if not hits:
        return "No matching regulation sections found."

    # Keep the best-ranked chunk per distinct (part, section); hits are already
    # ordered by similarity, so the first chunk seen for a section is its most
    # relevant one. Stop once we have TOP_SECTIONS distinct sections.
    seen: set[tuple[str, str]] = set()
    selected = []
    for hit in hits:
        key = (hit.metadata["part"], hit.metadata["section"])
        if key in seen:
            continue
        seen.add(key)
        selected.append(hit)
        if len(selected) == TOP_SECTIONS:
            break

    blocks = [
        f"[{hit.metadata['citation']}] {hit.metadata['heading']} "
        f"({hit.metadata['program']})\n{hit.page_content}"
        for hit in selected
    ]
    return "\n\n".join(blocks)
