# Architecture

BARO consists of a React/Vite frontend, a FastAPI backend, a MySQL observation database, and an ML inference runtime.

```text
React/Vite Frontend
  -> FastAPI Backend
      -> Candidate / History / Route Analysis API
      -> ML Inference Runtime
      -> MySQL Observation DB
      -> Refresh / Crawler Jobs
```

Private server URLs are represented as `<BACKEND_API_URL>` in public documents.
