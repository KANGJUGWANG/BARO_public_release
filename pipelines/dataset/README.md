# Dataset Pipeline

The dataset pipeline turns repeated observations into model-ready rows.

## Concepts

- `search_observation`: one observed search condition at one timestamp
- `flight_offer_observation`: one flight offer observed under a search observation
- freeze dataset: a fixed training/evaluation snapshot
- latest usable current cutoff: last timestamp allowed for current-row training
- label horizon: future window used only for label construction

## Label Horizon

The final Exp-C target uses a 72-hour future window. The last 72 hours of observations are not used as current training rows when future labels cannot be computed safely.

## Public Scope

The public repository provides schema-shaped synthetic samples, not the full dataset.

Related sample files:

- `data/sample/sample_search_observation.csv`
- `data/sample/sample_flight_offer_observation.csv`
- `data/sample/sample_features.csv`

## Private Requirement

Full materialization requires the private observation database or a private frozen dataset.
