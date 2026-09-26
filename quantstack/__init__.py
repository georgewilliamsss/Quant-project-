"""quantstack: five open-source quant repos wired into one engine.

Pricing  -> QuantLib          (quantstack.pricing)
Risk     -> ORE               (quantstack.risk)
Sizing   -> skfolio           (quantstack.allocation)
Execution-> NautilusTrader    (quantstack.execution)
Display  -> Perspective       (quantstack.dashboard)

The wires between them are the four data contracts in ``quantstack.contracts``.
"""

__version__ = "0.1.0"
