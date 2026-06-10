# NSE Multiverse Tool

Measure non-standard errors (specification-driven variation in regression estimates) via a
browser-based multiverse analysis tool.

## Quick start (Docker)

```bash
docker-compose up --build
```

Then open http://localhost:5173.

## Quick start (local development)

**Backend**

```bash
# Start Postgres and Redis (or use Docker for just these services)
docker-compose up db redis -d

cd apps/backend
pip install -r requirements.txt
pip install -e ../../packages/nse_engine

uvicorn main:app --reload --port 8000
# In a second terminal:
rq worker --url redis://localhost:6379/0 nse
```

**Frontend**

```bash
cd apps/frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Structure

```
packages/nse_engine/   Shared engine (Config, runner, aggregate, report)
apps/backend/          FastAPI + RQ workers
apps/frontend/         React + Vite + TypeScript (academic theme, D3 charts)
```

## Milestones

| Milestone | Status |
|-----------|--------|
| M0 Engine refactor | ✓ |
| M1 Aggregation | ✓ |
| M2 Backend API | ✓ |
| M3 Frontend | ✓ |
| M4 Export package | ✓ |
| M5 Hurdle model | partial (structure in place) |

## Export

After a run completes, click **Download replication package** to get a zip containing:
- The engine source
- Your dataset
- The exact config (mode forced to `full`)
- A `run.py` that reproduces and extends the analysis locally

```bash
unzip nse_replication_*.zip
cd nse_replication
pip install -r requirements.txt
python run.py --config config.json
```
