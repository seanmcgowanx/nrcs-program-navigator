# NRCS Conservation Program Navigator

AAI-510 Final Team Project — an internal AI agent for advisors at an agricultural consulting agency, who use it to research NRCS conservation funding programs (EQIP, CSP, ACEP, RCPP) for their farmer and landowner clients.

An advisor describes a client's operation in plain language and the agent returns a ranked list of programs the client may qualify for, estimated payment ranges, applicable practice codes, and current application deadlines. The goal is to collapse a fragmented, state by state regulatory landscape into a single conversation.

> This repository is a bare bones scaffold. Every module is a stub containing only a docstring describing its purpose. No logic is implemented yet.

## Architecture at a glance

A single LLM orchestrates four tools through a ReAct reasoning loop (Reason, Act, Observe, repeat). The LLM decides which tool to call based on context; nothing is hard coded into a fixed sequence. None of the tools call an LLM themselves; they are pure data retrieval or logic.

| Tool | Type | Data source |
|------|------|-------------|
| `eligibility_screener` | RAG (pgvector search) | eCFR regulation embeddings in Postgres |
| `practice_matcher` | Live web scrape | NRCS Practice Standards index |
| `payment_estimator` | SQL query | `payment_rates` table in Postgres (from the FIPS CSV, FY2023 to FY2025) |
| `program_availability` | Live web scrape | NRCS Ranking Dates page |

Scope handling is not a tool. The agent gracefully declines out of scope requests (CRP, which is FSA administered; legal or tax advice; unrelated chit chat) and redirects the user, all via its system prompt. The system prompt also drives a short elicitation flow that gathers the client profile (state, acreage, current practices, primary resource concern; county is optional since payment data is state level) across turns before screening.

The multiple model requirement is satisfied at evaluation time by swapping the agent LLM (premier model vs. cheaper model) across traces. It is not a two LLM pipeline.

Persistence is a single PostgreSQL database with the pgvector extension. It holds three things: the `payment_rates` table, the eCFR embeddings, and the LangGraph checkpointer (agent conversation state). An optional FastAPI serving layer (`POST /chat`) wraps the agent so it can run as a service; `docker-compose.yml` brings up the database for local reproducibility.

## Repository structure

```
.
├── pyproject.toml              Poetry project + dependencies
├── docker-compose.yml          Local Postgres + pgvector for reproducibility
├── .env.example                Template for API keys and settings (copy to .env)
├── .gitignore
├── notebooks/                  Graded deliverables (run top to bottom)
│   ├── 01_data_pipeline.ipynb      Load CSV payments, fetch + embed eCFR
│   ├── 02_agent_definition.ipynb   Assemble LLM + 4 tools + ReAct loop
│   └── 03_evaluation_traces.ipynb  5 traces, LLM comparison, judge
├── src/nrcs_navigator/         Importable package (notebooks import from here)
│   ├── config.py                   Central settings, model names, paths from .env
│   ├── data/                       Data pipeline building blocks
│   │   ├── db.py                       Postgres + pgvector connection and schema
│   │   ├── fips_payments.py            Load FIPS CSV into the payment_rates table
│   │   ├── ecfr_loader.py              Fetch the 4 eCFR parts from the API, chunk by section
│   │   └── vectorstore.py              Embed eCFR chunks into the pgvector store
│   ├── tools/                      The four agent tools
│   │   ├── eligibility_screener.py     RAG over eCFR regulations
│   │   ├── practice_matcher.py         Live scrape of practice standards
│   │   ├── payment_estimator.py        Query FIPS payment table
│   │   └── program_availability.py     Live scrape: programs open by state
│   ├── agent/                      Agent assembly
│   │   ├── prompts.py                  System prompt: scope guard + elicitation
│   │   ├── llms.py                     Model factory: premier vs. cheaper, swappable
│   │   └── graph.py                    LangGraph ReAct agent wiring it all together
│   ├── serving/                    Optional FastAPI serving layer
│   │   └── app.py                      POST /chat over the agent
│   └── evaluation/                 Evaluation harness
│       ├── datasets.py                 Eval inputs, including out of scope cases
│       ├── judge.py                    LLM as judge scoring functions
│       └── run_traces.py               Run the 5 traces and log them to LangSmith
├── tests/                      Lightweight unit tests for tools and wiring
└── data/
    └── raw/                        Downloaded CSV and cached eCFR XML (git ignored)
```

Cleaned payments and embeddings are not kept on disk; they live in Postgres.

## Stack

- Agent framework: LangChain + LangGraph
- LLMs: OpenAI gpt-4o (premier) and gpt-4o-mini (cheaper leg); the model factory also supports Gemini if a Google key is set
- Tracing and evaluation: LangSmith
- Persistence: PostgreSQL + pgvector (payment_rates table, eCFR embeddings, agent checkpointer)
- Environment and dependencies: Poetry

## Setup

1. Install Poetry if you do not have it. Install it in isolation, not into a conda or project environment, so its own dependencies stay separate:

   ```bash
   pip install pipx        # if you do not already have pipx
   pipx ensurepath
   pipx install poetry
   ```

   (Alternatively, the official installer: `curl -sSL https://install.python-poetry.org | python3 -`.) Restart your shell afterward so `poetry` is on your PATH.

2. Use a Python 3.11 interpreter. The project requires `>=3.10,<3.13`, so a default 3.13 environment will not work. With conda:

   ```bash
   conda create -n nrcs python=3.11 -y
   conda activate nrcs
   poetry env use $(which python)
   ```

   Poetry builds its own virtual environment on top of that interpreter; conda only supplies the Python.

3. Install dependencies:

   ```bash
   poetry install
   ```

4. Copy the environment template and fill in your keys:

   ```bash
   cp .env.example .env
   # then edit .env with your OpenAI, Google, and LangSmith keys, plus DATABASE_URL
   ```

5. Provision PostgreSQL and point `DATABASE_URL` at it. The pgvector extension is enabled automatically by `db.init_db()` (which runs `CREATE EXTENSION IF NOT EXISTS vector`) the first time the pipeline runs, so the role in `DATABASE_URL` needs permission to create extensions. The simplest local option is the bundled compose file:

   ```bash
   docker compose up -d
   ```

   (Equivalently, a one off container: `docker run -d --name nrcs-pg -p 5432:5432 -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=nrcs_navigator pgvector/pgvector:pg16`.)

6. Register the Jupyter kernel so the notebooks use this environment:

   ```bash
   poetry run python -m ipykernel install --user --name nrcs-navigator
   ```

7. Launch the notebooks:

   ```bash
   poetry run jupyter lab
   ```

## Deliverables

| Deliverable | Notebook |
|-------------|----------|
| Data pipeline | `notebooks/01_data_pipeline.ipynb` |
| Agent definition | `notebooks/02_agent_definition.ipynb` |
| Evaluation traces | `notebooks/03_evaluation_traces.ipynb` |
| Video presentation | (recorded separately, no AI usage) |

## Scope note

NRCS programs only. CRP is administered by FSA, a separate USDA agency with separate eligibility rules, payment data, and deadlines, so it is intentionally excluded and noted as a natural v2 addition.
