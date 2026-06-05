# Phase 3.5-E Build / Compile / Audit Check

## Frontend

Commands executed in the public release repository:

```powershell
cd frontend
npm.cmd install
npm.cmd audit
npm.cmd run build
```

Result:

- `npm.cmd install`: pass
- `npm.cmd audit`: pass, 0 vulnerabilities
- `npm.cmd run build`: pass

Generated folders from validation were removed after the check:

- `frontend/node_modules`
- `frontend/dist`
- `frontend/android/.gradle`

## Backend

Command executed:

```powershell
python -m py_compile backend\main.py backend\core\config.py backend\core\db.py backend\recommend\router.py backend\recommend\service.py backend\flights\router.py backend\flights\service.py
```

Result:

- backend syntax compile: pass

Temporary pycache was redirected outside the repository and removed after validation.

## Decision

Build, audit, and syntax gates pass for the public release repository.
