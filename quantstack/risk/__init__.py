"""ORE risk leg of the stack: exposure simulation + XVA, the positions -> ORE wire,
and the ORE -> QuantLib bridge test.

* :mod:`quantstack.risk.run_ore` - the article's 20y EUR swap through ORE in-process
  (``python -m quantstack.risk.run_ore``); writes ``results/risk_*`` including the
  pricing curve's native pillars (``risk_curve_pillars.csv``).
* :mod:`quantstack.risk.portfolio_writer` - ``contracts.PositionSnapshot`` -> ORE
  ``<Portfolio>`` of ``EquityPosition`` trades (``python -m quantstack.risk.portfolio_writer``).
* :mod:`quantstack.risk.bridge_test` - rebuilds ORE's EUR6M curve in the standalone
  QuantLib wheel from ``run_ore``'s results files, reprices the swap and explains
  the gap to ORE's NPV (``python -m quantstack.risk.bridge_test``).

Nothing is imported here on purpose: ``import ORE`` loads a large native library,
so it happens only inside the functions that need it.
"""
