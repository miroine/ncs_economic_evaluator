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
    baseline = app.metric[1].value
    full_nok = app.metric[1].proto.help.split('(')[-1]
    app.selectbox(key='sel_money_unit').select('BNOK')
    app.selectbox(key='sel_oil_unit').select('kbbl')
    app.selectbox(key='sel_gas_unit').select('BCM').run()
    assert not app.exception
    assert app.metric[1].value == baseline
    assert app.metric[1].value.endswith(' billion NOK')
    assert 'BNOK' in app.metric[1].proto.help
    assert app.metric[1].proto.help.endswith(full_nok)
    chart = json.loads(app.get('plotly_chart')[0].proto.spec)
    assert all('BNOK' in trace['name'] and 'mnok' not in trace['name'] for trace in chart['data'])
    assert chart['layout']['template']['layout']['font']['color'] == '#051c2c'
    app.button(key='module_Production & Economics').click().run()
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
    app.button(key='module_Sensitivity & Breakeven').click().run()
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
    app.button(key='module_Scenarios & Uncertainty').click().run()
    assert not app.exception
    app.button(key='run_mc').click().run()
    assert not app.exception
    samples = app.session_state.mc_samples.copy()
    assert len(samples) == 2000
    assert any(metric.label == 'P50 (Median)' for metric in app.metric)
    app.selectbox(key='sel_money_unit').select('BNOK').run()
    assert not app.exception
    np.testing.assert_array_equal(app.session_state.mc_samples, samples)
    median = next(metric for metric in app.metric if metric.label == 'P50 (Median)')
    assert median.value.endswith(' billion NOK')
    assert 'BNOK' in median.proto.help
    assert not app.warning
    app.number_input(key='assump_disc_pct').set_value(10).run()
    assert any('Run Monte Carlo again' in warning.value for warning in app.warning)
    assert not any(metric.label == 'P50 (Median)' for metric in app.metric)
    app.button(key='module_Project & Export').click().run()
    assert not app.exception
    assert any('excluded' in warning.value for warning in app.warning)


def test_module_buttons_are_visible_and_preserve_project_state():
    app = start_app()
    modules = ['Dashboard', 'Production & Economics', 'Sensitivity & Breakeven',
               'Scenarios & Uncertainty', 'Project & Export']
    assert not any(widget.label == 'Module' for widget in app.selectbox)
    for module in modules:
        assert app.button(key=f'module_{module}').label == module
    app.number_input(key='assump_disc_pct').set_value(10).run()
    profile = app.session_state.profile.copy(deep=True)
    for module in modules[1:] + modules[:1]:
        app.button(key=f'module_{module}').click().run()
        assert not app.exception
        assert app.session_state.active_page == module
        assert app.number_input(key='assump_disc_pct').value == 10
        assert app.session_state.profile.equals(profile)
        assert app.button(key=f'module_{module}').proto.type == 'primary'


def test_dashboard_compact_bar_profiles_and_monthly_periods():
    app = start_app()
    app.selectbox(key='sel_oil_unit').select('kbbl')
    app.selectbox(key='sel_gas_unit').select('BCM')
    app.selectbox(key='setting_resolution').select('monthly').run()
    assert not app.exception
    charts = [json.loads(chart.proto.spec) for chart in app.get('plotly_chart')]
    assert [chart['layout']['height'] for chart in charts] == [300, 300, 280]
    assert all(trace['type'] == 'bar' for trace in charts[0]['data'])
    assert all(trace['type'] == 'scatter' for trace in charts[1]['data'])
    production = charts[2]
    assert all(trace['type'] == 'bar' for trace in production['data'])
    assert production['layout']['yaxis']['title']['text'] == 'kbbl'
    assert production['layout']['yaxis2']['title']['text'] == 'BCM'
    for chart in charts:
        x = chart['data'][0]['x']
        assert len(x) == 180
        assert len(set(x)) == 180
        assert x[:2] == ['2027-01', '2027-02']
    app.button(key='module_Production & Economics').click().run()
    assert not app.exception
    generated = json.loads(app.get('plotly_chart')[0].proto.spec)
    assert all(trace['type'] == 'bar' for trace in generated['data'])
    assert generated['layout']['yaxis']['title']['text'] == 'kbbl'
    assert generated['layout']['yaxis2']['title']['text'] == 'BCM'
