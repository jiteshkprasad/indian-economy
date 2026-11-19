"""Phase 2: the Social Accounting Matrix (SAM) for FY 2023-24.

The contract is docs/phase2/DESIGN_BRIEF.md; the block builder's how-to is docs/phase2/SAM_GUIDE.md.

Modules:
- spec.py          vocabularies, column schemas, thresholds and tolerances (DESIGN_BRIEF s.3, s.5.3)
- accounts.py      the 128 accounts (accounts.yaml), allowed blocks (structure.yaml), ref ownership (s.4)
- framework.py     BlockContext, BlockResult, block discovery, dependency order, validation, block outputs
- assemble.py      block entries -> unbalanced SAM, constraints, pre-balancing diagnostics
- balance.py       cross-entropy balancing (the framework's dual Newton method, its interior-point fallback;
                   cvxpy solvers for diagnosis), KKT certificate, exact polish, GRAS cross-check
- report.py        BALANCING.md and the over-threshold explanation check (explanations.yaml and
                   explanations/<block>.yaml)
- run.py           the `sam` and `sam-report` commands
- blocks/<block>.py one module per block (production.py is the template)
"""
