# CLAUDE.md

Guidance for Claude (and any AI assistant) working in this repository. Read this first, then the linked docs before making changes.

## What this project is

The NRCS Conservation Program Navigator is the AAI-510 final team project: an AI agent that helps farmers identify, evaluate, and apply for NRCS conservation funding programs (EQIP, CSP, ACEP, RCPP). A farmer describes their operation in plain language; the agent returns a ranked list of programs they qualify for, estimated payment ranges, applicable practice codes, and current application deadlines.

The repository is currently a bare scaffold. Every module is a stub containing only a docstring describing its purpose. No logic is implemented yet. When implementing, fill in the stubs; do not change the agreed architecture without reason.

## Reference docs

- [docs/architecture.md](docs/architecture.md) — the authoritative architecture. The agent, the four tools, scope handling, persistence, state schema, evaluation, scope boundary, and open decisions. Read this before touching agent or data code.
- [README.md](README.md) — setup instructions (Poetry, Python 3.11, database) and the repository tour.

## Architecture in brief

A single LLM orchestrates four tools through a LangGraph ReAct loop. The model chooses tools based on context; nothing is hard coded into a sequence. The four tools are `eligibility_screener` (RAG over eCFR embeddings), `practice_matcher` (live scrape), `payment_estimator` (SQL on `payment_rates`), and `deadline_lookup` (live scrape). See [docs/architecture.md](docs/architecture.md) for the full picture.

## Load bearing constraints

These are easy to get wrong and expensive to fix later. Honor them:

- **Four tools, not five.** Scope handling is in the system prompt (`agent/prompts.py`), not a tool. There is no `out_of_scope_handler`. Out of scope requests get a polite decline plus redirect, no tool call.
- **One database for three jobs.** A single PostgreSQL plus pgvector instance holds the `payment_rates` table, the eCFR embeddings, and the LangGraph checkpointer. Do not introduce a second store (no FAISS, no separate vector DB).
- **Multiple models at evaluation time only.** The premier versus cheaper comparison is done by swapping the agent LLM across traces via the `model_name` parameter to `build_agent`. It is not a two LLM pipeline. Tools never call an LLM.
- **Tools return data, the model reasons.** Each tool is pure retrieval or logic. Keep reasoning in the model, not the tools.
- **NRCS only.** EQIP, CSP, ACEP, RCPP. CRP is FSA administered and intentionally excluded; the agent redirects CRP questions to the local FSA office. ACEP is appraisal based, so `payment_estimator` redirects to the local NRCS office rather than quoting a rate.
- **Embedding model is fixed, not swappable.** OpenAI `text-embedding-3-small` (1536 dimensions), a constant in `config.py`. Unlike the two agent LLMs (swapped via env for the evaluation), the embedding model is locked: the stored pgvector embeddings are its output, so changing it means embedding every chunk again. Do not move it to `.env`.
- **eCFR comes from the API as XML, not PDFs.** The four parts are fetched from the eCFR versioner API at a pinned version date. Chunks align to whole sections (one chunk per section) and carry their citation (for example 7 CFR 1466.6). Changed from the original PDF plan so section structure and citations are reliable. See the decisions section of [docs/architecture.md](docs/architecture.md).

## Repository layout

```
src/nrcs_navigator/
  config.py            Central settings, model names, paths, read from .env
  data/                Data pipeline (Data Engineer)
    db.py                Postgres + pgvector connection and schema (DDL)
    fips_payments.py     Load FIPS CSV into payment_rates
    ecfr_loader.py       Fetch the four eCFR parts from the API, parse XML, chunk by section
    vectorstore.py       Embed eCFR chunks into the pgvector store
  tools/               The four agent tools (AI Engineer)
  agent/               Agent assembly (AI Engineer)
    prompts.py           System prompt: scope guard + elicitation flow
    llms.py              Model factory: premier vs cheaper, swappable
    graph.py             LangGraph ReAct wiring + Postgres checkpointer
  serving/             Optional FastAPI layer exposing POST /chat
  evaluation/          Eval datasets, LLM as judge, trace runner
notebooks/             Graded deliverables (01 data, 02 agent, 03 evaluation)
tests/                 Lightweight unit tests
docs/                  Architecture and workflow references
data/raw/              Downloaded CSV and cached eCFR XML (git ignored)
```

The notebooks are the graded deliverables and import from the `src` package, so keep logic in `src` and keep the notebooks thin.

## Development environment

- **Dependencies: Poetry.** Install Poetry in isolation (pipx or the official installer), not with `pip install` into a conda or project environment.
- **Python 3.11.** The project requires `>=3.10,<3.13`; a default 3.13 environment will not resolve. Use a dedicated interpreter (for example `conda create -n nrcs python=3.11`) and point Poetry at it with `poetry env use`.
- Commit `poetry.lock` and the schema so collaborators reproduce the exact setup on clone.
- Run commands inside the Poetry environment, for example `poetry run jupyter lab`, `poetry run pytest`.

Full setup steps are in [README.md](README.md).

## Conventions

- Keep secrets in `.env` (never committed). Read settings through `config.py`, not `os.environ` directly.
- Persistence lives in Postgres, not on disk. Cleaned payments and embeddings are not kept as files.
- Prefer prose docstrings on stubs that describe intent, matching the existing scaffold style.
- Avoid hyphenated compound words in written deliverables and docs.
