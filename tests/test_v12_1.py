import numpy as np, pandas as pd
from economics.physical_v12 import ResourceCase, FacilityLimits, integrated_profile
from economics.periods import expand_profile
from economics.schedule_v12 import simulate_schedule
from economics.project_decision_v12 import terminal_project_values
from economics.engine import Assumptions


def annual_base():
    return pd.DataFrame({'year':[2028], 'oil_mmbbl':[0.0], 'gas_msm3':[0.0], 'capex_mnok':[0.0], 'opex_mnok':[0.0], 'decom_mnok':[0.0]})


def test_daily_rate_conserves_across_resolutions():
    base=annual_base()
    q=expand_profile(base,'quarterly')
    m=expand_profile(base,'monthly')
    case=ResourceCase(1000,1.0); wells=[{'onstream_year':2028,'oil_kbopd':10}]; fac=FacilityLimits(oil_kbopd=10,uptime=1)
    a=integrated_profile(base[['year']],case,wells,fac)
    qp=integrated_profile(q[['year','period','periods_per_year']],case,wells,fac)
    mp=integrated_profile(m[['year','period','periods_per_year']],case,wells,fac)
    assert np.isclose(a.oil_mmbbl.sum(),3.66)
    assert np.isclose(qp.oil_mmbbl.sum(),a.oil_mmbbl.sum())
    assert np.isclose(mp.oil_mmbbl.sum(),a.oil_mmbbl.sum())


def test_month_lengths_are_used():
    m=expand_profile(annual_base(),'monthly')
    p=integrated_profile(m[['year','period','periods_per_year']],ResourceCase(1000,1),[{'onstream_year':2028,'oil_kbopd':10}],FacilityLimits(oil_kbopd=10))
    assert p.period_days.tolist()[:2]==[31.0,29.0]
    assert np.isclose(p.oil_mmbbl.iloc[0],0.31)
    assert np.isclose(p.oil_mmbbl.iloc[1],0.29)


def test_schedule_duration_and_delay_are_calendar_months():
    acts=[{'name':'Build','start_month':0,'duration_months':12,'delay_low_months':3,'delay_mode_months':3,'delay_high_months':3.000001}]
    s=simulate_schedule(acts,5,1)
    assert np.allclose(s.total_delay_months,3,atol=1e-5)
    assert np.allclose(s.completion_month,15,atol=1e-5)


def _profile(freq):
    annual=pd.DataFrame({'year':[2028,2029,2030], 'oil_mmbbl':[1.,1.,0.], 'gas_msm3':[0.,0.,0.], 'capex_mnok':[0.,0.,0.], 'opex_mnok':[0.,0.,0.], 'decom_mnok':[0.,0.,0.]})
    return expand_profile(annual,freq)


def test_twelve_month_decision_delay_is_one_year_at_all_resolutions():
    a=Assumptions(tax_mode='legacy',ordinary_tax=0,special_tax=0,discount_rate=.1)
    for freq,rows in [('annual',1),('quarterly',4),('monthly',12)]:
        p=_profile(freq)
        base=terminal_project_values(p,a,{'x':{}})['x']
        delayed=terminal_project_values(p,a,{'x':{'delay_months':12}})['x']
        # Delay must reduce value and correspond to exactly one model-year of rows.
        assert delayed < base
        assert rows==int(p.periods_per_year.iloc[0])


def test_legacy_delay_years_maps_to_months():
    p=_profile('monthly'); a=Assumptions(tax_mode='legacy',ordinary_tax=0,special_tax=0,discount_rate=.1)
    v1=terminal_project_values(p,a,{'x':{'delay_years':1}})['x']
    v2=terminal_project_values(p,a,{'x':{'delay_months':12}})['x']
    assert np.isclose(v1,v2)
