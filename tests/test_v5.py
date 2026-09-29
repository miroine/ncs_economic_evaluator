import pandas as pd
from economics.fiscal_ncs import calculate_post_2022_tax, fiscal_audit
from economics.value_of_information import evpi_from_payoffs
from economics.project_io import dumps_project, loads_project
from economics.engine import Assumptions

def test_fiscal_depreciation_and_special_deduction():
    df=pd.DataFrame({'year':[2026,2027,2028,2029,2030,2031],'revenue_mnok':[0]*6,'opex_mnok':[0]*6,'decom_mnok':[0]*6,'capex_mnok':[600,0,0,0,0,0]})
    x=calculate_post_2022_tax(df)
    assert list(x.ordinary_depreciation_mnok)==[100]*6
    assert x.special_tax_base_mnok.iloc[0] < -500
    assert fiscal_audit()['special_rate']==0.718

def test_evpi():
    r=evpi_from_payoffs([[100,0],[20,60]],[.5,.5])
    assert r['evpi'] >= 0
    assert r['ev_with_perfect_information'] >= r['current_ev']

def test_project_roundtrip():
    p=pd.DataFrame([{'year':2027,'oil_mmbbl':1,'gas_msm3':0,'capex_mnok':1,'opex_mnok':1,'decom_mnok':0}])
    raw=dumps_project(p,Assumptions(),[{'name':'Base'}],{'nodes':[],'edges':[]})
    d=loads_project(raw)
    assert d['schema_version']==1 and d['profile'][0]['year']==2027
