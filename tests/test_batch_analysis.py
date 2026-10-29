from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from economics.analysis import sensitivity_curve, tornado
from economics.advanced_analysis import breakeven_factor, spider
from economics.batch import npv_cases
from economics.cutoff import CutoffSettings
from economics.engine import Assumptions, calculate_cashflow, npf
from economics.market import default_market_deck
from economics.monte_carlo import Uncertainty, run_monte_carlo, sample_factors
from economics.periods import expand_profile


def profile():
    return pd.DataFrame({
        'year': range(2027, 2035),
        'oil_mmbbl': [0, 0, 1, 2, 1.5, 1, .2, .05],
        'gas_msm3': [0, 0, 20, 40, 30, 20, 4, 1],
        'capex_mnok': [1000, 1500, 100, 0, 0, 0, 0, 0],
        'opex_mnok': [0, 0, 100, 100, 100, 100, 500, 500],
        'decom_mnok': [0, 0, 0, 0, 0, 0, 0, 600],
        'tariff_mnok': [0, 0, 10, 10, 10, 10, 10, 10],
    })


def scalar_value(p, a, row, deck, cutoff):
    p = p.copy()
    a = replace(a, oil_price_usd_bbl=a.oil_price_usd_bbl*row[0],
                gas_price_usd_sm3=a.gas_price_usd_sm3*row[1], usd_nok=a.usd_nok*row[5])
    p['capex_mnok'] *= row[2]
    p['opex_mnok'] *= row[3]
    p[['oil_mmbbl', 'gas_msm3']] *= row[4]
    if deck is not None:
        deck = deck.copy()
        deck['oil_usd_bbl'] *= row[0]
        deck['gas_usd_sm3'] *= row[1]
        deck['usd_nok'] *= row[5]
    return calculate_cashflow(p, a, deck, cutoff)['discounted_cf_mnok'].sum()


@pytest.mark.parametrize('resolution', ['annual', 'quarterly', 'monthly'])
@pytest.mark.parametrize('tax_mode', ['ncs_v2', 'ncs_post_2022', 'legacy'])
@pytest.mark.parametrize('mode', ['none', 'hard', 'negative_ocf', 'economic_limit'])
@pytest.mark.parametrize('use_deck', [False, True])
def test_batch_matches_full_cashflow(resolution, tax_mode, mode, use_deck):
    p = expand_profile(profile(), resolution, 'front')
    a = Assumptions(tax_mode=tax_mode, money_basis='nominal', discount_rate_basis='real')
    deck = default_market_deck([2027, 2034], oil=63, gas=.42, usd_nok=11) if use_deck else None
    cutoff = CutoffSettings(mode=mode, hard_cutoff_year=2034, consecutive_negative_periods=2)
    factors = np.array([[1, 1, 1, 1, 1, 1], [.2, .4, 1.5, 1.8, .3, .7], [1.4, 1.2, .9, .8, 1.3, 1.2]])
    expected = [scalar_value(p, a, row, deck, cutoff) for row in factors]
    np.testing.assert_allclose(npv_cases(p, a, factors, deck, cutoff), expected, rtol=1e-12, atol=1e-9)


@pytest.mark.parametrize('move_decom', [False, True])
def test_minimum_rate_cutoff_and_chunk_boundary(move_decom):
    p = profile().iloc[2:].reset_index(drop=True)
    a = Assumptions(tax_mode='ncs_v2')
    cutoff = CutoffSettings(mode='hard', minimum_oil_mmbbl=.25, minimum_gas_msm3=5,
                            move_decom=move_decom, decom_lag_periods=10)
    factors = np.ones((513, 6))
    factors[-1, 4] = .25
    result = npv_cases(p, a, factors, cutoff=cutoff)
    np.testing.assert_allclose(result[[0, -1]], [scalar_value(p, a, row, None, cutoff) for row in factors[[0, -1]]])


@pytest.mark.parametrize('distribution', ['normal', 'triangular', 'lognormal'])
def test_monte_carlo_preserves_sampling_and_active_model(distribution):
    p = profile()
    a = Assumptions(tax_mode='ncs_v2')
    u = Uncertainty(oil_distribution=distribution)
    deck = default_market_deck(p.year, oil=40)
    cutoff = CutoffSettings(mode='hard', hard_cutoff_year=2032)
    actual, factors = run_monte_carlo(p, a, u, 20, 7, True, deck, cutoff)
    pd.testing.assert_frame_equal(factors, sample_factors(u, 20, 7))
    expected = [scalar_value(p, a, np.r_[row, 1], deck, cutoff) for row in factors.to_numpy()]
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-9)


def test_zero_uncertainty_equals_deterministic_active_model():
    p = profile()
    a = Assumptions(tax_mode='ncs_v2')
    u = Uncertainty(0, 0, 0, 0, 0)
    deck = default_market_deck(p.year, oil=42)
    cutoff = CutoffSettings(mode='hard', hard_cutoff_year=2032)
    values = run_monte_carlo(p, a, u, 30, market_deck=deck, cutoff=cutoff)
    expected = calculate_cashflow(p, a, deck, cutoff)['discounted_cf_mnok'].sum()
    np.testing.assert_allclose(values, expected)


def test_sensitivity_outputs_match_full_cashflow():
    p = profile()
    a = Assumptions(tax_mode='ncs_v2')
    deck = default_market_deck(p.year)
    cutoff = CutoffSettings(mode='economic_limit')
    curve = sensitivity_curve(p, a, 'Oil price', [.8, 1, 1.2], deck, cutoff)
    expected = [scalar_value(p, a, [f, 1, 1, 1, 1, 1], deck, cutoff) for f in [.8, 1, 1.2]]
    np.testing.assert_allclose(curve.npv_mnok, expected)
    t, base = tornado(p, a, market_deck=deck, cutoff=cutoff)
    assert base == pytest.approx(expected[1])
    assert t.loc[t.variable == 'Oil price', 'low_npv'].iloc[0] == pytest.approx(expected[0])
    s = spider(p, a, deck, variables=['Oil price'], changes=[-20, 0, 20], cutoff=cutoff)
    np.testing.assert_allclose(s.npv_mnok, expected)


def test_invalid_factor_shape_is_explicit():
    with pytest.raises(ValueError, match='six columns'):
        npv_cases(profile(), Assumptions(), [[1, 2]])


def test_npv_only_analyses_never_solve_irr(monkeypatch):
    def unexpected_irr(*args):
        raise AssertionError('IRR must not run for NPV-only analysis')

    monkeypatch.setattr(npf, 'irr', unexpected_irr)
    p = profile()
    a = Assumptions()
    assert len(run_monte_carlo(p, a, iterations=10)) == 10
    assert len(spider(p, a)) == 54
    assert len(sensitivity_curve(p, a, 'Oil price')) == 17
    assert len(tornado(p, a)[0]) == 5
    breakeven_factor(p, a, 'Oil price')
