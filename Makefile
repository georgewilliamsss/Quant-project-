# Five repos, one engine.  Every target runs inside the pinned Python 3.13 venv.
PY ?= .venv/bin/python
UV ?= uv

.PHONY: venv install check pricing allocation risk bridge execution dashboard all quick serve test test-fast test-slow clean

venv:        ## creates .venv only if it does not exist yet
	test -x $(PY) || $(UV) venv .venv --python 3.13

install: venv  ## the full lock (every transitive pin) + this package, editable (python -m quantstack.* works from any directory)
	$(UV) pip install --python $(PY) -r requirements-lock.txt -e ".[dev]"

check:  ## all five engines import in ONE process (ORE before QuantLib: see quantstack/_swig_order.py)
	$(PY) -c "import ORE, QuantLib, perspective, skfolio, nautilus_trader; print('perspective', perspective.__version__, '| QuantLib', QuantLib.__version__, '| ORE', ORE.__version__, '| skfolio', skfolio.__version__, '| nautilus', nautilus_trader.__version__)"

pricing:     ## QuantLib: one instrument, four engines
	$(PY) -m quantstack.pricing.four_engines

allocation:  ## skfolio: max-Sharpe vs HRP, in and out of sample
	$(PY) -m quantstack.allocation.compare

risk:        ## ORE: NPV + 1000-path exposure simulation + XVA on the 20y swap
	$(PY) -m quantstack.risk.run_ore

bridge: risk ## ORE curve -> standalone QuantLib re-price (the 1 bp bridge test)
	$(PY) -m quantstack.risk.bridge_test

execution:   ## NautilusTrader backtest with skfolio HRP inside the event loop
	$(PY) -m quantstack.execution.backtest

dashboard:   ## Perspective server on http://127.0.0.1:8080 (replays results/, no auth: localhost only)
	$(PY) -m quantstack.dashboard.server --port 8080

all:         ## the whole drivetrain in one process; regenerates every canonical results/ file
	$(PY) scripts/run_all.py

quick:       ## same drivetrain, ORE 16 paths + a short backtest (~10 s; writes results/quick/, gitignored)
	$(PY) scripts/run_all.py --quick

serve:       ## full drivetrain, then keep the live dashboard up on http://127.0.0.1:8080 until Ctrl-C
	$(PY) scripts/run_all.py --serve

test-fast:
	$(PY) -m pytest -q -m "not slow"

test-slow:
	$(PY) -m pytest -q -m slow

test: test-fast test-slow

clean:
	rm -rf results/ore_output results/quick quantstack/risk/Output .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
