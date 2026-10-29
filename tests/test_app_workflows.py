import json
from pathlib import Path

import numpy as np
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


def start_app():
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    return app


def test_theme_dashboard_and_tables_follow_units_without_changing_model():
    app = start_app()
    assert app.selectbox(key='theme_name').value == 'McKinsey-inspired'
    canonical = app.session_state.profile.copy(deep=True)
    baseline = float(app.metric[1].value.split()[0].replace(',', ''))
    app.selectbox(key='sel_money_unit').select('BNOK')
    app.selectbox(key='sel_oil_unit').select('kbbl')
    app.selectbox(key='sel_gas_unit').select('BCM').run()
    assert not app.exception
    assert app.metric[1].value.endswith(' BNOK')
    assert abs(float(app.metric[1].value.split()[0]) - baseline*.001) < .01
    chart = json.loads(app.get('plotly_chart')[0].proto.spec)
    assert all('BNOK' in trace['name'] and 'mnok' not in trace['name'] for trace in chart['data'])
    assert chart['layout']['template']['layout']['font']['color'] == '#051c2c'
    app.selectbox(key='active_page').select('Production & Economics').run()
    assert not app.exception
    tables = [element.value for element in app.dataframe]
    econ = next(table for table in tables if 'after_tax_cf (BNOK)' in table.columns)
    assert 'oil (kbbl)' in econ and 'gas (BCM)' in econ
    editor = next(table for table in tables if 'oil_kbbl' in table.columns)
    np.testing.assert_allclose(editor.oil_kbbl, canonical.oil_mmbbl*1000)
    assert app.session_state.profile.equals(canonical)
    for theme in ['North Sea', 'Midnight Offshore', 'Arctic Light']:
        app.selectbox(key='theme_name').select(theme).run()
        assert not app.exception


def test_sensitivity_only_evaluates_selected_view_and_uses_units():
    app = start_app()
    app.selectbox(key='sel_money_unit').select('BNOK')
    app.selectbox(key='active_page').select('Sensitivity & Breakeven').run()
    assert not app.exception
    assert len(app.get('plotly_chart')) == 3
    assert not app.dataframe
    spider = json.loads(app.get('plotly_chart')[2].proto.spec)
    assert spider['layout']['yaxis']['title']['text'] == 'NPV (BNOK)'
    app.radio(key='analysis_view').set_value('Breakeven Analysis').run()
    assert not app.exception
    assert len(app.dataframe) == 2
    app.radio(key='analysis_view').set_value('Market Decks').run()
    assert not app.exception
    assert len(app.get('plotly_chart')) == 3


def test_monte_carlo_run_unit_switch_stale_inputs_and_export():
    app = start_app()
    app.selectbox(key='active_page').select('Scenarios & Uncertainty').run()
    assert not app.exception
    app.button(key='run_mc').click().run()
    assert not app.exception
    samples = app.session_state.mc_samples.copy()
    assert len(samples) == 2000
    assert any(metric.label == 'P50 (Median)' for metric in app.metric)
    app.selectbox(key='sel_money_unit').select('BNOK').run()
    assert not app.exception
    np.testing.assert_array_equal(app.session_state.mc_samples, samples)
    assert next(metric for metric in app.metric if metric.label == 'P50 (Median)').value.endswith(' BNOK')
    assert not app.warning
    app.number_input(key='assump_disc_pct').set_value(10).run()
    assert any('Run Monte Carlo again' in warning.value for warning in app.warning)
    assert not any(metric.label == 'P50 (Median)' for metric in app.metric)
    app.selectbox(key='active_page').select('Project & Export').run()
    assert not app.exception
    assert any('excluded' in warning.value for warning in app.warning)
