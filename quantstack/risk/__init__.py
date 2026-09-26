"""ORE risk leg of the stack: exposure simulation + XVA, and the positions -> ORE wire.

* :mod:`quantstack.risk.run_ore` - the article's 20y EUR swap through ORE in-process
  (``python -m quantstack.risk.run_ore``).
* :mod:`quantstack.risk.portfolio_writer` - ``contracts.PositionSnapshot`` -> ORE
  ``<Portfolio>`` of ``EquityPosition`` trades.

Nothing is imported here on purpose: ``import ORE`` loads a large native library,
so it happens only inside the functions that need it.
"""
