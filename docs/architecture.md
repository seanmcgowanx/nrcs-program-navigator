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
| `program_availability` | Live web scrape | NRCS Ranking Dates page |

`payment_estimator` does not invent a number for ACEP, which is appraisal based; it redirects the user to the local NRCS office. The two scrape tools talk to live NRCS pages and never touch the database.

## Scope handling is not a tool

The agent declines out of scope requests through its system prompt, not a dedicated function. In scope requests (NRCS program guidance) drive the agent toward its tools. Out of scope requests get a polite decline plus a redirect, with no tool call and no guessing:

- CRP questions are administered by FSA, a separate agency, so redirect to the local FSA office.
- Legal or tax advice and unrelated chit chat redirect to the local NRCS service center.

This is what satisfies the rubric requirement to gracefully handle out of scope queries, and it supplies the required graceful rejection examples in the evaluation set.

## Elicitation flow

The system prompt also drives a short multi turn flow. Before screening eligibility, the agent gathers the client's farm profile from the advisor when it is missing: state (county is optional context only, since the payment data is state level), acreage, current practices or operation type, and the primary resource concern. It asks for missing fields one conversational step at a time rather than dumping a form, and proceeds once it has enough to screen. Collected fields accumulate in the graph state so the agent does not re ask.

## Persistence

A single PostgreSQL database with the pgvector extension holds three things:

1. The `payment_rates` table (structured payment data).
2. The eCFR embeddings (the vector store behind `eligibility_screener`).
3. The LangGraph checkpointer (agent conversation state, keyed by session ID).

`data/db.py` owns the connection and schema. `init_db()` runs `CREATE EXTENSION IF NOT EXISTS vector` and the table DDL, so the role in `DATABASE_URL` needs permission to create extensions. `docker-compose.yml` brings up a local instance for reproducibility.

### Agent state schema

The checkpointer persists, keyed by session or thread ID:

- Message history (the running advisor and agent conversation).
- Accumulated client profile (the elicited fields, so the agent does not re ask across turns).
- Cached scrape results (practice standards and ranking dates fetched during the session, reused so a live scrape is not repeated within a conversation).

## Serving layer (optional)

`src/nrcs_navigator/serving/app.py` wraps the agent in a FastAPI service exposing `POST /chat`. It is not required for grading; it demonstrates the agent running as a network service and reuses the Postgres checkpointer so conversation state survives across requests.

## Models and evaluation

The multiple model requirement is met at evaluation time by swapping the agent LLM across traces (a premier model versus a cheaper or free model). It is not a two LLM pipeline. The evaluation harness (`src/nrcs_navigator/evaluation/`) defines at least five examples, including two out of scope inputs that test graceful rejection, runs the traces through LangSmith, and scores them with an LLM as judge.

## Scope boundary

NRCS programs only: EQIP, CSP, ACEP, RCPP. CRP is administered by FSA, a separate USDA agency with separate eligibility rules, payment data, and deadlines, so it is intentionally excluded and noted as a natural v2 addition.

## Decisions

These were open and are now settled; recorded here so the choice and its reasoning persist.

- **Embedding model: OpenAI `text-embedding-3-small` (1536 dimensions).** Chosen over an open source model because it adds no dependencies (the OpenAI client is already used for the premier model leg), is strong on dense regulatory text, and costs a fraction of a cent for this corpus. Configured as constants in `config.py` (`EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`), not env vars: the stored pgvector embeddings are this model's output, so the model and its dimension are an invariant, not a tunable. Unlike the two agent LLMs (swapped via env for the evaluation), changing the embedding model means embedding every chunk again. Decided 2026-06-08.
- **eCFR source: the eCFR API as structured XML, not PDFs.** The four parts are fetched from the versioner API (`full/{date}/title-7.xml?part=NNNN`) at a pinned version date for reproducible embeddings. The XML exposes the part, subpart, and section hierarchy explicitly, so chunks align to whole sections (one chunk per section; an oversized section is split further to `CHUNK_SIZE` tokens with `CHUNK_OVERLAP`) and each chunk carries its citation (for example 7 CFR 1466.6). This replaces the original PDF plus pypdf plan, which would have required reverse engineering section boundaries from extracted text and produced weaker citations. Decided 2026-06-08.
- **Agent program vocabulary: the four high level programs (EQIP, ACEP, CSP, RCPP).** These are the lingua franca between tools and what the model reasons in, defined once as `config.PROGRAMS`. The FIPS payment export instead labels rows by funding pool (EQIP Farm Bill, EQIP IRA, CStwP Farm Bill, CStwP IRA, CSP-GCI, RCPP-CSP, RCPP-EQIP); those granular labels are a data layer detail and must not cross a tool boundary. `payment_estimator` alone translates a high level program into its pools via `config.PROGRAM_FUNDING_POOLS` and aggregates across them. An explicit map is used rather than a SQL prefix match because CSP is stored under its older acronym "CStwP" plus "CSP-GCI", so a `LIKE 'CSP%'` would silently miss the CStwP rows. `fips_payments.IN_SCOPE_PROGRAMS` (the cleaning filter) is derived by flattening the same map, so the seven labels live in one place. Decided 2026-06-08.
- **eligibility_screener retrieval is deduplicated by section.** A long section is split into several chunks, so a raw top k similarity search can return multiple chunks of the same section and crowd out other relevant provisions. The tool over fetches candidate chunks (`CANDIDATE_CHUNKS`), keeps the best ranked chunk per distinct section, and returns the top distinct sections (`TOP_SECTIONS`), so the model sees a breadth of provisions rather than repeats of one. Decided 2026-06-08.
- **Agent conversation state persists in Postgres (the LangGraph PostgresSaver), not in process memory.** The checkpointer stores the message history, and with it the elicited client profile, keyed by thread_id in the shared database alongside the payments and embeddings. Chosen over an in memory saver because the state must survive process restarts and be reachable across workers: the optional FastAPI serving layer is stateless, so a conversation's second request can land on a different or restarted process than its first, and only a shared store lets any worker resume a thread_id. Reusing the existing database adds no new infrastructure (one store for three jobs). Tradeoff: checkpoints are not removed by the checkpointer itself -- a thread persists until explicitly deleted, and a checkpoint is written per super step, so a retention policy is required. Addressed by a background sweep in the serving app (`agent/cleanup.py`, started in the `lifespan`) that deletes any thread idle past `config.CHECKPOINT_RETENTION_DAYS` (default 30), running on startup and then every `CHECKPOINT_CLEANUP_INTERVAL_HOURS`. A notebook only run could use an in memory saver, but the serving story and the single store decision make Postgres the right default. Decided 2026-06-08.
