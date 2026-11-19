"""The top-flows annual time series (DESIGN_BRIEF s.8, DECISIONS D2-18): a post-SAM step.

`uv run python -m pipeline timeseries` builds data/timeseries/ from clean data (every year the data
allow, old and new NAS bases kept apart) and compares each flow's 2023-24 value with its definition as
a sum of SAM cells (the balanced SAM once it exists). Definitions: flows.yaml; registered 2023-24
bridges: explanations.yaml; code: build.py. Plan: docs/phase2/plans/timeseries.md (s.8 overrides).
"""
