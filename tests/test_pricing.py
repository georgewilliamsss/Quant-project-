"""Tests for quantstack.pricing.four_engines.

These run in well under a minute.  The heaviest non-slow checks are twenty
50,000-sample pseudo-random MC runs (~15 ms each) and one 100,000-point Sobol
run.  The 1,000,000-sample ladder points the CLI uses only run in the slow
end-to-end test, per the brief.
"""

from __future__ import annotations

import json
import math

import QuantLib as ql
import pytest

from quantstack.pricing import four_engines as fe


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def closed_form_call(spot: float, strike: float, rate: float, vol: float, t: float) -> float:
    """Independent Black-Scholes call price (no dividends) built on math.erf.

    It shares no code with QuantLib, so agreement with AnalyticEuropeanEngine
    shows the engine is right, not just unchanged.
    """
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    return spot * _norm_cdf(d1) - strike * math.exp(-rate * t) * _norm_cdf(d2)


@pytest.fixture(autouse=True)
def _restore_evaluation_date():
    """build_process() sets QuantLib's global evaluation date.  Put it back so
    nothing leaks into later QuantLib-using tests in the same process."""
    settings = ql.Settings.instance()
    saved = settings.evaluationDate
    yield
    settings.evaluationDate = saved


@pytest.fixture()
def option_and_process():
    process = fe.build_process()
    option = fe.build_option()
    return option, process


@pytest.fixture()
def small_ladders(monkeypatch):
    """Cheap ladders so the full run_all_engines() path runs in milliseconds."""
    monkeypatch.setattr(fe, "TREE_STEPS_LADDER", [50, 200])
    monkeypatch.setattr(fe, "FD_GRID_LADDER", [20, 100])
    monkeypatch.setattr(fe, "MC_SAMPLES_LADDER", [1_000, 5_000])


@pytest.fixture()
def vanilla_option_constructions(monkeypatch):
    """Count every ql.VanillaOption built while the test runs."""
    real = ql.VanillaOption
    built: list[int] = []

    def counting(*args, **kwargs):
        obj = real(*args, **kwargs)
        built.append(id(obj))
        return obj

    monkeypatch.setattr(fe.ql, "VanillaOption", counting)
    return built


def test_analytic_price(option_and_process):
    option, process = option_and_process
    t = fe.year_fraction()
    assert t == 1.0  # 2026-01-15 -> 2027-01-15 is 365 days under Act/365F
    row = fe.price_analytic(option, process)
    # d1 = 0.2, d2 = 0: C = 100 N(0.2) - 100 e^{-0.02} N(0)
    by_hand = 100.0 * _norm_cdf(0.2) - 100.0 * math.exp(-0.02) * 0.5
    assert closed_form_call(fe.SPOT, fe.STRIKE, fe.RATE, fe.VOL, t) == pytest.approx(by_hand, abs=1e-12)
    assert row["price"] == pytest.approx(by_hand, abs=1e-10)


def test_article_numbers_reproduced_with_366_day_life():
    """The article's 8.9294 / 8.9288 / 8.9295 come from a 1Y option whose life
    spans 29 Feb (T = 366/365).  At the article's evaluation date the same code
    path reproduces them to 4dp.  MC is checked in standard errors, at 50k
    samples to keep the test fast."""
    repro = fe.article_setup_repro(mc_samples=50_000)
    assert repro["days"] == 366
    assert repro["year_fraction"] == pytest.approx(366 / 365, abs=1e-15)
    p = repro["prices"]
    assert p["analytic"]["price"] == pytest.approx(
        closed_form_call(fe.SPOT, fe.STRIKE, fe.RATE, fe.VOL, 366 / 365), abs=1e-10
    )
    for name in ("analytic", "binomial_crr", "fd_black_scholes"):
        assert round(p[name]["price"], 4) == pytest.approx(fe.ARTICLE_REFERENCE[name], abs=1e-9), name
        assert repro["matches_article_4dp"][name]
    mc = p["mc_pseudo_random"]
    assert abs(mc["price"] - fe.ARTICLE_REFERENCE["mc_pseudo_random"]) < 3 * mc["std_error"]


def test_article_repro_restores_evaluation_date(option_and_process):
    fe.article_setup_repro(mc_samples=1_000)
    assert ql.Settings.instance().evaluationDate == fe.EVAL_DATE


def test_binomial_moderate_refinement(option_and_process):
    option, process = option_and_process
    analytic = fe.price_analytic(option, process)["price"]
    price, _ = fe._price(option, ql.BinomialVanillaEngine(process, "crr", 300))
    assert abs(price - analytic) < 0.01


def test_binomial_finest_refinement(option_and_process):
    option, process = option_and_process
    analytic = fe.price_analytic(option, process)["price"]
    price, _ = fe._price(option, ql.BinomialVanillaEngine(process, "crr", fe.TREE_STEPS_LADDER[-1]))
    assert abs(price - analytic) < 0.002


def test_fd_moderate_refinement(option_and_process):
    option, process = option_and_process
    analytic = fe.price_analytic(option, process)["price"]
    price, _ = fe._price(option, ql.FdBlackScholesVanillaEngine(process, 100, 100))
    assert abs(price - analytic) < 0.01


def test_fd_finest_refinement(option_and_process):
    option, process = option_and_process
    analytic = fe.price_analytic(option, process)["price"]
    grid = fe.FD_GRID_LADDER[-1]
    price, _ = fe._price(option, ql.FdBlackScholesVanillaEngine(process, grid, grid))
    assert abs(price - analytic) < 0.002


def test_mc_pseudo_random_within_standard_errors(option_and_process):
    """Pseudo-random MC at 50k samples, judged against its own error estimate.

    At 50k samples SE is about 0.062, so the brief's fixed 0.01 / 0.002
    tolerances are 0.16 / 0.03 SE.  Only a lucky seed meets them: 3 of 40
    seeds met 0.002 in review.  The check that holds for any seed is
    abs_error < 3 SE.  It is run over 20 seeds so a pass cannot come from
    one lucky stream.
    """
    option, process = option_and_process
    analytic = fe.price_analytic(option, process)["price"]
    z_scores = []
    for seed in range(1, 21):
        engine = ql.MCEuropeanEngine(process, "pr", timeStepsPerYear=1, requiredSamples=50_000, seed=seed)
        price, _ = fe._price(option, engine)
        se = option.errorEstimate()
        assert 0.05 < se < 0.075  # sigma_payoff / sqrt(50k), roughly 13.8 / 224
        z_scores.append(abs(price - analytic) / se)
    # 3 SE is a 99.7% band; allow one excursion in 20 so a QuantLib RNG change
    # does not make the test flaky.
    assert sum(z < fe.MC_SE_MULTIPLE for z in z_scores) >= 19
    # And the module's own seed passes.
    engine = fe._mc_engine(process, 50_000, "pr")
    price, _ = fe._price(option, engine)
    assert abs(price - analytic) < fe.MC_SE_MULTIPLE * option.errorEstimate()


def test_mc_sobol_moderate_and_finest(option_and_process):
    """The tight fixed-tolerance MC check, done with a Sobol sequence (the
    same MCEuropeanEngine with 'ld').  It is deterministic and does not
    depend on the seed, so 0.01 at 10k and 0.002 at 100k are real
    convergence results, not luck."""
    option, process = option_and_process
    analytic = fe.price_analytic(option, process)["price"]
    moderate, _ = fe._price(option, fe._mc_engine(process, 10_000, "ld"))
    assert abs(moderate - analytic) < 0.01
    finest, _ = fe._price(option, fe._mc_engine(process, 100_000, "ld"))
    assert abs(finest - analytic) < 0.002
    for seed in (1, 12345):
        engine = ql.MCEuropeanEngine(process, "ld", timeStepsPerYear=1, requiredSamples=100_000, seed=seed)
        again, _ = fe._price(option, engine)
        assert again == finest


def test_instrument_identity(small_ladders, vanilla_option_constructions):
    """The SAME VanillaOption object prices every row, on the exact code path
    main() uses, and all four engines (plus the Sobol variant) are covered.
    Counting constructions catches a ladder that builds its own instrument."""
    process = fe.build_process()
    option = fe.build_option()
    analytic_row, rows = fe.run_all_engines(option, process)
    all_rows = [analytic_row] + rows

    assert vanilla_option_constructions == [id(option)]
    assert fe.check_single_instrument(all_rows, option) == len(all_rows)
    assert {r["instrument_id"] for r in all_rows} == {id(option)}
    assert {r["engine"] for r in all_rows} == {"analytic", *fe.NUMERICAL_ENGINES}

    # Different engines give different numbers, which shows the engine swap
    # took effect rather than a cached NPV being reused.
    finest = {name: [r for r in rows if r["engine"] == name][-1]["price"] for name in fe.NUMERICAL_ENGINES}
    assert len({analytic_row["price"], *finest.values()}) == 1 + len(finest)


def test_identity_check_catches_a_rebuilt_instrument(monkeypatch, small_ladders, vanilla_option_constructions):
    """The check has teeth.  If a ladder quietly prices a freshly built
    option, check_single_instrument (as called by main) rejects the rows."""
    process = fe.build_process()
    option = fe.build_option()
    real_ladder = fe.run_binomial_ladder
    monkeypatch.setattr(
        fe, "run_binomial_ladder", lambda _opt, proc, analytic: real_ladder(fe.build_option(), proc, analytic)
    )
    analytic_row, rows = fe.run_all_engines(option, process)

    assert len(vanilla_option_constructions) == 2
    with pytest.raises(AssertionError, match="not priced on the single instrument"):
        fe.check_single_instrument([analytic_row] + rows, option)


def test_schedule_demo():
    info = fe.schedule_demo()
    assert info["count"] == 21
    assert info["first_dates"][0] == "2016-03-01"
    # 2036-03-01 is a Saturday; Following convention rolls it to Monday.
    assert info["last_dates"][-1] == "2036-03-03"
    assert info["day_count_fraction"]["thirty360_bondbasis"] == pytest.approx(1.0)
    assert info["day_count_fraction"]["actual360"] == pytest.approx(365 / 360)


@pytest.mark.slow
def test_full_cli_run(tmp_path, monkeypatch, vanilla_option_constructions):
    """End-to-end run of main(), including the 1e6-sample MC ladder points,
    the article repro and file I/O.  Marked slow; skipped by default test runs.

    Exactly two instruments are built: one for the brief's setup, which
    prices all 27 convergence rows, and one for the article's 2024 setup,
    which has a different expiry date and so is a different contract."""
    monkeypatch.setattr(fe, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(fe, "FIGURES_DIR", tmp_path / "figures")
    summary = fe.main()
    assert len(vanilla_option_constructions) == 2
    assert (tmp_path / "pricing_convergence.csv").exists()
    assert (tmp_path / "figures" / "pricing_convergence.png").exists()

    on_disk = json.loads((tmp_path / "pricing_summary.json").read_text())
    assert on_disk == json.loads(json.dumps(summary))
    assert on_disk["evaluation_date"] == fe.EVAL_DATE.ISO()
    assert on_disk["market"]["year_fraction"] == 1.0
    assert on_disk["instrument_identity"]["distinct_instrument_ids"] == 1
    assert all(e["check_passed"] for e in on_disk["engines"].values())
    mc = on_disk["engines"]["mc_pseudo_random"]
    assert mc["abs_error_vs_analytic"] < fe.MC_SE_MULTIPLE * mc["std_error"]
    repro = on_disk["article_setup_repro"]
    assert repro["matches_article_4dp"] == {
        "analytic": True,
        "binomial_crr": True,
        "fd_black_scholes": True,
        "mc_pseudo_random": False,  # MC agrees only within SE (~0.03 SE here)
    }
