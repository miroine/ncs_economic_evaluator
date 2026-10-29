from dataclasses import replace

import numpy as np
import pytest

from economics.conventions import BOE_PER_SM3_GAS
from economics.production import FIELD_TYPES, FieldProfileSettings, field_profile
from economics.project_io import validate_profile_table


@pytest.mark.parametrize('case', FIELD_TYPES)
def test_cases_are_resource_bounded_and_canonical(case):
    s = FieldProfileSettings(field_type=case, oil_resources_mmbbl=30., gas_resources_msm3=500.,
                             oil_recovery_factor=.5, gas_recovery_factor=.6)
    p = field_profile(s)
    assert p.oil_mmbbl.sum() <= 15 + 1e-10
    assert p.gas_msm3.sum() <= 300 + 1e-10
    assert (p.iloc[:s.development_years][['oil_mmbbl', 'gas_msm3']].to_numpy() == 0).all()
    assert p.capex_mnok.sum() == pytest.approx(s.capex_mnok)
    assert p.decom_mnok.sum() == s.decom_mnok
    validate_profile_table(p)
    if case == 'Dry gas':
        assert p.oil_mmbbl.sum() == 0
    if case == 'Gas with condensate':
        np.testing.assert_allclose(p.oil_mmbbl, p.gas_msm3 * s.condensate_mmbbl_per_msm3)
    if case == 'Oil with associated gas':
        np.testing.assert_allclose(p.gas_msm3, p.oil_mmbbl * s.associated_gas_msm3_per_mmbbl)


def test_depletion_preserves_early_rates_and_partial_final_year():
    s = FieldProfileSettings(field_type='Independent oil and gas', development_years=0,
                             oil_resources_mmbbl=25, oil_plateau_mmbbl=10,
                             gas_resources_msm3=35, gas_plateau_msm3=20,
                             oil_ramp_years=0, gas_ramp_years=0,
                             oil_plateau_years=10, gas_plateau_years=10, uptime=1.)
    p = field_profile(s)
    np.testing.assert_allclose(p.oil_mmbbl.iloc[:4], [10, 10, 5, 0])
    np.testing.assert_allclose(p.gas_msm3.iloc[:4], [20, 15, 0, 0])
    assert p.attrs['last_production_year'] == 2029
    assert p.loc[p.year == 2030, 'decom_mnok'].iloc[0] == s.decom_mnok


def test_linked_fluid_resource_limit_stops_both_streams():
    s = FieldProfileSettings(oil_resources_mmbbl=100, gas_resources_msm3=100,
                             associated_gas_msm3_per_mmbbl=20, uptime=1., oil_ramp_years=0)
    p = field_profile(s)
    assert p.oil_mmbbl.sum() == pytest.approx(5.)
    assert p.gas_msm3.sum() == pytest.approx(100.)
    s = replace(s, field_type='Gas with condensate', oil_resources_mmbbl=1.,
                gas_resources_msm3=1000., condensate_mmbbl_per_msm3=.01)
    p = field_profile(s)
    assert p.oil_mmbbl.sum() == pytest.approx(1.)
    assert p.gas_msm3.sum() == pytest.approx(100.)


def test_ramp_plateau_decline_and_uptime_applied_once():
    s = FieldProfileSettings(field_type='Dry gas', development_years=0, production_years=6,
                             gas_resources_msm3=10000., gas_plateau_msm3=100.,
                             gas_ramp_years=2, gas_plateau_years=2,
                             gas_decline_rate=.2, uptime=.5)
    p = field_profile(s)
    np.testing.assert_allclose(p.gas_msm3.iloc[:6], [25, 50, 50, 50, 40, 32])


def test_cost_timing_decom_extension_and_variable_opex():
    s = FieldProfileSettings(field_type='Dry gas', start_year=2030, development_years=3,
                             production_years=2, decom_lag_years=2, gas_plateau_msm3=100.,
                             gas_ramp_years=0, uptime=1., variable_opex_nok_boe=25.)
    p = field_profile(s)
    np.testing.assert_allclose(p.capex_mnok.iloc[:3], [4000, 4000, 4000])
    assert p.attrs['first_production_year'] == 2033
    assert p.year.max() == 2036
    assert p.decom_mnok.iloc[-1] == 2000.
    np.testing.assert_allclose(p.opex_mnok.iloc[3:5], 600. + 100. * BOE_PER_SM3_GAS * 25.)
    assert (p.loc[p.gas_msm3 == 0, 'opex_mnok'] == 0).all()


@pytest.mark.parametrize('changes', [
    {'uptime':0}, {'oil_decline_rate':1.1}, {'gas_recovery_factor':-.1},
    {'production_years':0}, {'development_years':1.5}, {'capex_mnok':-1},
    {'oil_resources_mmbbl':float('nan')}, {'field_type':'unknown'},
    {'gas_resources_msm3':0.}, {'oil_plateau_mmbbl':0.},
])
def test_invalid_settings_raise_actionable_errors(changes):
    with pytest.raises(ValueError):
        field_profile(replace(FieldProfileSettings(), **changes))
