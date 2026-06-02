# Architecture

This is the authoritative reference for how the NRCS Conservation Program Navigator is put together. The architecture is locked; when code and this document disagree, fix the code to match this document, or change this document deliberately and note why.

## One sentence

A single LLM orchestrates four tools through a LangGraph ReAct loop, persists everything in one PostgreSQL plus pgvector database, and is compared across two models at evaluation time.

## The agent

The agent is a single LLM running a Reason, Act, Observe loop (LangChain plus LangGraph). The model decides which tool to call at each step based on context. Nothing is hard coded into a fixed sequence. None of the tools call an LLM themselves; they are pure data retrieval or logic, and the model reads their output and decides what to do next.

The same agent code is built on two different models so the evaluation can compare them. The model name is a parameter to `build_agent`, so swapping a premier model for a cheaper model needs no change to tool or graph code.

## The four tools

| Tool | Type | Data source |
|------|------|-------------|
| `eligibility_screener` | RAG (pgvector search) | eCFR regulation embeddings in Postgres |
| `practice_matcher` | Live web scrape | NRCS Practice Standards index |
| `payment_estimator` | SQL query | `payment_rates` table in Postgres (FIPS CSV, FY2023 to FY2025) |
| `deadline_lookup` | Live web scrape | NRCS Ranking Dates page |

`payment_estimator` does not invent a number for ACEP, which is appraisal based; it redirects the user to the local NRCS office. The two scrape tools talk to live NRCS pages and never touch the database.

## Scope handling is not a tool

The agent declines out of scope requests through its system prompt, not a dedicated function. In scope requests (NRCS program guidance) drive the agent toward its tools. Out of scope requests get a polite decline plus a redirect, with no tool call and no guessing:

- CRP questions are administered by FSA, a separate agency, so redirect to the local FSA office.
- Legal or tax advice and unrelated chit chat redirect to the local NRCS service center.

This is what satisfies the rubric requirement to gracefully handle out of scope queries, and it supplies the required graceful rejection examples in the evaluation set.

## Elicitation flow

The system prompt also drives a short multi turn flow. Before screening eligibility, the agent gathers the farmer profile when it is missing: state and county, acreage, current practices or operation type, and the primary resource concern. It asks for missing fields one conversational step at a time rather than dumping a form, and proceeds once it has enough to screen. Collected fields accumulate in the graph state so the agent does not re ask.

## Persistence

A single PostgreSQL database with the pgvector extension holds three things:

1. The `payment_rates` table (structured payment data).
2. The eCFR embeddings (the vector store behind `eligibility_screener`).
3. The LangGraph checkpointer (agent conversation state, keyed by session ID).

`data/db.py` owns the connection and schema. `init_db()` runs `CREATE EXTENSION IF NOT EXISTS vector` and the table DDL, so the role in `DATABASE_URL` needs permission to create extensions. `docker-compose.yml` brings up a local instance for reproducibility.

### Agent state schema

The checkpointer persists, keyed by session or thread ID:

- Message history (the running farmer and agent conversation).
- Accumulated farmer profile (the elicited fields, so the agent does not re ask across turns).
- Cached scrape results (practice standards and ranking dates fetched during the session, reused so a live scrape is not repeated within a conversation).

## Serving layer (optional)

`src/nrcs_navigator/serving/app.py` wraps the agent in a FastAPI service exposing `POST /chat`. It is not required for grading; it demonstrates the agent running as a network service and reuses the Postgres checkpointer so conversation state survives across requests.

## Models and evaluation

The multiple model requirement is met at evaluation time by swapping the agent LLM across traces (a premier model versus a cheaper or free model). It is not a two LLM pipeline. The evaluation harness (`src/nrcs_navigator/evaluation/`) defines at least five examples, including two out of scope inputs that test graceful rejection, runs the traces through LangSmith, and scores them with an LLM as judge.

## Scope boundary

NRCS programs only: EQIP, CSP, ACEP, RCPP. CRP is administered by FSA, a separate USDA agency with separate eligibility rules, payment data, and deadlines, so it is intentionally excluded and noted as a natural v2 addition.

## Open decisions

- **Embedding model.** Hosted (for example OpenAI `text-embedding-3`) versus open source (for example BGE) is undecided. Whichever is chosen sets the pgvector column dimension in `data/db.py`, so it is configured once in `config.py` and must be agreed before the vector store or `eligibility_screener` is built.
