import numpy as np
import pandas as pd
from economics.engine import Assumptions, calculate_cashflow
from economics.cutoff import CutoffSettings
from economics.production import generated_profile
from economics.concepts import DevelopmentConcept, compare_concepts
from economics.value_of_information import evsi_from_signals
from economics.advanced_analysis import breakeven_suite

def profile():
    return pd.DataFrame({'year':[2027,2028,2029,2030,2031],'oil_mmbbl':[5,4,2,.2,.1],'gas_msm3':[0]*5,'capex_mnok':[100,0,0,0,0],'opex_mnok':[20,20,20,20,20],'decom_mnok':[0,0,0,0,50]})

def test_hard_cutoff_moves_decom():
    cf=calculate_cashflow(profile(),Assumptions(),cutoff=CutoffSettings(mode='hard',hard_cutoff_year=2030,decom_lag_periods=1))
    assert cf.attrs['cutoff_year']==2030 and cf.loc[cf.year==2030,'oil_mmbbl'].iloc[0]==0
    assert cf.loc[cf.year==2031,'decom_mnok'].iloc[0]==50

def test_negative_ocf_cutoff():
    cf=calculate_cashflow(profile(),Assumptions(oil_price_usd_bbl=5),cutoff=CutoffSettings(mode='negative_ocf',consecutive_negative_periods=2))
    assert cf.attrs['cutoff_year'] is not None

def test_generated_profile_reserve_constraint():
    p=generated_profile(2030,years=12,oil_reserves_mmbbl=40,oil_plateau_mmbbl=10)
    assert p.oil_mmbbl.sum() <= 40.000001 and len(p)==12

def test_concept_comparison():
    out=compare_concepts(profile(),Assumptions(),[DevelopmentConcept('A'),DevelopmentConcept('B',capex_factor=1.2)])
    assert list(out.concept)==['A','B'] and out.loc[0,'npv_mnok'] != out.loc[1,'npv_mnok']

def test_evsi_net_value():
    r=evsi_from_signals([[0,100],[40,40]],[.5,.5],[[.8,.2],[.2,.8]],information_cost=5)
    assert r['evsi']>=0 and np.isclose(r['net_value_of_information'],r['evsi']-5)

def test_breakeven_suite_shape():
    x=breakeven_suite(profile(),Assumptions())
    assert {'Oil price','CAPEX','Production'}.issubset(set(x.variable))
