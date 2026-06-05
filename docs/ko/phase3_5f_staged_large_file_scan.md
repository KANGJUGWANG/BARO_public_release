# Phase 3.5-F Staged Large File Scan

- Staged files: 330
- Total staged size bytes: 4378002
- >= 5MB review files: 0
- >= 10MB warning files: 0
- >= 50MB block files: 0

## Top 20 Staged Files by Blob Size

| path | size_bytes | status |
| --- | ---: | --- |
| `frontend/assets/icon.png` | 1243890 | ok |
| `frontend/assets/baro-splash-full-logo.png` | 880252 | ok |
| `frontend/src/assets/baro-login-logo.png` | 230455 | ok |
| `frontend/package-lock.json` | 127969 | ok |
| `frontend/assets/baro-splash-symbol.png` | 93021 | ok |
| `frontend/src/web/pages/SearchResultPage.jsx` | 84385 | ok |
| `frontend/assets/baro-launcher-foreground.png` | 82202 | ok |
| `frontend/assets/baro-launcher-preview.png` | 76310 | ok |
| `backend/recommend/service.py` | 74060 | ok |
| `frontend/src/assets/airlines/BX-airbusan-logo.png` | 55888 | ok |
| `docs/ko/phase3_5f_pre_stage_manifest.csv` | 49915 | ok |
| `docs/ko/full_docs_inventory.csv` | 49280 | ok |
| `frontend/android/gradle/wrapper/gradle-wrapper.jar` | 43764 | ok |
| `frontend/android/app/src/main/res/drawable-land-xxxhdpi/splash.png` | 42292 | ok |
| `frontend/android/app/src/main/res/drawable-port-xxxhdpi/splash.png` | 40640 | ok |
| `docs/ko/phase3_5f_staged_manifest.csv` | 35323 | ok |
| `frontend/src/web/pages/CardDetailPage.jsx` | 31043 | ok |
| `frontend/android/app/src/main/res/drawable-land-xxhdpi/splash.png` | 29516 | ok |
| `frontend/android/app/src/main/res/drawable-port-xxhdpi/splash.png` | 28882 | ok |
| `docs/ko/full_docs_inventory_corrected.csv` | 28742 | ok |

## Decision

PASS. No staged file is 5MB or larger.
