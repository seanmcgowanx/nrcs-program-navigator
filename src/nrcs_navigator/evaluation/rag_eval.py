"""Retrieval evaluation for the eligibility_screener RAG component.

This is a *component* eval, separate from the agent harness in run_traces.py. It
tests the retriever directly (vectorstore.similarity_search) rather than through
the agent, so a poor result is attributable to retrieval, not to the model's
reasoning. The agent eval answers "did the agent give a good answer"; this
answers "does the right regulation come back for a query".

Method: each example is a natural language question paired with the gold CFR
section that answers it. The gold citations are grounded in the section headings
(true structure), not in what the retriever happens to return, so they are an
independent reference. For each query we retrieve the top sections and check:
    - hit@k: is the gold citation in the top k retrieved sections (recall, since
      each query has one gold section)
    - reciprocal rank: 1 / rank of the gold section, 0 if not found; mean over
      examples is MRR, which rewards ranking the gold section higher

Run `evaluate()` for the summary; `per_example()` for the row by row detail.
"""

from nrcs_navigator.data import vectorstore

# Each example: a question and the single gold CFR section that answers it
# (chosen from the section headings, so it is ground truth independent of the
# retriever). program is the metadata filter to pass when evaluating the filtered
# retrieval path.
# Questions are deliberately paraphrased to avoid the gold section's heading
# vocabulary, so this tests semantic retrieval (does the meaning match the right
# regulation), not keyword overlap with the title.
RAG_EXAMPLES: list[dict] = [
    {
        "question": "Does my client's operation qualify to take part in the Conservation Stewardship Program, and who is allowed to apply?",
        "gold_citation": "7 CFR 1470.6",
        "program": "CSP",
    },
    {
        "question": "How is the amount of money a Conservation Stewardship Program participant receives each year worked out?",
        "gold_citation": "7 CFR 1470.24",
        "program": "CSP",
    },
    {
        "question": "When joining the Conservation Stewardship Program, what written document describing what the operator will do on the land must be prepared?",
        "gold_citation": "7 CFR 1470.22",
        "program": "CSP",
    },
    {
        "question": "After a Conservation Stewardship Program agreement reaches its end, can the producer extend it for another term?",
        "gold_citation": "7 CFR 1470.26",
        "program": "CSP",
    },
    {
        "question": "Under EQIP, how does NRCS set the dollar amount a producer gets for installing a given practice?",
        "gold_citation": "7 CFR 1466.23",
        "program": "EQIP",
    },
    {
        "question": "What countrywide resource concerns is EQIP meant to focus on?",
        "gold_citation": "7 CFR 1466.4",
        "program": "EQIP",
    },
    {
        "question": "When entering an EQIP contract, what document listing the practices and the schedule for installing them must the producer develop?",
        "gold_citation": "7 CFR 1466.7",
        "program": "EQIP",
    },
    {
        "question": "Through EQIP, how can an organization receive money to test promising new conservation technologies?",
        "gold_citation": "7 CFR 1466.32",
        "program": "EQIP",
    },
    {
        "question": "If a farmer sells the development rights on their farmland through ACEP, how is the dollar value they receive figured out?",
        "gold_citation": "7 CFR 1468.24",
        "program": "ACEP",
    },
    {
        "question": "Under ACEP, can a partner buy land, place a permanent restriction on it, and then sell it on to a farmer?",
        "gold_citation": "7 CFR 1468.27",
        "program": "ACEP",
    },
    {
        "question": "In RCPP, what formal arrangement does NRCS sign with the organizations leading a project?",
        "gold_citation": "7 CFR 1464.22",
        "program": "RCPP",
    },
    {
        "question": "How does an organization put forward a new project idea to NRCS to be considered under RCPP?",
        "gold_citation": "7 CFR 1464.20",
        "program": "RCPP",
    },
]


def _retrieved_citations(query: str, k: int, program: str | None) -> list[str]:
    """Top retrieved CFR citations for a query, deduped, in rank order.

    Over-fetches chunks then dedupes to distinct sections (a section can produce
    several chunks), so rank reflects distinct sections. Truncates to k.
    """
    docs = vectorstore.similarity_search(query, k=k * 4, program=program)
    ordered: list[str] = []
    for d in docs:
        cit = d.metadata.get("citation")
        if cit and cit not in ordered:
            ordered.append(cit)
    return ordered[:k]


def per_example(k: int = 5, use_program_filter: bool = False):
    """Row by row retrieval result: gold rank and hit for each example.

    use_program_filter passes the example's program as a metadata filter (the
    scoped retrieval path), so you can compare filtered vs. unfiltered recall.
    """
    import pandas as pd

    rows = []
    for ex in RAG_EXAMPLES:
        program = ex["program"] if use_program_filter else None
        citations = _retrieved_citations(ex["question"], k, program)
        gold = ex["gold_citation"]
        rank = citations.index(gold) + 1 if gold in citations else None
        rows.append(
            {
                "question": ex["question"][:55],
                "program": ex["program"],
                "gold": gold,
                "rank": rank,
                "hit": rank is not None,
                "reciprocal_rank": (1.0 / rank) if rank else 0.0,
            }
        )
    return pd.DataFrame(rows)


def evaluate(k_values=(1, 3, 5), use_program_filter: bool = False):
    """Summary retrieval metrics: hit@k for each k, plus MRR.

    hit@k is computed at the largest k via per_example, then thresholded for each
    smaller k from the gold rank. MRR is the mean reciprocal rank across examples.
    Returns a one row DataFrame.
    """
    import pandas as pd

    max_k = max(k_values)
    detail = per_example(k=max_k, use_program_filter=use_program_filter)

    summary = {}
    for k in sorted(k_values):
        hits_at_k = detail["rank"].apply(lambda r: bool(r is not None and r <= k))
        summary[f"hit@{k}"] = hits_at_k.mean()
    summary["MRR"] = detail["reciprocal_rank"].mean()
    summary["n"] = len(detail)

    label = "filtered" if use_program_filter else "unfiltered"
    return pd.DataFrame({label: summary}).T
