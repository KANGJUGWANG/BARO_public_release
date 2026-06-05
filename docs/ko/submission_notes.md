# Submission Notes

BARO public release repository is prepared for source review and capstone submission.

## Public Scope

- Frontend and backend source code
- Public documentation
- Example configuration files
- Small sample CSV files for schema understanding
- Pipeline and artifact contract documentation

## Private Scope

- Real environment values
- Production DB connection information
- Production server addresses
- Personal local paths
- Model pkl artifacts
- Raw training data and large experiment outputs
- Android signing keys and keystore files

## Review Rule

The public repository may contain symbolic environment variable names and standard HTTP header names. These are allowed only when they do not expose real values.
