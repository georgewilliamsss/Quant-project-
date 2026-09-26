"""Session-wide test setup.

Import ORE before any test module imports QuantLib.  The two wheels share a
SWIG runtime type table and QuantLib calls made after a later ``import ORE``
can segfault (see quantstack/_swig_order.py).  Without this, the suite only
passed because pytest collects test_bridge/test_pricing (QuantLib) before
test_risk (ORE) alphabetically; ``pytest tests/test_risk.py tests/test_bridge.py``
died with exit 139.
"""

from quantstack._swig_order import ensure_ore_before_quantlib

ensure_ore_before_quantlib()
