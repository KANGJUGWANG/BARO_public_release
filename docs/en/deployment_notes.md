# Deployment Notes

This public repository contains source code and public documentation only. Production deployment requires private environment variables, DB access, and model artifacts.

## Frontend

Set the API base URL through an environment variable.

```env
VITE_API_BASE_URL=<BACKEND_API_URL>
```

## Backend

FastAPI runtime requires a private `.env` and DB configuration.

## Android

Capacitor Android project files are included. Release signing keys are not included.
