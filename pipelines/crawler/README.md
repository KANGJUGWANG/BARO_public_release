# Crawler Pipeline

The crawler layer collects flight search results and normalizes offers into observation records.

## Related Code

- `backend/crawler/parser.py`
- `backend/crawler/collector.py`
- `backend/crawler/url_builder.py`
- `backend/crawler/constants.py`
- `src/crawler/parser.py`
- `src/crawler/collector.py`

## Public Scope

This repository can show the parser/collector structure and the target schema. Running the real collector requires private source configuration and operational credentials that are not included here.

## Output Concept

Crawler output is normalized into:

- search observation rows
- flight offer observation rows

See [sample data](../../data/sample/README.md) for synthetic examples.

## Not Included

- Real external source credentials
- Production endpoint values
- Production runtime schedule
- Raw collected payloads
