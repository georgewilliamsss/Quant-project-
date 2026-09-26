"""Import-order guard for the two SWIG wheels that both wrap QuantLib.

``open-source-risk-engine`` (``import ORE``) ships its own copy of QuantLib and
``QuantLib`` is the standalone wheel.  Both are SWIG modules built against the
same SWIG runtime, so they share ONE runtime type table (``swig_runtime_data5``
in ``sys.modules``).  Whichever module registers a C++ type *last* supplies the
Python proxy class for it, and a proxy created by one binary handed back to the
other dereferences the wrong object layout.

Measured on this stack (QuantLib 1.43, ORE 1.8.17.0, Python 3.13):

* ``import ORE`` then ``import QuantLib``: pricing, an ORE exposure run, the
  standalone-QuantLib bridge test, a NautilusTrader backtest and more QuantLib
  afterwards all succeed in one process.
* ``import QuantLib`` then ``import ORE``: every QuantLib call made after ORE
  has been imported can segfault (``ql.as_floating_rate_coupon(c).fixingDate()``
  in the bridge test dies with exit 139).

So the rule is: **ORE first, QuantLib second.**  Every module in ``quantstack``
that imports QuantLib calls :func:`ensure_ore_before_quantlib` first; modules
that import ORE call :func:`warn_if_quantlib_already_loaded`.  ``import ORE``
costs ~0.25 s, which is cheaper than a crash.
"""

from __future__ import annotations

import importlib.util
import sys
import warnings

SWIG_RUNTIME_MODULE = "swig_runtime_data5"

_EXPLANATION = (
    "QuantLib and ORE share one SWIG runtime type table; the module imported "
    "last owns the proxy classes, and QuantLib calls made after ORE was "
    "imported can segfault. Import ORE (or quantstack.risk) before QuantLib "
    "in any process that uses both. See quantstack/_swig_order.py."
)


def ore_installed() -> bool:
    return importlib.util.find_spec("ORE") is not None


def ensure_ore_before_quantlib() -> bool:
    """Import ORE now if it is installed and QuantLib is not loaded yet.

    Returns True when the process is in the safe state afterwards (ORE loaded
    before QuantLib, or ORE not installed at all).  If QuantLib is already
    loaded and ORE is not, importing ORE here would *create* the unsafe state,
    so nothing is imported and False is returned; a warning is emitted only
    when ORE is actually imported later (see :func:`warn_if_quantlib_already_loaded`).
    """
    if "ORE" in sys.modules or not ore_installed():
        return True
    if "QuantLib" in sys.modules:
        return False
    import ORE  # noqa: F401  (side effect: registers the shared type table first)

    return True


def warn_if_quantlib_already_loaded() -> None:
    """Call right before ``import ORE``: warn if QuantLib got there first."""
    if "QuantLib" in sys.modules and "ORE" not in sys.modules:
        warnings.warn(
            "importing ORE after QuantLib in the same process: " + _EXPLANATION,
            RuntimeWarning,
            stacklevel=3,
        )


__all__ = ["ensure_ore_before_quantlib", "warn_if_quantlib_already_loaded", "ore_installed", "SWIG_RUNTIME_MODULE"]
