# BARO Backend

This backend is a public-source FastAPI project for the BARO capstone service. Production database access, production model artifacts, and real authentication provider credentials are not included.

## Install

```bash
cd backend
pip install -r requirements.txt
```

## Configuration

Use public example files as placeholders only. Create local/private environment files outside version control when running the backend with real services.

Required configuration groups:

- frontend origin
- database connection
- authentication provider keys
- token signing key
- model artifact directory

Do not commit real values.

## Run

From the repository root:

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Full model inference requires private model artifacts and a populated observation database.

## Main Areas

- `backend/flights`: candidate search API
- `backend/recommend`: recommendation, history, route analysis, and analyze-job APIs
- `backend/ml_inference`: model runtime adapters and feature/history helpers
- `backend/crawler`: public crawler/parser structure
- `backend/core`: config, DB, and token helpers
