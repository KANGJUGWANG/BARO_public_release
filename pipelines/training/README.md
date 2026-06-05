# Training Pipeline

BARO uses a two-stage recommendation model.

## Stage 1

Stage 1 estimates future price-saving potential. Its output is represented as `pred_saving`.

## Stage 2

Stage 2 combines the original features and `pred_saving` to estimate `wait_probability`. The final decision is:

```text
WAIT if wait_probability > threshold else BUY
```

## Final Exp-C Target

The final model uses the Exp-C target:

```text
WAIT if 72h max_drop_krw >= 20000 and 72h max_drop_pct >= 0.03
```

## Final Public Summary

- Collection window: 2026-04-16 08:00 ~ 2026-06-04 00:00
- Observation timestamps: 147
- Trainable flight rows: 4,562,741
- Oneway training rows: 989,669
- Roundtrip training rows: 3,573,072
- Oneway threshold: 80%
- Roundtrip threshold: 65%

## Public Scope

This repository documents the training contract and sample schemas. Full training requires private datasets and model artifact output storage.
