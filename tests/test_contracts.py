"""Tests for the four data contracts.  These are the wires; they must be boring
and rock solid, because every module leans on them."""

from datetime import date

import pandas as pd
import pytest

from quantstack import contracts as c


def test_validate_weights_accepts_long_only_partial_investment():
    w = c.validate_weights({"A": 0.5, "B": 0.3})
    assert w == {"A": 0.5, "B": 0.3}


def test_validate_weights_rejects_nan_negative_and_overinvested():
    with pytest.raises(ValueError):
        c.validate_weights({"A": float("nan")})
    with pytest.raises(ValueError):
        c.validate_weights({"A": -0.1, "B": 1.1})
    with pytest.raises(ValueError):
        c.validate_weights({"A": 0.7, "B": 0.7})


def test_validate_weights_clips_tiny_negative_noise():
    w = c.validate_weights({"A": -1e-9, "B": 1.0})
    assert w["A"] == 0.0


class _FakeEstimator:
    def fit(self, X):
        n = X.shape[1]
        self.weights_ = [1.0 / n] * n
        return self


def test_fit_weights_adapter_uses_sklearn_contract():
    rets = pd.DataFrame({"A": [0.01, -0.02, 0.03], "B": [0.0, 0.01, -0.01]})
    w = c.fit_weights(_FakeEstimator(), rets)
    assert w == {"A": 0.5, "B": 0.5}


def test_target_deltas_sells_first_and_respects_cap():
    intents = c.target_deltas(
        weights={"A": 0.5, "B": 0.5},
        equity=10_000.0,
        prices={"A": 10.0, "B": 20.0},
        positions={"A": 1_000.0, "B": 0.0},
        investment_cap=0.98,
    )
    # A: target 0.98*10000*0.5/10 = 490 -> sell 510; B: target 245 -> buy 245
    assert [o.symbol for o in intents] == ["A", "B"]
    assert intents[0].side == "SELL" and intents[0].delta_qty == -510.0
    assert intents[1].side == "BUY" and intents[1].delta_qty == 245.0


def test_target_deltas_liquidates_names_that_left_the_weights():
    intents = c.target_deltas({"B": 1.0}, 1_000.0, {"A": 5.0, "B": 10.0}, {"A": 10.0})
    assert any(o.symbol == "A" and o.delta_qty == -10.0 for o in intents)


def test_target_deltas_skips_zero_and_unpriced():
    intents = c.target_deltas({"A": 0.5, "Z": 0.5}, 1_000.0, {"A": 10.0}, {"A": 49.0})
    assert intents == []  # A already at target (49 = int(490/10)), Z unpriced


def test_position_snapshot_roundtrip(tmp_path):
    snap = c.PositionSnapshot(
        as_of=date(2022, 12, 28),
        positions=[c.Position("AAPL", 100, 130.0), c.Position("MSFT", 50, 240.0)],
        cash=1_000.0,
    )
    assert snap.market_value == 13_000.0 + 12_000.0
    assert snap.equity == 26_000.0
    path = c.write_positions_csv(snap, tmp_path / "positions.csv")
    back = c.read_positions_csv(path)
    assert back.as_of == snap.as_of
    assert [(p.symbol, p.qty, p.last) for p in back.positions] == [
        ("AAPL", 100.0, 130.0),
        ("MSFT", 50.0, 240.0),
    ]
    assert set(snap.to_rows()[0]) == set(c.POSITIONS_SCHEMA)


def test_recording_sink_keeps_last_row_per_symbol_and_full_curve():
    sink = c.RecordingSink()
    sink.update_positions([{"symbol": "A", "qty": 1, "last": 1.0, "value": 1.0}])
    sink.update_positions([{"symbol": "A", "qty": 2, "last": 1.5, "value": 3.0}])
    sink.update_equity([{"date": "2020-01-02", "equity": 100.0}])
    sink.update_equity([{"date": "2020-01-03", "equity": 101.0}])
    assert sink.positions["A"]["qty"] == 2
    curve = sink.equity_curve()
    assert list(curve.values) == [100.0, 101.0]
    assert curve.index.is_monotonic_increasing


def test_null_sink_accepts_anything():
    c.NullSink().update_positions([{"symbol": "A"}])
    c.NullSink().update_equity(iter([]))
    c.NullSink().update_fills([])
