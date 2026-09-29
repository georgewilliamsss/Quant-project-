#!/usr/bin/env python3
"""
tournament_mc.py - Monte Carlo of strategy archetypes for the Bloomberg Global
Trading Challenge 2026 (12 Oct - 13 Nov 2026, ~25 trading days).

OBJECTIVE
    Only 1st place matters, so every strategy is scored on
        P(win) = P(our benchmark-relative return >= max over the N other teams)
    and not on expected return.

HOW P(win) IS COMPUTED (exact given the model, no field-simulation noise)
    Treat the N other teams as i.i.d. draws from a "team" distribution with
    survival function S_team(x) = P(one team's relative return > x), independent
    of our book. Then
        P(field max <= x) = (1 - S_team(x))**N
        P(win)            = E_ours[ (1 - S_team(X_ours))**N ]
    S_team is a mixture: Normal "bulk" components (closed form) plus a
    "lottery" component whose survival function is estimated from a large
    simulated sample of lottery-team returns. main() also brute-force simulates
    whole fields to check the closed form (see the field-max validation table).

RUN
    python3 tournament_mc.py              full run (200k paths per strategy; about 1-2 min)
    python3 tournament_mc.py --quick      50k paths, for iteration
    python3 tournament_mc.py --calibrate  grid-search the recalibrated field (prints the fit, then exits)

OUTPUTS (written next to this file)
    fig_return_distributions.png  log-scale histograms of relative return, per strategy
    fig_pwin_by_strategy.png      P(win) by strategy, field size N and field model
    fig_sensitivity.png           P(win) sensitivities for the leading strategies
    tournament_mc_output.md       every results table in markdown (the memo quotes these)
    tournament_mc_results.json    headline numbers, machine readable

Every assumption is a parameter in PARAMS below. Change it there and rerun.
numpy + matplotlib only.
"""
import argparse
import copy
import json
import math
import os
import time
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# =============================================================================
# 1. PARAMETERS: every modelling assumption lives here
# =============================================================================
PARAMS = {
    # ---- simulation control -------------------------------------------------
    'seed': 20261012,
    'n_paths': 200_000,            # paths per strategy evaluation (brief: >= 200k)
    'n_lottery_samples': 400_000,  # samples behind each field's lottery-team CDF
    'n_bruteforce_fields': 4_000,  # whole-field replications used only to validate (1-S)^N
    'field_sizes': [1000, 3000, 5000],
    'base_N': 3000,                # ~2,450 teams (2024), ~2,650 (2025); expect ~3,000 in 2026

    # ---- competition constraints -------------------------------------------
    'n_slots': 5,        # fully invested, max 20% per name -> 5 slots of 20%
    'window_days': 25,   # trading days, Oct 12 - Nov 13 2026
    'floor': -0.95,      # a single stock cannot lose more than 95% in one event/round

    # ---- benchmark (WLS index) ---------------------------------------------
    # Relative return = our return - index return (arithmetic difference; this is
    # how Bloomberg's "Rel P&L" appears to work, see 05_rules_and_past_winners.md).
    # beta_stock = 0 is the brief's literal spec: block returns are drawn
    # independently of the index, so relative = ours - index. beta_stock = 1
    # would make the index cancel exactly. Either way the effect is small
    # (5% index sd against winning margins of +100% or more).
    'index': {'mu': 0.0, 'sd': 0.05, 'beta_stock': 0.0},

    # ---- building block: PDUFA binary (per event) ---------------------------
    # approval_model 'two_regime' (default): 50% of approvals "priced in" U(+5%,+20%),
    # 50% "big pop" U(+40%,+120%). 'normal': approval ~ N(+25%, 20%).
    # approve_scale multiplies approval returns (1.0 = briefed; 0.27 makes EV = 0).
    # Expected return per event at these defaults: 0.8*46.25% - 0.2*50% = +27%.
    'pdufa': {'p_approve': 0.80, 'approval_model': 'two_regime',
              'frac_priced_in': 0.5, 'priced_in': (0.05, 0.20), 'big_pop': (0.40, 1.20),
              'normal_mu': 0.25, 'normal_sd': 0.20, 'approve_scale': 1.0,
              'crl_mu': -0.50, 'crl_sd': 0.15},

    # ---- building block: Phase 3 readout (per event) ------------------------
    # EV per event: 0.55*80% - 0.45*65% = +14.75%
    'phase3': {'p_success': 0.55, 'succ_mu': 0.80, 'succ_sd': 0.40,
               'fail_mu': -0.65, 'fail_sd': 0.15},

    # ---- building block: earnings roulette (per event) ----------------------
    # move = s * T_df, s chosen so E|move| = mean_abs_move. Positive skew:
    # up-moves x(1+skew), down-moves x(1-skew) -> E|move| unchanged, mean = +2.5%.
    'earnings': {'df': 3.0, 'mean_abs_move': 0.25, 'skew': 0.10, 'shift': 0.0,
                 'rounds': 4, 'max_up': 3.0},

    # ---- building block: weekly momentum rotation (manager's S8) ------------
    # Each slot rotates every ~5 days into the current top mover. Weekly return
    # ~ s * T_2.5 with E|move| = 15%, 5 rounds compounding. p_moon: optional
    # chance that a slot is a 5-10x microcap over the window (used by the field).
    'rotation': {'df': 2.5, 'mean_abs_move': 0.15, 'rounds': 5, 'max_up': 3.0,
                 'p_moon': 0.0, 'moon_gross': (5.0, 10.0)},

    # ---- building block: momentum / theme basket (one month) ----------------
    # per-name return = drift + regime shift + sd*(sqrt(rho)*M + sqrt(1-rho)*eps)
    # regime (common to the theme): melt-up p=0.15 adds +60%; crash p=0.20 adds -35%.
    # EV per name: 8% + 0.15*60% - 0.20*35% = +10% per month.
    'theme': {'drift': 0.08, 'sd': 0.35, 'rho': 0.70,
              'p_melt': 0.15, 'melt_add': 0.60, 'p_crash': 0.20, 'crash_add': -0.35},

    # ---- building block: short-squeeze candidate (one month) ----------------
    # EV: 0.15*120% + 0.85*(-10%) = +9.5%
    'squeeze': {'p': 0.15, 'mu': 1.20, 'sd': 0.60, 'else_mu': -0.10, 'else_sd': 0.25},

    # ---- strategy knobs ------------------------------------------------------
    'k_seq': 3,          # sequential binary events per slot (S3, S5, S6, S7)
    'rho_binary': 0.0,   # one-factor Gaussian-copula correlation among OUR binaries

    # ---- field models --------------------------------------------------------
    # bulk: list of (weight, mean, sd) Normal components of relative return.
    # lottery: teams that run one of the strategies below (weights in 'mix'),
    #          with parameter overrides applied to their building blocks.
    # crowd_frac: share of lottery teams holding a 5-name basket in OUR theme
    #             (sensitivity only; 0 = everybody's theme is independent of ours).
    'fields': {
        'briefed': {
            'label': 'F-briefed',
            'desc': '80% N(0,8%) + 15% N(0,20%) + 5% lottery teams holding 5 static PDUFA binaries (as briefed)',
            'bulk': [(0.80, 0.0, 0.08), (0.15, 0.0, 0.20)],
            'w_lottery': 0.05,
            'lottery': {'mix': {'S1': 1.0}, 'overrides': {}},
            'crowd_frac': 0.0,
        },
        # Recalibrated to history (run --calibrate to reproduce the grid search).
        # Targets: median field max ~ +100..+170% and 90th pct ~ +300% at N=3,000, plus the
        # 2025 rank facts (of ~2,650 teams: #69 at +5.3%, #9 at +23%, #6 at +44%).
        # Best fit of a 600-point grid: bulk sds = briefed x 0.25 (N(0,2%) / N(0,5%)), and
        # only 1% of teams are "lottery" teams, but they compound a very fat process:
        # 5 slots rolling 5 weekly t(2.5) moves with E|move| = 30% (2x our S8), weekly
        # moves capped at +900%, no trimming. Fit: median max +142%, p90 +274%;
        # teams above +5.3/+23/+44% per 2,650 = 80/7.8/4.8 (actual 69/9/6).
        # A larger lottery share overshoots the rank facts; 5-10x microcap
        # moonshots (rotation.p_moon) did not improve the fit, so p_moon = 0.
        'recal': {
            'label': 'F-recal',
            'desc': 'recalibrated to 2023-25 winners: 99% tight bulk N(0,2%)/N(0,5%) + 1% lottery teams compounding weekly t(2.5) rotations with E|move| 30%',
            'bulk': [(0.80 * 0.99 / 0.95, 0.0, 0.08 * 0.25), (0.15 * 0.99 / 0.95, 0.0, 0.20 * 0.25)],
            'w_lottery': 0.01,
            'lottery': {'mix': {'S8': 1.0},
                        'overrides': {'rotation.mean_abs_move': 0.30, 'rotation.max_up': 9.0,
                                      'rotation.p_moon': 0.0}},
            'crowd_frac': 0.0,
        },
    },
    'base_field': 'recal',

    # ---- history used for calibration (05_rules_and_past_winners.md) ---------
    'history': [
        (2023, 1727, 0.637, 'HKU, +67.7% return, +$637k relative profit on $1M, 6 weeks'),
        (2024, 2453, 1.677, 'RIT, relative profit $1,676,618 on $1M'),
        (2025, 2650, 3.10, 'CUHK, $1M -> $4.1M (+310%; press headline ">400%")'),
    ],
    'rank_facts_2025': [(0.053, 69), (0.23, 9), (0.44, 6)],   # (relative return, rank) of ~2,650
    'brief_alt_winners': [0.40, 0.60, 1.00],                  # manager's alternative calibration
    'scaled_targets': [0.40, 0.60, 1.00, 1.68, 3.10],
}

STRATEGY_ORDER = ['S1', 'S2', 'S2i', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'S9']


def strategy_spec(name, P):
    """Slot layout of each strategy. All slots are 20% at inception.
    binary = (event type, number of slots, events per slot in sequence)
    theme  = number of slots in ONE theme basket (shared regime and factor)
    indep  = number of momentum names each drawn from its own, unrelated theme
    idle_after = after its single event the slot sits in index-like stocks
    """
    k = P['k_seq']
    n = P['n_slots']
    E = P['earnings']['rounds']
    Rr = P['rotation']['rounds']
    specs = {
        'S1': dict(short='S1 static PDUFA x5', binary=('pdufa', n, 1), idle_after=True,
                   label='5 independent PDUFA binaries, one event each, then index-like'),
        'S2': dict(short='S2 one-theme basket', theme=n,
                   label='5 names in one momentum theme (rho=0.7, shared melt-up/crash)'),
        'S2i': dict(short='S2i 5 unrelated themes', indep=n,
                    label='Control: same per-name momentum marginal as S2, 5 unrelated themes'),
        'S3': dict(short=f'S3 seq PDUFA k={k}', binary=('pdufa', n, k),
                   label=f'5 slots, each rolling through {k} PDUFA binaries'),
        'S4': dict(short=f'S4 earnings x{E}', binary=('earnings', n, E),
                   label=f'5 slots, each rolling through {E} earnings events (t3, E|move|=25%)'),
        'S5': dict(short=f'S5 2 theme+3 seqPDUFA', binary=('pdufa', 3, k), theme=2,
                   label=f'2 theme slots + 3 slots rolling {k} PDUFA binaries'),
        'S6': dict(short=f'S6 3 theme+2 seqPDUFA', binary=('pdufa', 2, k), theme=3,
                   label=f'3 theme slots + 2 slots rolling {k} PDUFA binaries'),
        'S7': dict(short=f'S7 seq Phase3 k={k}', binary=('phase3', n, k),
                   label=f'5 slots, each rolling through {k} Phase 3 readouts'),
        'S8': dict(short=f'S8 weekly rotation x{Rr}', binary=('rotation', n, Rr),
                   label=f'5 slots rotating weekly into top movers, t2.5, E|move|=15%, {Rr} rounds'),
        'S9': dict(short='S9 squeeze x5', binary=('squeeze', n, 1),
                   label='5 short-squeeze candidates held all month (extra)'),
    }
    return specs[name]


# =============================================================================
# 2. MATH HELPERS (numpy has no erfc / normal cdf; scipy is not allowed)
# =============================================================================
SQRT2 = math.sqrt(2.0)


def erfc(x):
    """Complementary error function, Numerical Recipes 'erfcc' (Chebyshev fit).
    Fractional error < 1.2e-7 everywhere, including deep in the tail. That matters
    because (1 - S)**N multiplies tail errors by N."""
    x = np.asarray(x, dtype=float)
    z = np.abs(x)
    t = 1.0 / (1.0 + 0.5 * z)
    poly = (-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (
        -0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (
            -0.82215223 + t * 0.17087277)))))))))
    r = t * np.exp(poly)
    return np.where(x >= 0, r, 2.0 - r)


def norm_sf(z):
    """P(Z > z) for standard normal Z."""
    return 0.5 * erfc(np.asarray(z) / SQRT2)


def norm_cdf(z):
    return norm_sf(-np.asarray(z))


def correlated_uniforms(rng, n_paths, n_names, rho):
    """One-factor Gaussian copula: U_i = Phi(sqrt(rho) M + sqrt(1-rho) e_i).
    rho = 0 gives independent uniforms."""
    if rho <= 0.0:
        return rng.random((n_paths, n_names))
    M = rng.standard_normal((n_paths, 1))
    e = rng.standard_normal((n_paths, n_names))
    u = norm_cdf(math.sqrt(rho) * M + math.sqrt(1.0 - rho) * e)
    return np.clip(u, 1e-12, 1 - 1e-12)


def t_mean_abs(df):
    """E|T| for Student-t with df > 1."""
    return 2.0 * math.sqrt(df) * math.gamma((df + 1) / 2) / (
        math.sqrt(math.pi) * (df - 1) * math.gamma(df / 2))


def emp_sf(sorted_sample, x):
    """Empirical P(L > x) from a sorted sample."""
    return 1.0 - np.searchsorted(sorted_sample, x, side='right') / sorted_sample.size


def with_overrides(P, overrides):
    """Deep-copy P and set dotted keys, e.g. {'pdufa.p_approve': 0.7}."""
    Q = copy.deepcopy(P)
    for key, val in overrides.items():
        d = Q
        parts = key.split('.')
        for p in parts[:-1]:
            d = d[p]
        d[parts[-1]] = val
    return Q


def ev_neutral(P):
    """'EV-neutral world': keep every payoff shape but make each building block's
    expected return ~0, as an efficient market would price it.
      binaries: set P(good outcome) to the market-implied fair odds for the payoffs
      theme: drift chosen so drift + p_melt*melt + p_crash*crash = 0
      earnings: remove the +2.5% mean created by the skew
    The rotation block is already mean-zero (symmetric t)."""
    Q = copy.deepcopy(P)
    d = Q['pdufa']
    if d['approval_model'] == 'two_regime':
        f = d['frac_priced_in']
        e_app = d['approve_scale'] * (f * np.mean(d['priced_in']) + (1 - f) * np.mean(d['big_pop']))
    else:
        e_app = d['approve_scale'] * d['normal_mu']
    d['p_approve'] = -d['crl_mu'] / (e_app - d['crl_mu'])
    ph = Q['phase3']
    ph['p_success'] = -ph['fail_mu'] / (ph['succ_mu'] - ph['fail_mu'])
    sq = Q['squeeze']
    sq['p'] = -sq['else_mu'] / (sq['mu'] - sq['else_mu'])
    th = Q['theme']
    th['drift'] = -(th['p_melt'] * th['melt_add'] + th['p_crash'] * th['crash_add'])
    er = Q['earnings']
    rng = np.random.default_rng(12345)
    m = np.maximum(draw_t_move(rng, 1_000_000, er['df'], er['mean_abs_move'], er['skew'], 0.0, er['max_up']),
                   P['floor'])
    er['shift'] = -float(m.mean())   # removes the skew-induced mean and the floor/cap effect
    return Q


# =============================================================================
# 3. BUILDING BLOCKS (all return simple returns; uniforms u: high u = good outcome)
#    Every branch draws full-size arrays so random numbers are shared across
#    parameter values (common random numbers keep sensitivities smooth).
# =============================================================================
def draw_pdufa(rng, u, d):
    q = 1.0 - d['p_approve']
    z = rng.standard_normal(u.shape)
    r_crl = d['crl_mu'] + d['crl_sd'] * z
    v = np.clip((u - q) / max(d['p_approve'], 1e-12), 0.0, 1.0)  # uniform within approvals
    if d['approval_model'] == 'two_regime':
        f = d['frac_priced_in']
        a0, a1 = d['priced_in']
        b0, b1 = d['big_pop']
        r_app = np.where(v < f, a0 + (a1 - a0) * v / f, b0 + (b1 - b0) * (v - f) / (1 - f))
    else:
        r_app = d['normal_mu'] + d['normal_sd'] * z
    return np.where(u < q, r_crl, d['approve_scale'] * r_app)


def draw_phase3(rng, u, d):
    z = rng.standard_normal(u.shape)
    ok = u >= 1.0 - d['p_success']
    return np.where(ok, d['succ_mu'] + d['succ_sd'] * z, d['fail_mu'] + d['fail_sd'] * z)


def draw_squeeze(rng, u, d):
    z = rng.standard_normal(u.shape)
    sq = u >= 1.0 - d['p']
    return np.where(sq, d['mu'] + d['sd'] * z, d['else_mu'] + d['else_sd'] * z)


def draw_t_move(rng, shape, df, mean_abs, skew=0.0, shift=0.0, max_up=np.inf):
    """Student-t move scaled so E|move| = mean_abs, optional up/down asymmetry."""
    t = rng.standard_t(df, size=shape)
    s = mean_abs / t_mean_abs(df)
    m = s * t * np.where(t > 0, 1.0 + skew, 1.0 - skew) + shift
    return np.minimum(m, max_up)


def draw_theme(rng, n_paths, n_names, d):
    """Returns (per-name returns [n_paths, n_names], common centre [n_paths]).
    The common centre (drift + regime + factor) is what a crowd of teams holding
    the same theme would share with us."""
    ureg = rng.random(n_paths)
    melt = ureg < d['p_melt']
    crash = (~melt) & (ureg < d['p_melt'] + d['p_crash'])
    shift = np.where(melt, d['melt_add'], np.where(crash, d['crash_add'], 0.0))
    M = rng.standard_normal(n_paths)
    eps = rng.standard_normal((n_paths, n_names))
    rho = d['rho']
    centre = d['drift'] + shift + d['sd'] * math.sqrt(rho) * M
    r = centre[:, None] + d['sd'] * math.sqrt(1.0 - rho) * eps
    return r, centre


# =============================================================================
# 4. STRATEGY ENGINE
# =============================================================================
def simulate(name, P, n=None, stream=0):
    """Simulate one strategy. Returns dict with benchmark-relative returns under
      rel_a: (a) no rebalancing - each slot compounds on its own, winners may grow
             beyond 20% of the book (assumed allowed if organic);
      rel_b: (b) forced trim to 20% after every event, proceeds spread into the
             other slots. With exactly 5 slots and full investment that is the same
             as re-equalising all slots to 20% after each event, so the book
             compounds event by event: gross_b = prod_e (1 + 0.2 r_e). Events are
             staggered (one event per rebalance), so the order does not matter.
    plus the index path and the theme centre (for the crowding sensitivity)."""
    n = int(n or P['n_paths'])
    spec = strategy_spec(name, P)
    rng = np.random.default_rng([P['seed'], zlib.crc32(name.encode()), stream])
    n_slots = P['n_slots']
    w = 1.0 / n_slots
    floor = P['floor']
    I = P['index']['mu'] + P['index']['sd'] * rng.standard_normal(n)

    slot_gross = []   # list of [n, m] arrays; binary slots first
    ev = None         # [n, n_binary_slots, k] event returns (binary / sequential slots)
    if spec.get('binary'):
        etype, nb, k = spec['binary']
        ev = np.empty((n, nb, k))
        for j in range(k):   # j-th event of every binary slot
            if etype == 'pdufa':
                u = correlated_uniforms(rng, n, nb, P['rho_binary'])
                r = draw_pdufa(rng, u, P['pdufa'])
            elif etype == 'phase3':
                u = correlated_uniforms(rng, n, nb, P['rho_binary'])
                r = draw_phase3(rng, u, P['phase3'])
            elif etype == 'squeeze':
                r = draw_squeeze(rng, rng.random((n, nb)), P['squeeze'])
            elif etype == 'earnings':
                d = P['earnings']
                r = draw_t_move(rng, (n, nb), d['df'], d['mean_abs_move'], d['skew'], d['shift'], d['max_up'])
            elif etype == 'rotation':
                d = P['rotation']
                r = draw_t_move(rng, (n, nb), d['df'], d['mean_abs_move'], 0.0, 0.0, d['max_up'])
            else:
                raise ValueError(etype)
            ev[:, :, j] = np.maximum(r, floor)
        g = np.prod(1.0 + ev, axis=2)
        if etype == 'rotation' and P['rotation']['p_moon'] > 0:
            # rare 5-10x microcap in a slot (used by the recalibrated field's lottery teams)
            lo, hi = P['rotation']['moon_gross']
            moon = rng.random(g.shape) < P['rotation']['p_moon']
            g = np.where(moon, lo + (hi - lo) * rng.random(g.shape), g)
        slot_gross.append(g)

    theme_centre = None
    if spec.get('theme'):
        r, theme_centre = draw_theme(rng, n, spec['theme'], P['theme'])
        slot_gross.append(1.0 + np.maximum(r, floor))
    if spec.get('indep'):
        m = spec['indep']
        r, _ = draw_theme(rng, n * m, 1, P['theme'])
        slot_gross.append(1.0 + np.maximum(r.reshape(n, m), floor))

    G = np.concatenate(slot_gross, axis=1)
    assert G.shape[1] == n_slots, (name, G.shape)

    # (a) no rebalancing: book = average of slot gross returns
    gross_a = G.mean(axis=1)

    # (b) trim to 20% after each event (== re-equalise the 5 slots)
    if ev is None:
        gross_b = gross_a.copy()   # one-period theme books: nothing discrete to trim
    else:
        nb = ev.shape[1]
        R = nb * ev.shape[2]                 # number of staggered events = rebalances
        cont = G[:, nb:]                     # continuous (theme) slots, spread evenly over rounds
        per_round = (cont ** (1.0 / R) - 1.0).sum(axis=1) if cont.shape[1] else np.zeros(n)
        evf = ev.reshape(n, R)   # (moonshots, if enabled, only enter policy (a); the field uses (a))
        gross_b = np.prod(1.0 + w * (evf + per_round[:, None]), axis=1)

    # index exposure: S1 slots sit in index-like stocks after their event
    beta = P['index']['beta_stock']
    if spec.get('idle_after'):
        idle = rng.random((n, n_slots)).mean(axis=1)   # fraction of window after the event
    else:
        idle = 0.0
    c = idle + beta * (1.0 - idle)
    rel_a = gross_a - 1.0 + c * I - I
    rel_b = gross_b - 1.0 + c * I - I
    return {'name': name, 'rel_a': rel_a, 'rel_b': rel_b, 'I': I,
            'theme_centre': theme_centre, 'spec': spec}


# =============================================================================
# 5. FIELD MODEL
# =============================================================================
class Field:
    """Other teams: i.i.d. mixture of Normal bulk components and lottery teams."""

    def __init__(self, key, spec, P, n_samples, crowd_sample=None):
        self.key = key
        self.spec = spec
        self.bulk = spec['bulk']
        self.wL = spec['w_lottery']
        self.label = spec['label']
        # lottery teams' relative returns: simulate their strategies (policy (a))
        PL = with_overrides(P, spec['lottery']['overrides'])
        parts = []
        for strat, wt in spec['lottery']['mix'].items():
            m = max(1, int(round(n_samples * wt)))
            parts.append(simulate(strat, PL, n=m, stream=1000 + zlib.crc32(key.encode()) % 997)['rel_a'])
        self.L = np.sort(np.concatenate(parts))
        self.crowd_sample = crowd_sample   # sorted S2 sample, used when we hold no theme

    def team_sf(self, x):
        """P(one team's relative return > x)."""
        S = np.zeros_like(x, dtype=float)
        for wt, mu, sd in self.bulk:
            S += wt * norm_sf((x - mu) / sd)
        S += self.wL * emp_sf(self.L, x)
        return np.clip(S, 0.0, 1.0 - 1e-16)

    def crowd_sf(self, x, sim):
        """P(one crowd team beats x). Crowd teams hold a 5-name basket in OUR theme:
        same regime, same theme factor and same index draw as us; only their
        idiosyncratic name noise differs. If we hold no theme, they hold an
        unrelated one (independent S2 draws)."""
        if sim is not None and sim['theme_centre'] is not None:
            th = sim['P']['theme']
            sd_idio = th['sd'] * math.sqrt(1.0 - th['rho']) / math.sqrt(5.0)
            S = norm_sf((x + sim['I'] - sim['theme_centre']) / sd_idio)
        else:
            S = emp_sf(self.crowd_sample, x)
        return np.clip(S, 0.0, 1.0 - 1e-16)

    def log_cdf_max(self, x, N):
        return N * np.log1p(-self.team_sf(np.asarray(x, dtype=float)))

    def max_quantiles(self, N, qs):
        grid = np.linspace(-0.5, 15.0, 62001)
        lF = self.log_cdf_max(grid, N)
        return np.interp(np.log(np.asarray(qs)), lF, grid)

    def p_max_below(self, N, xs):
        return np.exp(self.log_cdf_max(np.asarray(xs, dtype=float), N))

    def p_win(self, rel, N, scale=1.0, n_crowd=0, sim=None):
        """E[(1 - S_team(X))^N * (1 - S_crowd(X))^n_crowd].
        scale != 1 evaluates against the field max stretched by 1/scale (used for
        the 'winner typically = T' table). n_crowd adds that many extra teams
        holding a basket in our theme (crowding sensitivity)."""
        x = rel * scale
        lg = N * np.log1p(-self.team_sf(x))
        if n_crowd:
            lg = lg + n_crowd * np.log1p(-self.crowd_sf(x, sim))
        return float(np.mean(np.exp(lg)))

    def brute_force_max(self, N, reps, rng):
        """Direct simulation of whole fields (validation only)."""
        out = np.empty(reps)
        ws = [b[0] for b in self.bulk] + [self.wL]
        ws = np.array(ws) / np.sum(ws)
        chunk = 200
        for i0 in range(0, reps, chunk):
            m = min(chunk, reps - i0)
            t = rng.choice(len(ws), size=(m, N), p=ws)
            x = rng.standard_normal((m, N))
            for i, (_, mu, sd) in enumerate(self.bulk):
                x = np.where(t == i, mu + sd * x, x)
            lot = t == len(self.bulk)
            x[lot] = self.L[rng.integers(0, self.L.size, size=int(lot.sum()))]
            out[i0:i0 + m] = x.max(axis=1)
        return out


# =============================================================================
# 6. REPORTING HELPERS
# =============================================================================
def fp(p):
    """Format a probability as a percentage with sensible precision."""
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return 'n/a'
    if p < 5e-6:
        return '<0.001%'
    if p < 1e-3:
        return f'{100 * p:.3f}%'
    if p < 1e-2:
        return f'{100 * p:.2f}%'
    return f'{100 * p:.1f}%'


def fr(x):
    """Format a return."""
    return f'{100 * x:+.0f}%'


def stats_row(rel):
    q = np.percentile(rel, [50, 90, 99])
    return {'mean': float(rel.mean()), 'median': float(q[0]), 'p90': float(q[1]), 'p99': float(q[2]),
            'P>50': float((rel > 0.5).mean()), 'P>100': float((rel > 1.0).mean()),
            'P>200': float((rel > 2.0).mean())}


def md_table(header, rows):
    out = ['| ' + ' | '.join(header) + ' |', '|' + '|'.join(['---'] * len(header)) + '|']
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out)


class Report:
    def __init__(self):
        self.parts = []

    def h(self, text):
        self.parts.append(f'\n### {text}\n')
        print(f'\n=== {text} ===')

    def t(self, header, rows, note=None):
        s = md_table(header, rows)
        self.parts.append(s + '\n')
        print(s)
        if note:
            self.parts.append(f'\n{note}\n')
            print(note)

    def p(self, text):
        self.parts.append(text + '\n')
        print(text)

    def save(self, path):
        with open(path, 'w') as f:
            f.write('# tournament_mc.py output (generated, do not edit by hand)\n')
            f.write('\n'.join(self.parts))


# =============================================================================
# 7. FIELD CALIBRATION (grid search; run with --calibrate)
# =============================================================================
def calibrate(P):
    """Grid search the recalibrated field: lottery share, lottery weekly move,
    microcap probability and bulk dispersion factor, against
    median max ~ +135%, p90 max ~ +300% (N=3,000) and the 2025 rank facts."""
    N = P['base_N']
    results = []
    for m_L, max_up, p_moon in [(m, u, pm) for m in [0.15, 0.20, 0.25, 0.30, 0.35]
                                for u in [3.0, 9.0] for pm in [0.0, 0.003, 0.01]]:
            spec = copy.deepcopy(P['fields']['recal'])
            spec['lottery']['overrides'] = {'rotation.mean_abs_move': m_L, 'rotation.p_moon': p_moon,
                                            'rotation.max_up': max_up}
            base = Field('cal', spec, P, 200_000)
            for wL in [0.01, 0.015, 0.02, 0.03, 0.05]:
                for b in [0.15, 0.2, 0.25, 0.35]:
                    base.wL = wL
                    base.bulk = [(0.80 * (1 - wL) / 0.95, 0.0, 0.08 * b), (0.15 * (1 - wL) / 0.95, 0.0, 0.20 * b)]
                    med, p90 = base.max_quantiles(N, [0.5, 0.9])
                    sf = base.team_sf(np.array([0.053, 0.23, 0.44]))
                    tgt = np.array([69, 9, 6]) / 2650.0
                    loss = ((med - 1.35) / 0.35) ** 2 + ((p90 - 3.0) / 0.6) ** 2 + \
                        0.5 * np.sum(np.log(np.maximum(sf, 1e-9) / tgt) ** 2)
                    results.append((loss, m_L, p_moon, wL, b, med, p90, *(sf * 2650), max_up))
    results.sort(key=lambda r: r[0])
    print('loss  m_L  p_moon  wL   b    med_max  p90_max  #>5.3%  #>23%  #>44%  max_up (per 2,650; 2025 actual 69 / 9 / 6)')
    for r in results[:20]:
        print(f'{r[0]:.3f} {r[1]:.3f} {r[2]:.3f} {r[3]:.2f} {r[4]:.2f}  {r[5]:+.2f}   {r[6]:+.2f}   '
              f'{r[7]:6.1f} {r[8]:6.1f} {r[9]:6.1f}  {r[10]:.0f}')


# =============================================================================
# 8. MAIN ANALYSIS
# =============================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true', help='50k paths per strategy')
    ap.add_argument('--calibrate', action='store_true', help='grid-search the recalibrated field and exit')
    ap.add_argument('--no-charts', action='store_true')
    args = ap.parse_args()
    t0 = time.time()
    P = copy.deepcopy(PARAMS)
    if args.quick:
        P['n_paths'] = 50_000
        P['n_lottery_samples'] = 150_000
        P['n_bruteforce_fields'] = 1_000
    if args.calibrate:
        calibrate(P)
        return

    PE = ev_neutral(P)       # EV-neutral world
    sizes = P['field_sizes']
    N0 = P['base_N']
    rep = Report()
    results = {'params': {k: v for k, v in P.items() if k != 'fields'}, 'fields': {}}

    # ---------------------------------------------------------------- blocks
    rep.h('T1. Expected return per event embedded in each building block')
    rows = []
    for label, fn in [('PDUFA', 'S1'), ('Phase 3', 'S7'), ('Earnings', 'S4'), ('Rotation (weekly)', 'S8'),
                      ('Squeeze', 'S9')]:
        vals = []
        for world in (P, PE):
            rng = np.random.default_rng(7)
            n = 400_000
            if fn == 'S1':
                r = draw_pdufa(rng, rng.random(n), world['pdufa'])
                pr = world['pdufa']['p_approve']
            elif fn == 'S7':
                r = draw_phase3(rng, rng.random(n), world['phase3'])
                pr = world['phase3']['p_success']
            elif fn == 'S9':
                r = draw_squeeze(rng, rng.random(n), world['squeeze'])
                pr = world['squeeze']['p']
            elif fn == 'S4':
                d = world['earnings']
                r = draw_t_move(rng, n, d['df'], d['mean_abs_move'], d['skew'], d['shift'], d['max_up'])
                pr = None
            else:
                d = world['rotation']
                r = draw_t_move(rng, n, d['df'], d['mean_abs_move'], 0.0, 0.0, d['max_up'])
                pr = None
            r = np.maximum(r, P['floor'])
            vals.append((r.mean(), r.std(), pr))
        rows.append([label, fr(vals[0][0]), f'{100 * vals[0][1]:.0f}%', fr(vals[1][0]),
                     '' if vals[1][2] is None else f'P(good) {vals[0][2]:.2f} -> {vals[1][2]:.3f}'])
    th, the = P['theme'], PE['theme']
    r_b = np.maximum(draw_theme(np.random.default_rng(7), 400_000, 1, th)[0], P['floor'])
    r_e = np.maximum(draw_theme(np.random.default_rng(7), 400_000, 1, the)[0], P['floor'])
    rows.append(['Theme name (month)', fr(r_b.mean()), f'{100 * r_b.std():.0f}%', fr(r_e.mean()),
                 f"drift {th['drift']:+.2f} -> {the['drift']:+.2f}"])
    rep.t(['Block', 'Mean (briefed)', 'Sd (briefed)', 'Mean (EV-neutral)', 'EV-neutral change'], rows)

    # ---------------------------------------------------------------- fields
    print('\nBuilding field models ...')
    s2_briefed = np.sort(simulate('S2', P, n=P['n_lottery_samples'], stream=77)['rel_a'])
    fields = {}
    for key, spec in P['fields'].items():
        fields[key] = Field(key, spec, P, P['n_lottery_samples'], crowd_sample=s2_briefed)
    # EV-neutral world: the briefed field's lottery teams play EV-neutral binaries too
    fields_evn = {'briefed': Field('briefed', P['fields']['briefed'], PE, P['n_lottery_samples'], s2_briefed),
                  'recal': fields['recal']}
    FKEYS = ['recal', 'briefed']   # base field first

    rep.h('T2. Distribution of the field maximum (winning relative return)')
    qs = [0.10, 0.25, 0.50, 0.75, 0.90, 0.99]
    rows = []
    for key in FKEYS:
        for N in sizes:
            qv = fields[key].max_quantiles(N, qs)
            rows.append([fields[key].label, f'{N:,}'] + [fr(v) for v in qv])
            results['fields'].setdefault(key, {})[N] = {f'q{int(q * 100)}': float(v) for q, v in zip(qs, qv)}
    for N in sizes:
        qv = fields_evn['briefed'].max_quantiles(N, qs)
        rows.append(['F-briefed, EV-neutral world', f'{N:,}'] + [fr(v) for v in qv])
    rep.t(['Field', 'N'] + [f'p{int(q * 100)}' for q in qs], rows)

    rep.h('T2b. Validation: closed-form (1-S)^N vs brute-force simulated fields, N=3,000')
    rng_bf = np.random.default_rng(99)
    rows = []
    for key in FKEYS:
        bf = fields[key].brute_force_max(N0, P['n_bruteforce_fields'], rng_bf)
        cf = fields[key].max_quantiles(N0, [0.1, 0.5, 0.9])
        rows.append([fields[key].label, P['n_bruteforce_fields']] +
                    [f'{fr(a)} / {fr(b)}' for a, b in zip(cf, np.percentile(bf, [10, 50, 90]))])
    rep.t(['Field', 'Brute-force fields', 'p10 closed/brute', 'p50 closed/brute', 'p90 closed/brute'], rows)

    rep.h('T3. Calibration against history: which field model matches?')
    rows = []
    for key in FKEYS:
        F = fields[key]
        sf = F.team_sf(np.array([x for x, _ in P['rank_facts_2025']]))
        med, p90 = F.max_quantiles(N0, [0.5, 0.9])
        pw_hist = [float(1 - F.p_max_below(n_t, [x])[0]) for (_, n_t, x, _) in P['history']]
        rows.append([F.label, fr(med), fr(p90)] + [f'{v * 2650:.1f}' for v in sf] +
                    [fp(v) for v in pw_hist])
    rep.t(['Field', 'median max (N=3k)', 'p90 max', '# teams > +5.3% (2025: 69)', '# > +23% (2025: 9)',
           '# > +44% (2025: 6)', 'P(max >= +64%) N=1,727 (2023)', 'P(max >= +168%) N=2,453 (2024)',
           'P(max >= +310%) N=2,650 (2025)'], rows)
    rows = []
    cands = P['brief_alt_winners'] + [0.68, 1.68, 3.10]
    for lab, F in [('F-recal', fields['recal']), ('F-briefed', fields['briefed']),
                   ('F-briefed, EV-neutral world', fields_evn['briefed'])]:
        meds = [F.max_quantiles(N, [0.5])[0] for N in sizes]
        near = [min(cands, key=lambda t: abs(t - m)) for m in meds]
        rows.append([lab] + [f'{fr(m)} (nearest {fr(t)})' for m, t in zip(meds, near)])
    rep.t(['Field'] + [f'median field max, N={N:,}' for N in sizes], rows,
          note='Candidates: the brief\'s +40/+60/+100% alternatives and the actual winners +68% (2023), '
               '+168% (2024), +310% (2025).')

    rep.h('T4. What return do we need? P(field max below X)')
    xs = [0.5, 1.0, 2.0, 3.0]
    rows = []
    for key in FKEYS:
        for N in sizes:
            pb = fields[key].p_max_below(N, xs)
            rows.append([fields[key].label, f'{N:,}'] + [fp(v) for v in pb])
    rep.t(['Field', 'N'] + [f'P(max < {fr(x)})' for x in xs], rows,
          note='Read: if we finish at +X, P(max < X) is roughly our chance of winning with that score.')

    # ---------------------------------------------------------------- headline
    print('\nSimulating strategies ...')
    sims, sims_e = {}, {}
    for s in STRATEGY_ORDER:
        sims[s] = simulate(s, P)
        sims[s]['P'] = P
        sims_e[s] = simulate(s, PE)
        sims_e[s]['P'] = PE
    short = {s: strategy_spec(s, P)['short'] for s in STRATEGY_ORDER}

    rep.h('T5. Strategy return distributions (benchmark-relative, briefed world)')
    rows = []
    results['stats'] = {}
    for s in STRATEGY_ORDER:
        for pol in ('a', 'b'):
            if pol == 'b' and s in ('S2', 'S2i'):
                continue
            st = stats_row(sims[s]['rel_' + pol])
            results['stats'][f'{s}{pol}'] = st
            rows.append([short[s], pol, fr(st['mean']), fr(st['median']), fr(st['p90']), fr(st['p99']),
                         fp(st['P>50']), fp(st['P>100']), fp(st['P>200'])])
    rep.t(['Strategy', 'cap', 'mean', 'median', 'p90', 'p99', 'P(>+50%)', 'P(>+100%)', 'P(>+200%)'], rows,
          note='cap a = no rebalancing (winners grow past 20%); b = trim to 20% after every event. '
               'S2/S2i are one-period baskets, so a = b.')

    rep.h('T5e. Strategy return distributions, EV-neutral world (policy a)')
    rows = []
    for s in STRATEGY_ORDER:
        st = stats_row(sims_e[s]['rel_a'])
        results['stats'][f'{s}a_evn'] = st
        rows.append([short[s], fr(st['mean']), fr(st['median']), fr(st['p90']), fr(st['p99']),
                     fp(st['P>50']), fp(st['P>100']), fp(st['P>200'])])
    rep.t(['Strategy', 'mean', 'median', 'p90', 'p99', 'P(>+50%)', 'P(>+100%)', 'P(>+200%)'], rows)

    def pw(sim, F, N, pol='a', **kw):
        return F.p_win(sim['rel_' + pol], N, sim=sim, **kw)

    rep.h('T6. HEADLINE: P(win) by strategy, field model and N (briefed world, cap policy a)')
    pwin = {}
    rows = []
    for s in STRATEGY_ORDER:
        row = [short[s]]
        for key in FKEYS:
            for N in sizes:
                v = pw(sims[s], fields[key], N)
                pwin[(s, key, N, 'a', 'brief')] = v
                row.append(fp(v))
        rows.append(row)
    rep.t(['Strategy'] + [f'{fields[k].label} N={N:,}' for k in FKEYS for N in sizes], rows,
          note=f'Fair share (every team identical) = 1/(N+1): {fp(1 / 1001)} / {fp(1 / 3001)} / {fp(1 / 5001)}.')

    rep.h('T7. Cap handling: P(win) at N=3,000, (a) no rebalancing vs (b) trim to 20% after each event')
    rows = []
    for s in STRATEGY_ORDER:
        row = [short[s]]
        for world, sm, fl in (('brief', sims, fields), ('evn', sims_e, fields_evn)):
            for key in FKEYS:
                for pol in ('a', 'b'):
                    v = pw(sm[s], fl[key], N0, pol)
                    pwin[(s, key, N0, pol, world)] = v
                    row.append(fp(v))
        rows.append(row)
    hdr = ['Strategy']
    for wlab in ('briefed', 'EV-neutral'):
        for key in FKEYS:
            hdr += [f'{wlab} {fields[key].label} (a)', f'{wlab} {fields[key].label} (b)']
    rep.t(hdr, rows)

    rep.h('T8. EV-neutral world: P(win) by N (cap policy a)')
    rows = []
    for s in STRATEGY_ORDER:
        row = [short[s]]
        for key in FKEYS:
            for N in sizes:
                v = pw(sims_e[s], fields_evn[key], N)
                pwin[(s, key, N, 'a', 'evn')] = v
                row.append(fp(v))
        rows.append(row)
    rep.t(['Strategy'] + [f'{fields[k].label} N={N:,}' for k in FKEYS for N in sizes], rows)

    # ---------------------------------------------------------------- scaled calibration
    rep.h("T9. P(win) if the winning score is typically T (field max rescaled so its median = T), N=3,000 shape")
    rows = []
    base_med = fields['recal'].max_quantiles(N0, [0.5])[0]
    for s in STRATEGY_ORDER:
        row = [short[s]]
        for T in P['scaled_targets']:
            row.append(fp(fields['recal'].p_win(sims[s]['rel_a'], N0, scale=base_med / T)))
        for T in P['scaled_targets']:
            row.append(fp(fields['recal'].p_win(sims_e[s]['rel_a'], N0, scale=base_med / T)))
        rows.append(row)
    rep.t(['Strategy'] + [f'brief T={fr(T)}' for T in P['scaled_targets']] +
          [f'EVN T={fr(T)}' for T in P['scaled_targets']], rows,
          note='Uses the F-recal field-max shape, stretched so its median equals T. '
               '+40/+60/+100% are the brief\'s alternatives; +168% and +310% are the 2024 and 2025 winners.')

    # ---------------------------------------------------------------- k scaling
    rep.h('T10. Sequential re-rolling: P(win) vs events per slot k (N=3,000)')
    rows = []
    kscan = {}
    for s in ['S3', 'S7', 'S5', 'S6']:
        for k in [1, 2, 3, 4]:
            Pk = with_overrides(P, {'k_seq': k})
            PEk = ev_neutral(Pk)
            a = simulate(s, Pk); a['P'] = Pk
            e = simulate(s, PEk); e['P'] = PEk
            vals = [pw(a, fields['recal'], N0, 'a'), pw(a, fields['recal'], N0, 'b'),
                    pw(a, fields['briefed'], N0, 'a'), pw(e, fields_evn['recal'], N0, 'a'),
                    pw(e, fields_evn['recal'], N0, 'b'), pw(e, fields_evn['briefed'], N0, 'a')]
            kscan[(s, k)] = vals
            rows.append([s, k, fr(a['rel_a'].mean())] + [fp(v) for v in vals])
    rep.t(['Strategy', 'k', 'mean (brief, a)', 'brief F-recal (a)', 'brief F-recal (b)', 'brief F-briefed (a)',
           'EVN F-recal (a)', 'EVN F-recal (b)', 'EVN F-briefed (a)'], rows)

    # ---------------------------------------------------------------- sensitivities
    rep.h('T11. Sensitivities: P(win) at N=3,000, cap policy (a)')
    SENS = [
        ('P(approve)', 'pdufa.p_approve', [0.70, 0.75, 0.80, 0.85, 0.90], ['S1', 'S3', 'S5', 'S6'], False),
        ('Approval pop scale (1 = briefed; 0.27 = EV 0)', 'pdufa.approve_scale', [0.27, 0.5, 0.75, 1.0, 1.25, 1.5],
         ['S1', 'S3', 'S5', 'S6'], False),
        ('Approval model', 'pdufa.approval_model', ['two_regime', 'normal'], ['S1', 'S3', 'S5'], False),
        ('Theme rho', 'theme.rho', [0.3, 0.5, 0.7, 0.9], ['S2', 'S5', 'S6'], True),
        ('Binary correlation rho', 'rho_binary', [0.0, 0.3, 0.6], ['S1', 'S3', 'S5', 'S7'], True),
        ('Melt-up size', 'theme.melt_add', [0.3, 0.6, 1.0, 1.5, 2.0], ['S2', 'S5', 'S6'], True),
        ('Melt-up probability', 'theme.p_melt', [0.05, 0.10, 0.15, 0.25], ['S2', 'S5', 'S6'], True),
        ('Rotation weekly E|move|', 'rotation.mean_abs_move', [0.10, 0.15, 0.20, 0.25, 0.30], ['S8'], True),
        ('Earnings E|move|', 'earnings.mean_abs_move', [0.15, 0.20, 0.25, 0.30], ['S4'], True),
    ]
    sens = {}
    for title, key, values, strats, do_evn in SENS:
        rows = []
        for s in strats:
            for v in values:
                Pv = with_overrides(P, {key: v})
                a = simulate(s, Pv); a['P'] = Pv
                vals = [pw(a, fields['recal'], N0), pw(a, fields['briefed'], N0)]
                if do_evn:
                    PEv = ev_neutral(Pv)
                    e = simulate(s, PEv); e['P'] = PEv
                    vals.append(pw(e, fields_evn['recal'], N0))
                else:
                    vals.append(float('nan'))
                sens[(key, s, v)] = vals
                rows.append([s, v, fr(a['rel_a'].mean())] + [fp(x) for x in vals])
        rep.p(f'\n**{title}** (`{key}`)\n')
        rep.t([ 'Strategy', 'value', 'mean (brief)', 'brief F-recal', 'brief F-briefed', 'EVN F-recal'], rows)

    rep.h('T12. Theme crowding: M extra teams hold a 5-name basket in OUR theme (N=3,000, policy a)')
    rows = []
    crowd_M = [0, 10, 30, 100]
    for s in ['S2', 'S5', 'S6']:
        row = [short[s]]
        for fk in FKEYS:
            for M in crowd_M:
                row.append(fp(fields[fk].p_win(sims[s]['rel_a'], N0, n_crowd=M, sim=sims[s])))
        rows.append(row)
    rep.t(['Strategy'] + [f'{fields[fk].label} M={M}' for fk in FKEYS for M in crowd_M], rows,
          note='Crowd teams share our theme regime, theme factor and index draw; only their '
               'idiosyncratic name noise differs. M=30 equals the number of lottery teams in F-recal.')

    # ---------------------------------------------------------------- key question
    rep.h('T13. Key question: independent tickets vs one correlated theme vs sequential re-rolling (N=3,000)')
    rows = []
    kq = [('S1', 'S1 5 independent PDUFA tickets', {}),
          ('S1', 'S1 same, biotech rho=0.3', {'rho_binary': 0.3}),
          ('S2i', 'S2i 5 momentum names, unrelated themes', {}),
          ('S2', 'S2 5 names, one theme (rho=0.7)', {}),
          ('S3', 'S3 sequential PDUFA k=2', {'k_seq': 2}),
          ('S3', 'S3 sequential PDUFA k=3', {}),
          ('S3', 'S3 sequential k=3, rho=0.3', {'rho_binary': 0.3}),
          ('S7', 'S7 sequential Phase 3 k=3', {}),
          ('S4', 'S4 earnings roulette x4', {}),
          ('S8', 'S8 weekly rotation x5', {}),
          ('S5', 'S5 2 theme + 3 seq PDUFA', {}),
          ('S6', 'S6 3 theme + 2 seq PDUFA', {})]
    keyq = {}
    for s, lab, ov in kq:
        Pv = with_overrides(P, ov)
        PEv = ev_neutral(Pv)
        a = simulate(s, Pv); a['P'] = Pv
        e = simulate(s, PEv); e['P'] = PEv
        vals = [pw(a, fields['recal'], N0, 'a'), pw(a, fields['recal'], N0, 'b'),
                pw(a, fields['briefed'], N0, 'a'), pw(e, fields_evn['recal'], N0, 'a'),
                pw(e, fields_evn['recal'], N0, 'b'), pw(e, fields_evn['briefed'], N0, 'a')]
        keyq[lab] = vals
        rows.append([lab, fr(a['rel_a'].mean()), fr(np.percentile(a['rel_a'], 99))] + [fp(v) for v in vals])
    rep.t(['Book', 'mean', 'p99', 'brief F-recal (a)', 'brief F-recal (b)', 'brief F-briefed (a)',
           'EVN F-recal (a)', 'EVN F-recal (b)', 'EVN F-briefed (a)'], rows)

    # ---------------------------------------------------------------- save
    results['pwin'] = {f'{k[0]}|{k[1]}|{k[2]}|{k[3]}|{k[4]}': v for k, v in pwin.items()}
    results['keyq'] = keyq
    results['kscan'] = {f'{k[0]}|{k[1]}': v for k, v in kscan.items()}
    results['runtime_s'] = time.time() - t0
    rep.save(os.path.join(HERE, 'tournament_mc_output.md'))
    with open(os.path.join(HERE, 'tournament_mc_results.json'), 'w') as f:
        json.dump(results, f, indent=1, default=str)

    if not args.no_charts:
        make_charts(P, sims, sims_e, fields, fields_evn, pwin, sens, kscan, short)
    print(f'\nDone in {time.time() - t0:.0f}s')


# =============================================================================
# 9. CHARTS
# =============================================================================
# Reference palette (dataviz skill), light mode; first 5 categorical slots validated.
C = {'surface': '#fcfcfb', 'ink': '#0b0b0b', 'ink2': '#52514e', 'muted': '#8a8984', 'grid': '#e6e5e1',
     's1': '#2a78d6', 's2': '#eb6834', 's3': '#1baf7a', 's4': '#eda100', 's5': '#e87ba4', 's6': '#008300'}


def _style(plt):
    plt.rcParams.update({
        'figure.facecolor': C['surface'], 'axes.facecolor': C['surface'], 'savefig.facecolor': C['surface'],
        'axes.edgecolor': C['grid'], 'axes.labelcolor': C['ink2'], 'axes.titlecolor': C['ink'],
        'xtick.color': C['ink2'], 'ytick.color': C['ink2'], 'text.color': C['ink'],
        'axes.grid': True, 'grid.color': C['grid'], 'grid.linewidth': 0.8, 'grid.linestyle': '-',
        'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 9,
        'axes.titlesize': 10, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left',
        'legend.frameon': False, 'lines.linewidth': 2, 'lines.solid_capstyle': 'round',
    })


def make_charts(P, sims, sims_e, fields, fields_evn, pwin, sens, kscan, short):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    _style(plt)
    N0 = P['base_N']
    pct = FuncFormatter(lambda v, _: f'{100 * v:+.0f}%' if v else '0%')

    # ---- chart 1: return distributions, small multiples ----
    order = STRATEGY_ORDER
    fig, axes = plt.subplots(2, 5, figsize=(16, 6.8), sharex=True, sharey=True)
    bins = np.arange(-1.0, 5.0001, 0.05)
    med_r = fields['recal'].max_quantiles(N0, [0.5])[0]
    med_b = fields['briefed'].max_quantiles(N0, [0.5])[0]
    for ax, s in zip(axes.flat, order):
        for pol, col, fill in (('a', C['s1'], True), ('b', C['s2'], False)):
            if pol == 'b' and s in ('S2', 'S2i'):
                continue
            x = np.clip(sims[s]['rel_' + pol], bins[0], bins[-1] - 1e-9)
            h, _ = np.histogram(x, bins=bins)
            h = h / x.size
            hh = np.where(h > 0, h, np.nan)
            ax.stairs(hh, bins, color=col, linewidth=1.6, baseline=None)
            if fill:
                ax.stairs(np.where(h > 0, h, 1e-9), bins, color=col, alpha=0.10, fill=True)
        ax.axvline(med_b, color=C['muted'], linewidth=1)
        ax.axvline(med_r, color=C['ink2'], linewidth=1)
        ax.set_yscale('log')
        ax.set_ylim(2e-6, 0.5)
        ax.set_xlim(-1, 5)
        ax.set_title(short[s], fontsize=9.5)
        ax.xaxis.set_major_formatter(pct)
        ax.set_xticks([-1, 0, 2, 4])
    for ax in axes[:, 0]:
        ax.set_ylabel('share of paths per 5% bin (log)')
    fig.supxlabel('benchmark-relative return over the window (paths beyond +500% are counted in the last bin)',
                  fontsize=9, color=C['ink2'])
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=C['s1'], lw=2, label='(a) no rebalancing: winners run past 20%'),
               Line2D([], [], color=C['s2'], lw=2, label='(b) trim to 20% after every event'),
               Line2D([], [], color=C['ink2'], lw=1, label=f'median winning return, F-recal N={N0:,}: {fr(med_r)}'),
               Line2D([], [], color=C['muted'], lw=1, label=f'median winning return, F-briefed N={N0:,}: {fr(med_b)}')]
    fig.legend(handles=handles, loc='upper left', ncol=4, bbox_to_anchor=(0.01, 0.955), fontsize=8.5)
    fig.suptitle(f"One-month benchmark-relative return by strategy (briefed assumptions, {P['n_paths']:,} paths each)",
                 x=0.01, ha='left', fontsize=12, fontweight='bold')
    fig.tight_layout(rect=(0, 0, 1, 0.91), w_pad=1.5)
    fig.savefig(os.path.join(HERE, 'fig_return_distributions.png'), dpi=150)
    plt.close(fig)

    # ---- chart 2: P(win) dot plot by strategy x N, three panels ----
    panels = [('Briefed world, F-recal field (base)', 'recal', 'brief'),
              ('Briefed world, F-briefed field', 'briefed', 'brief'),
              ('EV-neutral world, F-recal field', 'recal', 'evn')]
    base_vals = {s: pwin[(s, 'recal', N0, 'a', 'brief')] for s in order}
    rows = sorted(order, key=lambda s: base_vals[s])
    fig, axes = plt.subplots(1, 3, figsize=(16, 6.2), sharey=True)
    ncol = {1000: C['s1'], 3000: C['s2'], 5000: C['s3']}
    lo = 1e-5
    for ax, (title, fk, world) in zip(axes, panels):
        for i, s in enumerate(rows):
            vs = [max(pwin[(s, fk, N, 'a', world)], lo) for N in P['field_sizes']]
            ax.plot([min(vs), max(vs)], [i, i], color=C['grid'], lw=2, zorder=1)
            for N, v in zip(P['field_sizes'], vs):
                ax.plot(v, i, 'o', ms=7.5, color=ncol[N], mec=C['surface'], mew=1.5, zorder=3)
            v3 = pwin[(s, fk, N0, 'a', world)]
            ax.text(max(vs) * 1.5, i, fp(v3), va='center', fontsize=8, color=C['ink2'])
        ax.axvline(1.0 / (N0 + 1), color=C['muted'], lw=1)
        ax.text(1.0 / (N0 + 1) * 1.15, -0.85, 'fair share at N=3,000 (1/3,001)', fontsize=7.5, color=C['ink2'])
        ax.set_ylim(-1.1, len(rows) - 0.5)
        ax.set_xscale('log')
        ax.set_xlim(lo * 0.7, 3.0)
        ax.set_title(title)
        ax.set_xlabel('P(win) = P(our return is the field max), log scale')
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{100 * v:g}%'))
        ax.grid(axis='y', visible=False)
    axes[0].set_yticks(range(len(rows)))
    axes[0].set_yticklabels([short[s] for s in rows])
    handles = [Line2D([], [], marker='o', ls='', ms=7.5, color=ncol[N], label=f'N = {N:,} teams')
               for N in P['field_sizes']]
    fig.legend(handles=handles, loc='upper left', ncol=3, bbox_to_anchor=(0.01, 0.94), fontsize=9)
    fig.suptitle('P(win) by strategy and field size (labels = N=3,000; cap policy (a); < 0.001% plotted at 0.001%)',
                 x=0.01, ha='left', fontsize=12, fontweight='bold')
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(os.path.join(HERE, 'fig_pwin_by_strategy.png'), dpi=150)
    plt.close(fig)

    # ---- chart 3: sensitivities (F-recal, N=3000); solid = briefed world, dashed = EV-neutral ----
    from matplotlib.ticker import LogLocator, NullFormatter
    scol = {'S3': C['s1'], 'S5': C['s2'], 'S6': C['s3'], 'S2': C['s4'], 'S1': C['s5'], 'S7': C['s6']}
    panels = [('P(approve), briefed world only', 'pdufa.p_approve', ['S3', 'S5', 'S6', 'S1'], False),
              ('Approval pop scale (0.27 = EV 0), briefed only', 'pdufa.approve_scale', ['S3', 'S5', 'S6', 'S1'], False),
              ('Events per slot k', 'k', ['S3', 'S7', 'S5', 'S6'], True),
              ('Correlation among our binaries', 'rho_binary', ['S3', 'S7', 'S5', 'S1'], True),
              ('Theme correlation rho', 'theme.rho', ['S5', 'S6', 'S2'], True),
              ('Theme melt-up size', 'theme.melt_add', ['S5', 'S6', 'S2'], True)]
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.4))
    for ax, (title, key, strats, has_evn) in zip(axes.flat, panels):
        ends = []   # (x, y, label) of solid-line end labels, de-collided below
        for s in strats:
            if key == 'k':
                xs = [1, 2, 3, 4]
                yb = [kscan[(s, k)][0] for k in xs]
                ye = [kscan[(s, k)][3] for k in xs]
            else:
                xs = sorted({v for (kk, ss, v) in sens if kk == key and ss == s})
                yb = [sens[(key, s, v)][0] for v in xs]
                ye = [sens[(key, s, v)][2] for v in xs]
            yb = [max(y, 1e-5) for y in yb]
            ax.plot(xs, yb, color=scol[s], lw=2, marker='o', ms=6, mec=C['surface'], mew=1.2)
            ends.append([xs[-1], math.log10(yb[-1]), s])
            if has_evn:
                ye = [max(y, 1e-5) for y in ye]
                ax.plot(xs, ye, color=scol[s], lw=1.5, ls=(0, (4, 2)), marker='o', ms=4.5,
                        mec=C['surface'], mew=1.0)
        ends.sort(key=lambda e: e[1])
        for i in range(1, len(ends)):              # keep end labels >= 0.09 decades apart
            ends[i][1] = max(ends[i][1], ends[i - 1][1] + 0.09)
        for x_end, ly, s in ends:
            ax.text(x_end, 10 ** ly, f'  {s}', va='center', fontsize=8.5, color=C['ink2'])
        ax.set_yscale('log')
        ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 3.0)))
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{100 * v:g}%'))
        ax.set_title(title)
        ax.margins(x=0.12)
    for ax in axes[:, 0]:
        ax.set_ylabel(f'P(win), N={N0:,}, F-recal field')
    handles = [Line2D([], [], color=scol[s], lw=2, label=short[s]) for s in ['S3', 'S7', 'S5', 'S6', 'S2', 'S1']]
    handles += [Line2D([], [], color=C['ink2'], lw=2, label='briefed world'),
                Line2D([], [], color=C['ink2'], lw=1.5, ls=(0, (4, 2)), label='EV-neutral world')]
    fig.legend(handles=handles, loc='upper left', ncol=8, bbox_to_anchor=(0.01, 0.95), fontsize=8.5)
    fig.suptitle('Sensitivity of P(win) (recalibrated field, N=3,000, cap policy (a))',
                 x=0.01, ha='left', fontsize=12, fontweight='bold')
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    fig.savefig(os.path.join(HERE, 'fig_sensitivity.png'), dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
