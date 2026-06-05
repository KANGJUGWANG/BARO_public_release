# Smoke Validation

Smoke validation checks whether the public code structure can be built or inspected without private production assets.

## Backend Checks

Public-safe checks:

- Python syntax check
- app import check when dependencies are installed
- health route structure review
- model-info route contract review

Full runtime checks require private model artifacts and database access.

## Frontend Checks

Public-safe checks:

- dependency install
- Vite build
- static route/component review

## APK Checks

Public-safe checks:

- Capacitor project structure review
- Android resource presence

Release signing requires private signing material and is not included.
