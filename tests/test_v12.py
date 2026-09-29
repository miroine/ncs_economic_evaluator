import numpy as np, pandas as pd, pytest
from economics.physical_v12 import ResourceCase, FacilityLimits, recoverable_resources, integrated_profile
from economics.schedule_v12 import validate_schedule, simulate_schedule
from economics.cost_fx_v12 import convert_cost_lines
from economics.emissions_v12 import emissions_economics
from economics.uncertainty_register_v12 import validate_register, sample_register
from economics.validation_v12 import validate_model, has_errors
from economics.inspector_v12 import inspect_period
from economics.project_decision_v12 import terminal_project_values, evaluate_project_tree
from economics.engine import Assumptions, calculate_cashflow

def base_profile():
    return pd.DataFrame({'year':[2027,2028,2029],'oil_mmbbl':[0,1,1],'gas_msm3':[0,0,0],'capex_mnok':[100,0,0],'opex_mnok':[0,10,10],'decom_mnok':[0,0,0]})

def test_recoverable_resources():
    r=recoverable_resources(ResourceCase(100,.3,2,.5)); assert r['oil_mmbbl']==30; assert r['gas_msm3']==1000

def test_integrated_profile_well_and_facility_constraints():
    p=integrated_profile([2028,2029],ResourceCase(100,.5),[{'onstream_year':2028,'oil_kbopd':20}],FacilityLimits(oil_kbopd=10,uptime=1))
    assert np.allclose(p.oil_mmbbl,[3.66,3.65]); assert (p.oil_mmbbl<=p.well_oil_capacity_mmbbl).all(); assert (p.oil_mmbbl<=p.facility_oil_capacity_mmbbl).all()

def test_integrated_profile_resource_cap():
    p=integrated_profile([2028,2029],ResourceCase(1,1),[{'onstream_year':2028,'oil_kbopd':100}],FacilityLimits(oil_kbopd=100,uptime=1)); assert abs(p.oil_mmbbl.sum()-1)<1e-9; assert p.remaining_oil_mmbbl.iloc[-1]==0

def test_schedule_dependency_validation_and_sim():
    a=[{'name':'FEED','start':2027,'end':2028},{'name':'Build','start':2028,'end':2030,'depends_on':['FEED'],'delay_low':0,'delay_mode':.2,'delay_high':.5}]
    assert not validate_schedule(a); s=simulate_schedule(a,20); assert len(s)==20; assert (s.first_oil>=2030).all()

def test_schedule_invalid_dependency():
    a=[{'name':'Build','start':2027,'end':2028,'depends_on':['Missing']}]; assert validate_schedule(a)

def test_multicurrency_conversion():
    lines=[{'year':2028,'category':'well','currency':'USD','amount':1e6},{'year':2028,'category':'host','currency':'NOK','amount':10e6}]
    fx=pd.DataFrame({'year':[2028],'USD':[10.],'EUR':[11.],'GBP':[12.]}); x=convert_cost_lines(lines,fx); assert np.allclose(x.cost_mnok,[10,10])

def test_fx_missing_year_rejected():
    with pytest.raises(ValueError): convert_cost_lines([{'year':2029,'category':'x','currency':'USD','amount':1}],pd.DataFrame({'year':[2028],'USD':[10.],'EUR':[11.],'GBP':[12.]}))

def test_emissions_units_and_reduction():
    p=pd.DataFrame({'oil_mmbbl':[1.0],'gas_msm3':[0.]}); e=emissions_economics(p,20,1000,.5); assert abs(e.co2_tonnes.iloc[0]-10000)<1e-9; assert abs(e.carbon_cost_mnok.iloc[0]-10)<1e-9

def test_uncertainty_register_correlation():
    reg=[{'name':'a','distribution':'normal','mean':0,'std':1},{'name':'b','distribution':'uniform','low':0,'high':1}]; c=np.array([[1,.5],[.5,1]])
    assert not validate_register(reg,c); s=sample_register(reg,200,c,1); assert s.shape==(200,2)

def test_bad_correlation_rejected():
    reg=[{'name':'a','distribution':'normal','mean':0,'std':1}]; assert validate_register(reg,[[.9]])

def test_inspector_reconciles_revenue_and_discount():
    cf=calculate_cashflow(base_profile(),Assumptions(tax_mode='legacy',ordinary_tax=0,special_tax=0)); x=inspect_period(cf,1); assert abs(x['oil_revenue_formula_mnok']-x['oil_revenue_reported_mnok'])<1e-9; assert abs(x['after_tax_cf_mnok']*x['discount_factor']-x['discounted_cf_mnok'])<1e-9

def test_validation_gate():
    phys=integrated_profile([2028],ResourceCase(10,.5),[{'onstream_year':2028,'oil_kbopd':10}],FacilityLimits(oil_kbopd=5,uptime=1)); checks=validate_model(base_profile(),physical=phys); assert not has_errors(checks)

def test_project_terminal_values_and_tree():
    p=base_profile(); a=Assumptions(tax_mode='legacy',ordinary_tax=0,special_tax=0)
    states={'base':{},'high':{'oil_price_multiplier':2}}
    vals=terminal_project_values(p,a,states); assert vals['high']>vals['base']
    tree={'nodes':[{'id':'d','type':'decision'},{'id':'b','type':'outcome','scenario_key':'base'},{'id':'h','type':'outcome','scenario_key':'high'}],'edges':[{'id':'e1','source':'d','target':'b'},{'id':'e2','source':'d','target':'h'}]}
    res,_=evaluate_project_tree(tree,p,a,states); assert res['value']==pytest.approx(vals['high'])
