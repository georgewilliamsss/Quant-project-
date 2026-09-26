# Five repos, one engine.  Every target runs inside the pinned Python 3.13 venv.
PY ?= .venv/bin/python
UV ?= uv

.PHONY: venv install check pricing allocation risk bridge execution dashboard all test test-fast test-slow clean

venv:
	$(UV) venv .venv --python 3.13

install: venv
	$(UV) pip install --python $(PY) -r requirements.txt

check:  ## all five engines import in ONE process
	$(PY) -c "import perspective, QuantLib, ORE, skfolio, nautilus_trader; print('perspective', perspective.__version__, '| QuantLib', QuantLib.__version__, '| ORE', ORE.__version__, '| skfolio', skfolio.__version__, '| nautilus', nautilus_trader.__version__)"

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

all:         ## the whole drivetrain in one process
	$(PY) scripts/run_all.py

test-fast:
	$(PY) -m pytest -q -m "not slow"

test-slow:
	$(PY) -m pytest -q -m slow

test: test-fast test-slow

clean:
	rm -rf results/ore_output quantstack/risk/Output .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
