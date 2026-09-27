"""Thesis portfolio run: the user's own 54-instrument book through the execution engine.

* :mod:`quantstack.thesis.universe` -- ``data/thesis/thesis_holdings.csv`` -> tickers,
  sleeves and the thesis's own weights (plus both renormalisations over a subset)
* :mod:`quantstack.thesis.data`     -- the GBP total-return panel: loading, the
  manifest check, per-ticker availability, the window/gap policy, and the
  min-at-100 rescaling the engine's whole shares need
* :mod:`quantstack.thesis.repairs`  -- documented level repairs (unadjusted
  share consolidations), applied before any slicing and logged
* :mod:`quantstack.thesis.report`   -- in-sample allocation statistics, the
  comparison markdown and the two thesis figures
* :mod:`quantstack.thesis.run`      -- presets, ``run_thesis(...)`` and the CLI
  (``python -m quantstack.thesis.run``, ``make thesis``)

Nothing is imported here on purpose: importing the package must not pull in
NautilusTrader or skfolio for callers that only want the data helpers.
"""
