# Phase 3.5-G Precommit Review

## Repository Check

- Repository root: public release repository root confirmed
- Branch: `main`
- Remote: public release repository remote confirmed
- Existing history: no unexpected public history observed in this local repository
- Git author config: user.name and user.email are configured
- Push status: not performed

## Final Staged Index

- Staged files before this precommit document: 329
- Total staged size bytes before this precommit document: 4375292
- Staged status: all additions
- Unstaged files: 0 at final Phase 3.5-F checkpoint
- Untracked files: 0 at final Phase 3.5-F checkpoint

## Manifest Coverage

- `docs/ko/phase3_5f_staged_manifest.csv` exists
- Phase 3.5-F audit docs are staged
- This Phase 3.5-G document is intentionally created after Phase 3.5-F and will be reflected by the final precommit manifest refresh before commit

## Mode / Binary / Symlink / Submodule

- Git mode counts: 100644=329
- Symlink entries (`120000`): 0
- Submodule entries (`160000`): 0
- Binary files: 46
- Binary file policy: app icons, splash assets, airline logos, and Gradle wrapper jar are expected public assets
- Note: executable file mode is not set in this Windows-prepared snapshot. Android release instructions use Windows `gradlew.bat`; Linux users may need to run Gradle through their shell or set executable permission locally.

## Important Area Review

- Root README/config docs: reviewed for public boundary language
- Backend config/auth/API: symbolic env var names only, no real values
- Frontend API/auth config: placeholder/env based, no production URL embedded
- Android resources: launcher/splash assets included; local properties and build/cache output ignored
- Docs: public summaries only; private paths and production addresses excluded

## Security Scan

- Content blockers: 0
- Allowlisted symbolic hits: 0
- Allowlisted details: symbolic `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD` environment variable names only
- Private key / keystore / DB dump / model artifact / raw data: not detected in staged snapshot

## Large File Scan

- Files >= 5MB: 0
- Largest staged blob: frontend/assets/icon.png (1243890 bytes)

## Line Ending / Whitespace

- `git diff --cached --check`: PASS before this document
- No line-ending blocker identified

## Commit Decision

Commit is allowed if the final manifest refresh, `git diff --cached --check`, and final security scan remain clean.
Push remains forbidden in this phase.
