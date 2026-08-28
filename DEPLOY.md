# Deploying Seamly to Vercel

The app is live as a serverless FastAPI deployment; the only missing piece
is a Postgres database, which needs one manual step because Vercel's
marketplace add-ons cannot be created from the CLI.

## Current state

- Project: `pawansingh3889s-projects/seamly`
- URL: https://seamly-blush.vercel.app
- Deployed via `builds` in `vercel.json` (Python runtime + static assets);
  the project settings build configuration is intentionally unused.
- Without a database every route returns 503 with a clear message; static
  assets already serve.

## Step 1: create a Postgres database

Easiest: in the Vercel dashboard, open the project, go to Storage, and add
a **Neon** Postgres database (free tier is fine). Copy the pooled connection
string (`postgresql://...sslmode=require`).

Any Postgres works: Neon, Supabase, or your own.

## Step 2: set the environment variables

```bash
vercel env add SEAMLY_DATABASE_URL production
# paste: postgresql+asyncpg://USER:PASS@HOST/db?ssl=require
# note the scheme: postgresql+asyncpg://, not postgresql:// (asyncpg driver)

printf "your-long-random-secret" | vercel env add SEAMLY_SESSION_SECRET production
```

Generate a secret with `openssl rand -hex 32`.

Optional: `SEAMLY_AUTO_SEED=0` (disable boot-seeding), `SEAMLY_FIXTURE_DIR`
(leave default), `SEAMLY_LLM_BASE_URL` / `SEAMLY_LLM_API_KEY` /
`SEAMLY_LLM_MODEL` (enable the analyst).

## Step 3: run the migrations once from your machine

Migrations are not run on Vercel; run them against the production database
locally (the schema includes the append-only audit trigger, which only
Postgres can enforce):

```bash
SEAMLY_DATABASE_URL="postgresql+asyncpg://USER:PASS@HOST/db?ssl=require" \
  uv run alembic upgrade head
```

Future schema changes: same command after merging the migration. Local
Postgres users just run `make migrate`.

## Step 4: redeploy

```bash
vercel --prod
```

The app boots, auto-seeds the empty ledger (7 exceptions, 15,110 pounds at
risk), and the board is live. Log in as `cfo@kestrel.example` /
`demo-secret`, then change or remove that account for anything real.

## Notes

- `requirements.txt` is generated: run `make requirements` after changing
  dependencies, then commit.
- `api/index.py` is the serverless entry; it adds `src/` to `sys.path`, so
  the src-layout package imports without an editable install.
- Cold starts re-check the ledger but only seed when it is empty
  (fingerprint-based upserts keep reruns idempotent).
- Vercel functions are stateless; sessions live in the Postgres `session`
  table, so logins survive cold starts.
- The 60-second `maxDuration` is set in `vercel.json`; Hobby accounts
  currently allow it. If Vercel rejects it, drop to 10.
