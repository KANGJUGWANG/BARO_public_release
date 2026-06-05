# Phase 3 npm Audit Review

## Initial Finding

`npm audit` initially reported 2 high severity advisories related to `react-router` through `react-router-dom`.

## Action Taken

- Ran `npm.cmd audit fix` without `--force`.
- `react-router` and `react-router-dom` were resolved to `7.17.0` in `package-lock.json`.
- `package.json` dependency range remained unchanged because the existing range allowed the safe patch.

## Result

- `npm audit fix` completed with `found 0 vulnerabilities`.
- Frontend build passed after the update.

`npm audit fix --force` was not used.
