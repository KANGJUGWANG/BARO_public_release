# Phase 3.5-D pipeline structure summary

## Created structure

```text
pipelines/
  README.md
  crawler/README.md
  dataset/README.md
  training/README.md
  packaging/README.md
  smoke/README.md
configs/
  README.md
  crawler.example.yaml
  dataset.example.yaml
  training.example.yaml
  backend.env.example
data/
  README.md
  sample/README.md
  sample_search_observation.csv
  sample_flight_offer_observation.csv
  sample_features.csv
models/
  README.md
  .gitkeep
outputs/
  README.md
  .gitkeep
```

## Public-safe handling

- Real datasets are not included.
- Sample rows are synthetic and schema-oriented.
- Real model artifacts are not included.
- `models/` explains the private artifact contract only.
- `outputs/` is a placeholder for local generated files only.
- Config files use placeholders only.

## README updates

Both `README.md` and `README.en.md` now link to:

- pipeline overview
- data sample guide
- model artifact policy
- output policy
- reproducibility scope
- pipeline code map summary

## Reproducibility update

`docs/ko/reproducibility_scope_v2.md` now references the actual public directories created in this Phase.

## Pipeline restructure update

`docs/ko/pipeline_restructure_plan.md` now records what has been created and what remains document-only.

## Remaining limitations

- Full dataset materialization remains private-data dependent.
- Full Stage1/Stage2 retraining remains private-data dependent.
- Full runtime inference remains private-artifact dependent.
- Live deployment procedures remain private-environment dependent.
