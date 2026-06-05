# BARO

BARO is a capstone project that recommends flight ticket purchase timing based on observed flight prices and machine-learning inference. The service presents a `BUY` or `WAIT` signal together with a price-drop expectation gauge.

This public repository contains the cleaned source code and public documentation for submission and review. Production database dumps, training datasets, model pkl artifacts, private server addresses, and secret values are not included.

## Key Features

- Oneway and roundtrip flight candidate views
- DB observation and realtime refresh source display
- BUY / WAIT recommendation output
- Price-drop expectation gauge
- Oneway and roundtrip detail pages with price trend views
- Route analysis page
- Mobile WebView / Android APK project structure

## System Overview

```text
Frontend (React/Vite)
  -> Backend API (FastAPI)
      -> MySQL observation DB
      -> ML inference runtime
      -> crawler/refresh jobs
```

See [docs/en/architecture.md](docs/en/architecture.md) for details.

## Model Summary

BARO uses a two-stage recommendation structure.

- Stage 1: estimates future price-saving potential
- Stage 2: decides BUY or WAIT

The public UI displays a price-drop expectation gauge. Final display thresholds are:

- Oneway: 80%
- Roundtrip: 65%

See [docs/en/model_overview.md](docs/en/model_overview.md) for details.

## Data Summary

Final presentation data summary:

- Collection window: 2026-04-16 08:00 ~ 2026-06-04 00:00
- Observation timestamps: 147
- Service DB observations: 141,120
- Trainable flight rows: 4,562,741

Raw datasets and model artifacts are not included in this public repository.

## Tech Stack

- Frontend: React, Vite, CSS Modules, Capacitor
- Backend: FastAPI, Python
- DB: MySQL
- ML: scikit-learn / XGBoost-family artifact-based inference
- Android: Capacitor Android

## Local Usage

### Frontend

```bash
cd frontend
npm install
npm run build
```

For local development:

```bash
npm run dev
```

### Backend syntax check

The public repository does not include production DB access or model artifacts, so full production inference requires a private runtime environment.

```bash
python -m py_compile backend/main.py
```

## Environment Variables

Do not commit real secret values. Use example files and configure local/private environments separately.

This public repository may include environment variable names, HTTP authorization header names, and placeholder examples. It must not include real production values, private server addresses, personal local paths, or private model artifacts.

Example:

```env
VITE_API_BASE_URL=<BACKEND_API_URL>
DB_HOST=<DB_HOST>
DB_USER=<DB_USER>
DB_PASS_PLACEHOLDER=<DB_PASS>
AUTH_PROVIDER_KEY=<AUTH_PROVIDER_KEY>
AUTH_REDIRECT_URI=<AUTH_REDIRECT_URI>
APP_SIGNING_KEY=<APP_SIGNING_KEY>
```

## API Summary

See [docs/en/api_contract.md](docs/en/api_contract.md).

- `GET /health`
- `GET /health/model`
- `GET /recommend/model-info`
- `POST /recommend/predict-one`
- `POST /recommend/analyze-job`
- `POST /recommend/oneway-candidates`
- `POST /recommend/roundtrip-candidates`
- `POST /recommend/history`


## Reproducibility and Pipelines

- [Pipeline Overview](pipelines/README.md)
- [Data Sample Guide](data/README.md)
- [Model Artifact Policy](models/README.md)
- [Output Policy](outputs/README.md)
- [Reproducibility Scope](docs/ko/reproducibility_scope_v2.md)
- [Pipeline Code Map](docs/ko/pipeline_code_map_summary.md)

## Public Repository Limitations

The following are intentionally excluded:

- Real `.env` files
- Release keystore / jks / key notes
- Private server IPs or internal paths
- DB dumps / parquet files / large CSV datasets
- Model pkl artifacts
- Raw internal phase logs

Internal phase logs are represented only through public summary documents.

## Disclaimer

This is an educational capstone project. Recommendations are decision-support information only and do not guarantee flight prices or purchase outcomes.
