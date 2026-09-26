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


def test_target_deltas_is_deterministic_on_ties():
    # Same delta for two names: order must not depend on set/hash order.
    kwargs = dict(weights={"B": 0.5, "A": 0.5}, equity=1_000.0, prices={"A": 10.0, "B": 10.0}, positions={})
    out = [o.symbol for o in c.target_deltas(**kwargs)]
    assert out == ["A", "B"]
    kwargs["weights"] = {"A": 0.5, "B": 0.5}
    assert [o.symbol for o in c.target_deltas(**kwargs)] == out


def test_position_snapshot_persists_cash_and_reads_legacy_files(tmp_path):
    snap = c.PositionSnapshot(date(2022, 12, 28), [c.Position("AAPL", 1, 2.0)], cash=51_934.97)
    back = c.read_positions_csv(c.write_positions_csv(snap, tmp_path / "p.csv"))
    assert back.cash == 51_934.97 and back.equity == snap.equity
    (tmp_path / "legacy.csv").write_text("as_of,symbol,qty,last,value\n2022-12-28,AAPL,1,2.0,2.0\n")
    assert c.read_positions_csv(tmp_path / "legacy.csv").cash == 0.0


def test_equity_csv_roundtrip_single_and_multi(tmp_path):
    idx = pd.to_datetime(["2020-01-02", "2020-01-03"])
    single = pd.Series([100.0, 101.5], index=idx)
    back = c.read_equity_csv(c.write_equity_csv(single, tmp_path / "e.csv"))
    assert back.name == "equity" and list(back.values) == [100.0, 101.5]
    multi = pd.DataFrame({"equity_hrp": [1.0, 2.0], "equity_equal_engine": [1.0, 3.0]}, index=idx)
    path = c.write_equity_csv(multi, tmp_path / "m.csv")
    assert c.equity_csv_columns(path) == ["equity_hrp", "equity_equal_engine"]
    assert c.read_equity_csv(path).name == "equity_hrp"  # first equity* column by default
    assert list(c.read_equity_csv(path, "equity_equal_engine").values) == [1.0, 3.0]
    with pytest.raises(ValueError):
        c.read_equity_csv(path, "equity_nope")
    with pytest.raises(ValueError):
        c.write_equity_csv(pd.DataFrame({"pnl": [1.0]}, index=idx[:1]), tmp_path / "bad.csv")
