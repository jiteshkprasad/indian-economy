"""India SAM data pipeline.

Entry point: ``python -m pipeline <command>`` (see ``pipeline/cli.py``).
This package must not import numpy/polars at import time: ``pipeline.__main__``
pins thread and hash-seed environment variables before anything heavy loads.
"""
