import numpy as np, pandas as pd
from economics.exploration import DiscoveryCase, prospect_emv, discovery_distribution
from economics.commercial import apply_commercial_terms, phased_costs
from economics.schedule_risk import simulate_schedule_risk, schedule_summary
from economics.decision_gates import DecisionGate, gate_register
from economics.portfolio_opt import optimize_portfolio
from economics.assurance import model_health

def test_prospect_emv():
    r=prospect_emv(.25,100,[DiscoveryCase('S',.5,500),DiscoveryCase('L',.5,1500)])
    assert np.isclose(r['risked_emv_mnok'],175)
def test_discovery_probabilities_sum():
    x=discovery_distribution(.3,100,[DiscoveryCase('A',.4,1),DiscoveryCase('B',.6,2)])
    assert np.isclose(sum(r['probability'] for r in x),1)
def test_commercial_tariff_reduces_cf():
    cf=pd.DataFrame({'oil_mmbbl':[1.0],'gas_msm3':[0.0],'after_tax_cf_mnok':[100.]})
    o=apply_commercial_terms(cf,tariff_nok_boe=10); assert o.commercial_cf_mnok.iloc[0] < 100
def test_host_capacity_scales_volume():
    cf=pd.DataFrame({'oil_mmbbl':[2.0],'gas_msm3':[0.0],'oil_revenue_mnok':[100.],'after_tax_cf_mnok':[50.]})
    o=apply_commercial_terms(cf,host_capacity_mboe=1000); assert np.isclose(o.oil_mmbbl.iloc[0],1)
def test_phased_costs():
    d=phased_costs([1,2],[{'name':'Wells','total_mnok':100,'weights':[.25,.75]}]); assert np.isclose(d.total_capex_mnok.sum(),100)
def test_schedule_reproducible():
    s=[{'name':'Drill','min_months':0,'mode_months':2,'max_months':6}]
    a=simulate_schedule_risk(s,100,7); b=simulate_schedule_risk(s,100,7); assert np.allclose(a.total_delay_months,b.total_delay_months)
def test_schedule_summary_order():
    a=simulate_schedule_risk([{'name':'A','min_months':0,'mode_months':1,'max_months':4}],1000); s=schedule_summary(a); assert s['P10_months']<=s['P50_months']<=s['P90_months']
def test_gate_net_value():
    g=DecisionGate('FID',continuation_value_mnok=1000,remaining_cost_mnok=300); assert g.net_continue_value_mnok==700
def test_gate_register():
    r=gate_register([DecisionGate('FEED',continuation_value_mnok=10,remaining_cost_mnok=4)]); assert r[0]['net_continue_value_mnok']==6
def test_portfolio_constraint():
    p=[{'name':'A','value_mnok':10,'annual_capex':{2030:8}},{'name':'B','value_mnok':9,'annual_capex':{2030:5}}]
    r=optimize_portfolio(p,{2030:10}); assert r['selected']==['A']
def test_assurance_flags():
    p=pd.DataFrame({'year':[2030,2031],'oil_mmbbl':[6.,6.]}); d=pd.DataFrame({'year':[2030,2031]})
    r=model_health(p,d,[.4,.5],recoverable_oil_mmbbl=10,money_basis='real',discount_basis='nominal'); assert sum(x['status']=='WARN' for x in r)>=3
