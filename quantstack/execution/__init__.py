"""Execution layer: NautilusTrader runs the loop, skfolio sizes inside it.

* :mod:`quantstack.execution.data`     -- skfolio's bundled prices -> Nautilus ``Bar`` objects
* :mod:`quantstack.execution.strategy` -- ``SkfolioRebalance`` (cash account, two-phase orders)
* :mod:`quantstack.execution.backtest` -- ``run_backtest(...)`` and the CLI
  (``python -m quantstack.execution.backtest``)

Nothing is imported here on purpose: importing the package must not pull in
NautilusTrader for callers that only want the contracts or the data helpers.
"""
