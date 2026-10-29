import json
from pathlib import Path

import numpy as np
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


def start_app(run=True):
    app = AppTest.from_file(APP, default_timeout=120).run()
    if run:
        app.button(key='run_all').click().run()
    assert not app.exception
    return app


def edit_table(app, key, edited_rows):
    # data_editor has no public AppTest editing API; emulate its browser delta.
    states = app._tree.get_widget_states()
    editor = next(element for element in app.dataframe if element.key == key)
    states.widgets.add(id=editor.proto.id, string_value=json.dumps(
        {'edited_rows': edited_rows, 'added_rows': [], 'deleted_rows': []}))
    app._run(states)
    assert not app.exception


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
    app.button(key='module_Input Data').click().run()
    editor = next(element.value for element in app.dataframe if 'oil_kbbl' in element.value.columns)
    np.testing.assert_allclose(editor.oil_kbbl, canonical.oil_mmbbl*1000)
    assert app.session_state.profile.equals(canonical)
    for theme in ['North Sea', 'Midnight Offshore', 'Arctic Light']:
        app.selectbox(key='theme_name').select(theme).run()
        assert not app.exception


def test_sensitivity_displays_selected_view_and_uses_units():
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
    app.button(key='module_Input Data').click().run()
    assert any('input_editor_market_deck' in element.key for element in app.dataframe if element.key)


def test_monte_carlo_run_unit_switch_stale_inputs_and_export():
    app = start_app()
    app.button(key='module_Scenarios & Uncertainty').click().run()
    assert not app.exception
    assert not any(button.key == 'run_mc' for button in app.button)
    samples = app.session_state.analysis_results['samples'].copy()
    assert len(samples) == 2000
    assert any(metric.label == 'P50 (Median)' for metric in app.metric)
    app.selectbox(key='sel_money_unit').select('BNOK').run()
    assert not app.exception
    np.testing.assert_array_equal(app.session_state.analysis_results['samples'], samples)
    median = next(metric for metric in app.metric if metric.label == 'P50 (Median)')
    assert median.value.endswith(' billion NOK')
    assert 'BNOK' in median.proto.help
    assert not app.warning
    app.button(key='module_Input Data').click().run()
    app.number_input(key='assump_disc_pct').set_value(10).run()
    app.button(key='module_Scenarios & Uncertainty').click().run()
    assert any('Results are hidden' in warning.value for warning in app.warning)
    assert not any(metric.label == 'P50 (Median)' for metric in app.metric)
    app.button(key='module_Project & Export').click().run()
    assert not app.exception
    assert any('Results are hidden' in warning.value for warning in app.warning)
    assert not app.get('download_button')


def test_module_buttons_are_visible_and_preserve_project_state():
    app = start_app()
    modules = ['Input Data', 'Dashboard', 'Production & Economics', 'Sensitivity & Breakeven',
               'Scenarios & Uncertainty', 'Project & Export']
    assert not any(widget.label == 'Module' for widget in app.selectbox)
    for module in modules:
        assert app.button(key=f'module_{module}').label == module
    app.button(key='module_Input Data').click().run()
    app.number_input(key='assump_disc_pct').set_value(10).run()
    app.button(key='run_all').click().run()
    profile = app.session_state.profile.copy(deep=True)
    for module in modules[1:] + modules[:1]:
        app.button(key=f'module_{module}').click().run()
        assert not app.exception
        assert app.session_state.active_page == module
        assert app.session_state.assump_disc_pct == 10
        assert app.session_state.profile.equals(profile)
        assert app.button(key=f'module_{module}').proto.type == 'primary'


def test_input_first_explicit_run_and_atomic_invalidation(monkeypatch):
    from economics import workflow
    import streamlit as st

    st.cache_data.clear()
    calls = []
    original = workflow.run_all

    def tracked_run(inputs):
        calls.append(inputs['seed'])
        return original(inputs)

    monkeypatch.setattr(workflow, 'run_all', tracked_run)
    app = start_app(run=False)
    assert app.session_state.active_page == 'Input Data'
    assert 'analysis_results' not in app.session_state
    assert not calls
    app.button(key='module_Dashboard').click().run()
    assert any('Results are hidden' in warning.value for warning in app.warning)
    assert not app.metric and not calls
    app.button(key='module_Input Data').click().run()
    app.button(key='run_all').click().run()
    assert calls == [42]
    first = app.session_state.analysis_results
    app.button(key='module_Project & Export').click().run()
    assert app.get('download_button')
    app.selectbox(key='sel_money_unit').select('BNOK').run()
    assert calls == [42]
    app.button(key='module_Input Data').click().run()
    app.number_input(key='input_seed').set_value(43).run()
    assert 'analysis_results' not in app.session_state
    assert calls == [42]
    app.button(key='run_all').click().run()
    assert calls == [42, 43]
    second = app.session_state.analysis_results
    assert second['key'] != first['key']
    assert not np.array_equal(second['samples'], first['samples'])
    app.button(key='module_Input Data').click().run()
    key = app.session_state.input_widget_scenario
    edit_table(app, key, {0: {'oil_factor': -1.}})
    app.button(key='run_all').click().run()
    assert not app.exception
    assert any('Analysis failed; results remain hidden' in error.value for error in app.error)
    assert 'analysis_results' not in app.session_state
    app.button(key='module_Project & Export').click().run()
    assert not app.get('download_button')


def test_editor_deltas_survive_repeated_edits_navigation_and_unit_changes():
    app = start_app(run=False)
    key = app.session_state.input_widget_profile
    edit_table(app, key, {2: {'oil_MMbbl': 3.}})
    edit_table(app, key, {2: {'oil_MMbbl': 3., 'gas_MSm3': 60.}})
    assert app.session_state.profile.loc[2, 'gas_msm3'] == 60.
    app.button(key='module_Dashboard').click().run()
    app.button(key='module_Input Data').click().run()
    assert app.session_state.profile.loc[2, 'oil_mmbbl'] == 3.
    app.selectbox(key='sel_oil_unit').select('kbbl').run()
    key = app.session_state.input_widget_profile
    edit_table(app, key, {2: {'oil_kbbl': 4000.}})
    app.selectbox(key='sel_oil_unit').select('MMbbl').run()
    assert app.session_state.profile.loc[2, 'oil_mmbbl'] == 4.
    assert app.session_state.profile.loc[2, 'gas_msm3'] == 60.
    key = app.session_state.input_widget_profile
    edit_table(app, key, {2: {'oil_MMbbl': -1.}})
    assert app.error
    assert app.button(key='run_all').disabled
    app.button(key='module_Dashboard').click().run()
    assert not app.metric


def test_loading_project_restores_inputs_without_running_and_resets_omitted_settings():
    from dataclasses import asdict
    from economics.engine import Assumptions

    app = start_app(run=False)
    profile = app.session_state.profile.to_dict('records')
    app.session_state._pending_project_import = {
        'profile': profile, 'assumptions': asdict(Assumptions(oil_price_usd_bbl=95.)),
        'settings': {'seed': 123, 'iterations': 500, 'time_resolution': 'quarterly',
                     'use_deck': False, 'uncertainty': {'oil_price_pct': .3},
                     'cutoff': {'mode': 'hard', 'hard_cutoff_year': 2035}},
    }
    app.run()
    assert not app.exception
    assert app.number_input(key='assump_oil').value == 95.
    assert app.number_input(key='input_seed').value == 123
    assert app.number_input(key='input_sigma_oil').value == 30.
    assert app.selectbox(key='setting_resolution').value == 'quarterly'
    assert 'analysis_results' not in app.session_state
    app.session_state._pending_project_import = {'profile': profile, 'assumptions': {}, 'settings': {}}
    app.run()
    assert not app.exception
    assert app.number_input(key='assump_oil').value == 75.
    assert app.number_input(key='input_seed').value == 42
    assert app.number_input(key='input_sigma_oil').value == 20.
    assert app.selectbox(key='input_cutoff_mode').value == 'none'
    assert app.selectbox(key='setting_resolution').value == 'annual'


def test_dashboard_compact_bar_profiles_and_monthly_periods():
    app = start_app(run=False)
    app.selectbox(key='sel_oil_unit').select('kbbl')
    app.selectbox(key='sel_gas_unit').select('BCM')
    app.selectbox(key='setting_resolution').select('monthly').run()
    app.button(key='run_all').click().run()
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
    app.button(key='module_Input Data').click().run()
    assert not app.exception
    generated = json.loads(app.get('plotly_chart')[0].proto.spec)
    assert all(trace['type'] == 'bar' for trace in generated['data'])
    assert generated['layout']['yaxis']['title']['text'] == 'kbbl'
    assert generated['layout']['yaxis2']['title']['text'] == 'BCM'


def test_generator_cases_units_recovery_and_apply():
    app = start_app(run=False)
    for case in ['Dry gas', 'Gas with condensate', 'Independent oil and gas', 'Oil with associated gas']:
        app.selectbox(key='gen_input_field_type').select(case).run()
        assert not app.exception
        assert not app.error
    app.selectbox(key='gen_input_field_type').select('Dry gas').run()
    app.number_input(key='gen_input_gas_resources_msm3_1.0').set_value(3000.).run()
    app.selectbox(key='sel_oil_unit').select('MSm3 oil')
    app.selectbox(key='sel_gas_unit').select('BCM')
    app.selectbox(key='sel_money_unit').select('BNOK').run()
    assert not app.exception
    assert app.number_input(key='gen_input_gas_resources_msm3_0.001').value == 3.
    assert app.number_input(key='gen_input_gas_plateau_msm3_0.001').value == .25
    app.selectbox(key='gen_input_resource_basis').select('In-place volumes × recovery factor').run()
    app.number_input(key='gen_input_gas_recovery_factor_100.0').set_value(50.).run()
    app.number_input(key='gen_input_start_year_1.0').set_value(2030.).run()
    generator_before = dict(app.session_state.generator)
    app.button(key='module_Dashboard').click().run()
    app.button(key='module_Input Data').click().run()
    assert app.session_state.generator == generator_before
    app.button(key='apply_generated_profile').click().run()
    assert not app.exception
    p = app.session_state.profile
    assert p.year.min() == 2030
    assert p.oil_mmbbl.sum() == 0
    assert 0 < p.gas_msm3.sum() <= 1500.
    assert p.loc[p.year < 2032, 'gas_msm3'].sum() == 0
    assert p.capex_mnok.sum() == generator_before['capex_mnok']
    assert p.decom_mnok.sum() == generator_before['decom_mnok']
    app.button(key='run_all').click().run()
    app.button(key='module_Project & Export').click().run()
    assert not app.exception
    # Saved generator settings travel with the canonical project profile.
    from economics.project_io import dumps_project, loads_project
    from economics.engine import Assumptions
    payload = dumps_project(p, Assumptions(), [], {}, settings={'generator':generator_before})
    loaded = loads_project(payload)
    assert loaded['settings']['generator'] == generator_before
    app.session_state._pending_project_import = loaded
    app.button(key='module_Input Data').click().run()
    assert not app.exception
    assert app.session_state.generator == generator_before
    assert app.selectbox(key='gen_input_field_type').value == 'Dry gas'


def test_generator_invalid_inputs_do_not_replace_project_profile():
    app = start_app(run=False)
    original = app.session_state.profile.copy()
    app.number_input(key='gen_input_oil_plateau_mmbbl_1.0').set_value(0.).run()
    assert not app.exception
    assert any('positive recoverable resources and plateau' in error.value for error in app.error)
    assert not any(button.key == 'apply_generated_profile' for button in app.button)
    assert app.session_state.profile.equals(original)


def test_condensate_ratio_keeps_precision_in_small_display_units():
    app = start_app(run=False)
    app.selectbox(key='gen_input_field_type').select('Gas with condensate')
    app.selectbox(key='sel_gas_unit').select('Sm3').run()
    assert not app.exception
    ratio = next(widget for widget in app.number_input if widget.label.startswith('Condensate / sales gas ratio'))
    assert ratio.value == .002 / 1e6
    assert ratio.proto.format == '%.10g'
    assert ratio.proto.step <= ratio.value
    assert not app.error
