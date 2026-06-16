# Deployment runbook

How to take the navigator live on free services: a Neon Postgres database, the
FastAPI backend on Render (Docker), and the Next.js frontend on Vercel. Follow
the phases in order. The ordering matters: the backend connects to the database
on startup, so the database must exist and hold data before the backend deploys.

Final shape:

| Layer | Service | Notes |
|-------|---------|-------|
| Database | Neon (Postgres + pgvector) | Holds payment_rates, eCFR embeddings, checkpointer |
| Backend | Render web service (Docker) | FastAPI, kept awake by an external uptime monitor |
| Frontend | Vercel (Next.js) | Calls the backend over HTTP |

Prerequisites: an OpenAI API key, and the two NRCS source URLs already in your
local `.env` (`NRCS_PRACTICE_STANDARDS_URL`, `NRCS_RANKING_DATES_URL`).

---

## Phase 1: Provision the Neon database

1. Create a free project at https://neon.tech. Note the connection string from
   the dashboard (Connection Details). It looks like
   `postgresql://USER:PASS@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require`.
2. Convert it to the form this project expects by inserting the `+psycopg`
   dialect tag after `postgresql`:
   ```
   postgresql+psycopg://USER:PASS@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require
   ```
   Keep `sslmode=require`; Neon refuses non TLS connections. The checkpointer
   helper (`db.psycopg_url`) strips the `+psycopg` tag but preserves `sslmode`.

The `vector` extension does not need manual enabling here; `init_db()` runs
`CREATE EXTENSION IF NOT EXISTS vector` in the next phase.

---

## Phase 2: Load the data into Neon

Run the existing pipeline locally, pointed at Neon. This is the same sequence
`notebooks/01_data_pipeline.ipynb` performs, condensed to one command.

1. Point your local `.env` at Neon:
   ```
   DATABASE_URL=postgresql+psycopg://USER:PASS@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require
   ```
2. Build the schema, load payments, and embed the eCFR sections:
   ```bash
   poetry run python -c "
   from nrcs_navigator.data import db, fips_payments, ecfr_loader, vectorstore
   db.init_db()
   rows = fips_payments.write(fips_payments.load_clean())
   chunks = vectorstore.build_index(ecfr_loader.load_chunks())
   print(f'loaded {rows} payment rows and embedded {chunks} eCFR chunks')
   "
   ```
   The embedding step calls the OpenAI embeddings API, so `OPENAI_API_KEY` must
   be set in `.env`. It is the slow step (it embeds every eCFR section once).
3. Sanity check the live database path before touching any host. With `.env`
   still pointing at Neon:
   ```bash
   poetry run uvicorn nrcs_navigator.serving.app:app --reload
   # in another shell:
   curl localhost:8000/health
   curl -X POST localhost:8000/chat -H 'content-type: application/json' \
     -d '{"session_id":"t1","message":"A client runs 180 acres of irrigated almonds in Stanislaus County, California and wants to cut water use."}'
   ```
   A grounded reply confirms the agent, the database, and the tools all work
   against Neon. Send a second message with the same `session_id` to confirm the
   conversation continues (checkpointer working).

---

## Phase 3: Deploy the backend to Render

The repo ships a `Dockerfile` (Chromium only Playwright image) and a
`render.yaml` Blueprint. The backend must be a Docker service; Render's native
Python environment cannot install Chromium's system libraries.

1. Push the repo to GitHub if it is not there already.
2. In Render, New > Blueprint, and point it at the repo. Render reads
   `render.yaml` and proposes the `nrcs-navigator-api` web service (Docker, free
   plan, health check at `/health`).
3. Render prompts for the `sync: false` environment variables. Set:
   - `OPENAI_API_KEY` - your key
   - `DATABASE_URL` - the Neon string from Phase 1 (with `+psycopg` and `sslmode=require`)
   - `NRCS_PRACTICE_STANDARDS_URL` - same value as your `.env`
   - `NRCS_RANKING_DATES_URL` - same value as your `.env`
   - `FRONTEND_ORIGINS` - leave as a placeholder for now (e.g. `http://localhost:3000`); update it in Phase 5 once the Vercel URL exists
   `PREMIER_MODEL` is already set to `gpt-4o` in `render.yaml`. The
   `LANGCHAIN_*` variables are optional; leave them blank unless you are turning
   on tracing (see Phase 6).
4. Deploy. The first build pulls dependencies and Chromium, so it takes a few
   minutes. When the health check at `/health` passes, the service is live. Note
   the URL, e.g. `https://nrcs-navigator-api.onrender.com`.
5. Verify:
   ```bash
   curl https://nrcs-navigator-api.onrender.com/health
   ```

Notes:
- Keep this at a single instance. The agent is built once on startup and holds
  the checkpointer connection.
- Free tier has 512 MB of memory. Normal chat is fine; the pressure point is a
  scrape tool launching Chromium (roughly 200 MB more). If you see memory
  related 502s during a scrape, move to the Starter plan (2 GB).

---

## Phase 4: Keep the backend awake

Render free spins the service down after about 15 minutes idle, and the next
request then pays a cold boot (which surfaces to a user as a request that hangs
and then 503s from the proxy). Keep it warm with an external uptime monitor that
pings `/health` on a fixed interval. `/health` touches no database or model, so
the pings are free.

Use UptimeRobot (free, includes downtime alerts):

1. Sign up at https://uptimerobot.com.
2. Add New Monitor.
3. Monitor Type: HTTP(s).
4. Friendly Name: `NRCS Navigator keep-warm`.
5. URL: `https://nrcs-navigator-api.onrender.com/health`
6. Monitoring Interval: 5 minutes (the free minimum, comfortably under the
   ~15 minute idle window).
7. Create Monitor.

A https://cron-job.org job hitting the same `/health` URL every 5 to 10 minutes
works equally well as an alternative.

Do not use GitHub Actions `schedule` for this. Scheduled workflows are
best effort and routinely fire far later than requested (10 minute cadences
slipping to an hour or more), which is too loose for a 15 minute idle window. The
repo contains `.github/workflows/keep-warm.yml` from an earlier approach; disable
it (Actions tab > keep-warm > Disable workflow) so it does not run, and rely on
the external monitor instead.

---

## Phase 5: Deploy the frontend to Vercel

1. In Vercel, New Project, import the same repo, and set the Root Directory to
   `frontend`. Vercel detects Next.js automatically.
2. Add an environment variable:
   - `NEXT_PUBLIC_API_URL` = the Render backend URL (no trailing slash), e.g.
     `https://nrcs-navigator-api.onrender.com`
3. Deploy. Note the Vercel URL, e.g. `https://nrcs-navigator.vercel.app`.
4. Open the CORS gate for that origin. In Render, set the backend
   `FRONTEND_ORIGINS` environment variable to the Vercel URL (comma separate if
   there is more than one) and let it redeploy:
   ```
   FRONTEND_ORIGINS=https://nrcs-navigator.vercel.app
   ```
5. End to end check: open the Vercel URL, send a message, and confirm a reply.
   Refresh the page and confirm the conversation continues (the session id is
   stored in the browser and resumes the same thread).

---

## Phase 6: Tracing with LangSmith (optional)

Tracing captures each agent run (per tool latency, recursion trips, errors),
which is the fastest way to see where a slow or failing turn spends its time. It
needs no code change; LangGraph instruments itself when the environment is set.

1. Create a key at https://smith.langchain.com (Settings > API Keys).
2. On Render, set both of these (the other two LangSmith variables already carry
   values in `render.yaml`):
   - `LANGCHAIN_TRACING_V2` = `true`
   - `LANGCHAIN_API_KEY` = your LangSmith key
3. Redeploy. Runs appear in the `nrcs-navigator` project in LangSmith.

Leave both unset to keep tracing off; the service runs the same either way. Note
that traces include the conversation content (the client operation descriptions)
and are stored in LangSmith's cloud. To trace local runs too, put the same
variables in your `.env`.

---

## Making changes after launch

Both services redeploy from GitHub, so the loop is push based.

**Backend (Render, Docker).**
1. Edit locally. Test against the real database before pushing by pointing your
   local `.env` `DATABASE_URL` at Neon and running
   `poetry run uvicorn nrcs_navigator.serving.app:app --reload`. For full
   container parity, `docker build -t nrcs-navigator-api . && docker run` it.
2. Commit and push. Render rebuilds the image and redeploys automatically (the
   Blueprint enables auto deploy). The `/health` check gates the cutover, so a
   bad build does not replace a working one. Watch progress in the Render logs.

**Frontend (Vercel).**
1. Edit locally and run `npm run dev` (point `.env.local` at the deployed or a
   local backend).
2. Commit and push. Vercel rebuilds and deploys automatically, with a preview
   URL per branch.

For risky changes, push to a branch and use the preview deploys rather than
pushing straight to the deployed branch. Changing a dependency means the
`requirements.txt` export must be regenerated
(`poetry export --only main --without-hashes -o requirements.txt`) and committed,
since the Docker image installs from it, not from `poetry.lock`.

---

## Operating notes

- **Updating data.** Re run the Phase 2 command against Neon whenever the FIPS
  export or the eCFR snapshot changes. The whole sequence is idempotent:
  `init_db()` uses `IF NOT EXISTS`, `fips_payments.write` replaces the table
  contents, and `vectorstore.build_index` rebuilds the embedding collection from
  scratch (it sets `pre_delete=True`), so re running never stacks duplicates.
- **Checkpoint growth.** The checkpointer never prunes old conversation state.
  For a long lived deployment, add a retention job that deletes rows from the
  `checkpoints` family older than some window.
- **Switching the serving model.** The backend serves `PREMIER_MODEL` (`gpt-4o`).
  To serve the cheaper leg, change that environment variable on Render to
  `gpt-4o-mini`; no code change is needed because `build_agent` reads it through
  config. (The embedding model is fixed and unaffected.)
- **Rotating the database.** If the Neon string changes, update `DATABASE_URL`
  on Render and rerun Phase 2 against the new database before cutting over.
