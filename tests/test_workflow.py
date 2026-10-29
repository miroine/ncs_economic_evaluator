from copy import deepcopy
from dataclasses import asdict

import numpy as np
import pandas as pd
import pytest

from economics import workflow
from economics.cutoff import CutoffSettings
from economics.engine import Assumptions, calculate_cashflow, metrics
from economics.market import default_market_deck
from economics.monte_carlo import Uncertainty, run_monte_carlo
from economics.periods import expand_profile
from economics.project_io import dumps_project, loads_project


@pytest.fixture
def inputs():
    years = list(range(2027, 2034))
    return {
        'profile': pd.DataFrame({
            'year': years, 'oil_mmbbl': [0, 0, 4, 6, 5, 3, 1],
            'gas_msm3': [0, 0, 60, 90, 75, 45, 15],
            'capex_mnok': [1000, 2000, 500, 0, 0, 0, 0],
            'opex_mnok': [0, 0, 300, 400, 350, 250, 150],
            'decom_mnok': [0, 0, 0, 0, 0, 0, 500],
        }),
        'assumptions': asdict(Assumptions(tax_mode='ncs_v2')),
        'market_deck': default_market_deck(years), 'use_deck': True,
        'cutoff': asdict(CutoffSettings()), 'resolution': 'annual', 'capex_phasing': 'even',
        'scenarios': pd.DataFrame([{'name': 'Base', 'oil_factor': 1.}]),
        'concepts': pd.DataFrame([{'name': 'Tie-back', 'capex_factor': .8}]),
        'uncertainty': asdict(Uncertainty()), 'iterations': 500, 'seed': 17,
        'tree': {'nodes': [{'id': 'base', 'type': 'outcome', 'scenario_key': 'Base'}], 'edges': []},
        'exploration': {'cos': .3, 'dry': 900., 'small': 1500., 'large': 12000.},
        'generator': None,
    }


@pytest.mark.parametrize('use_deck,resolution', [(True, 'annual'), (False, 'quarterly')])
def test_complete_snapshot_matches_canonical_engine(inputs, use_deck, resolution):
    inputs.update(use_deck=use_deck, resolution=resolution)
    original = deepcopy(inputs)
    result = workflow.run_all(inputs)
    profile = expand_profile(inputs['profile'], resolution)
    a = Assumptions(**inputs['assumptions'])
    deck = inputs['market_deck'] if use_deck else None
    cutoff = CutoffSettings(**inputs['cutoff'])
    expected = calculate_cashflow(profile, a, deck, cutoff)
    pd.testing.assert_frame_equal(result['cashflow'], expected)
    assert result['metrics'] == metrics(expected)
    assert result['key'] == workflow.input_key(inputs)
    assert set(result['curves']) == {'Oil price', 'Gas price', 'Production', 'CAPEX', 'OPEX'}
    assert not result['tornado'][0].empty
    for family in ('spider', 'breakevens', 'extended_breakevens',
                   'scenarios', 'concepts', 'discoveries'):
        assert not result[family].empty
    assert result['tree']['value'] == pytest.approx(result['scenario_values']['Base'])
    assert result['exploration']['risked_emv_mnok'] == pytest.approx(.3 * (.55 * 1500 + .45 * 12000) - .7 * 900)
    assert result['health']
    assert result['price_curve'].empty == use_deck
    samples, factors = run_monte_carlo(profile, a, Uncertainty(), 500, 17, True, deck, cutoff)
    np.testing.assert_array_equal(result['samples'], samples)
    pd.testing.assert_frame_equal(result['factors'], factors)
    pd.testing.assert_frame_equal(inputs['profile'], original['profile'])
    pd.testing.assert_frame_equal(inputs['market_deck'], original['market_deck'])


@pytest.mark.parametrize('field', [
    'profile', 'assumptions', 'market_deck', 'use_deck', 'cutoff', 'resolution',
    'capex_phasing', 'scenarios', 'concepts', 'uncertainty', 'iterations', 'seed',
    'tree', 'exploration', 'generator',
])
def test_every_model_input_invalidates_snapshot(inputs, field):
    baseline = workflow.input_key(inputs)
    value = inputs[field]
    if isinstance(value, pd.DataFrame):
        value.iloc[0, -1] = 2.
    elif isinstance(value, dict):
        value['changed'] = True
    else:
        inputs[field] = 'changed'
    assert workflow.input_key(inputs) != baseline


@pytest.mark.parametrize('group,field,value,message', [
    ('assumptions', 'discount_rate', np.nan, 'finite'),
    ('assumptions', 'usd_nok', 0., 'USD/NOK'),
    ('uncertainty', 'oil_distribution', 'unknown', 'choose'),
    ('uncertainty', 'gas_price_pct', -1., 'gas_price_pct'),
    ('uncertainty', 'production_pct', np.inf, 'finite'),
    ('uncertainty', 'price_correlation', 1.1, 'price_correlation'),
    ('cutoff', 'mode', 'unknown', 'cutoff rule'),
    ('cutoff', 'lookahead_periods', 1.5, 'whole number'),
    ('cutoff', 'minimum_oil_mmbbl', -1., 'minimum_oil'),
    ('exploration', 'cos', 1.1, 'chance'),
    ('exploration', 'large', np.nan, 'finite'),
    (None, 'iterations', 500.5, 'whole number'),
    (None, 'seed', np.inf, 'finite'),
    (None, 'capex_phasing', 'unknown', 'phasing'),
])
def test_invalid_inputs_fail_before_evaluating(inputs, monkeypatch, group, field, value, message):
    def unexpected_calculation(*args, **kwargs):
        pytest.fail('Invalid input reached the calculation engine')

    monkeypatch.setattr(workflow, 'calculate_cashflow', unexpected_calculation)
    (inputs if group is None else inputs[group])[field] = value
    with pytest.raises(ValueError, match=message):
        workflow.run_all(inputs)


@pytest.mark.parametrize('column,value', [('year', 2027.5), ('year', np.nan),
                                         ('oil_usd_bbl', np.inf), ('usd_nok', 0)])
def test_invalid_market_values_are_rejected(inputs, column, value):
    inputs['market_deck'] = inputs['market_deck'].astype(float)
    inputs['market_deck'].loc[0, column] = value
    with pytest.raises(ValueError, match='Market deck'):
        workflow.run_all(inputs)


def test_invalid_cases_and_tree_do_not_publish_a_bundle(inputs):
    inputs['scenarios'].loc[0, 'oil_factor'] = -1
    with pytest.raises(ValueError, match='negative'):
        workflow.run_all(inputs)
    inputs['scenarios'].loc[0, 'oil_factor'] = 1
    inputs['tree']['nodes'][0]['scenario_key'] = 'Missing scenario'
    with pytest.raises(ValueError, match='Decision tree'):
        workflow.run_all(inputs)


def test_project_roundtrip_preserves_all_run_settings(inputs):
    settings = {key: inputs[key] for key in ('cutoff', 'uncertainty', 'iterations', 'seed',
                                            'exploration', 'generator', 'use_deck', 'capex_phasing')}
    settings['time_resolution'] = inputs['resolution']
    loaded = loads_project(dumps_project(
        inputs['profile'], Assumptions(**inputs['assumptions']), inputs['scenarios'],
        inputs['tree'], market_deck=inputs['market_deck'], concepts=inputs['concepts'], settings=settings))
    assert loaded['settings'] == settings
    assert loaded['assumptions'] == inputs['assumptions']
    assert loaded['decision_tree'] == inputs['tree']
