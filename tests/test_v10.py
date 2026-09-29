import numpy as np, pandas as pd
from economics.engine import Assumptions, calculate_cashflow, metrics
from economics.periods import expand_profile
from economics.decks_v2 import named_decks, select_deck
from economics.reserves import reserves_profile
from economics.fiscal_v2 import calculate_fiscal_v2
from economics.analysis_studio import curve
from economics.uncertainty_v2 import diagnostics
from economics.reporting import decision_report_text
from economics.portfolio import snapshot, dumps_snapshots

def profile():
    return pd.DataFrame({'year':[2027,2028,2029],'oil_mmbbl':[0,10,8],'gas_msm3':[0,100,80],'capex_mnok':[1000,100,0],'opex_mnok':[10,200,180],'decom_mnok':[0,0,300]})

def test_period_expansion_preserves_totals():
    p=profile(); q=expand_profile(p,'quarterly'); m=expand_profile(p,'monthly')
    assert len(q)==12 and len(m)==36
    for c in ['oil_mmbbl','gas_msm3','capex_mnok','opex_mnok','decom_mnok']:
        assert np.isclose(q[c].sum(),p[c].sum()) and np.isclose(m[c].sum(),p[c].sum())

def test_fractional_discounting_differs():
    a=Assumptions(); annual=calculate_cashflow(expand_profile(profile(),'annual'),a)
    quarterly=calculate_cashflow(expand_profile(profile(),'quarterly'),a)
    assert quarterly.discount_factor.iloc[1] > annual.discount_factor.iloc[1]

def test_named_decks():
    d=named_decks([2027,2028]); assert set(d.deck)=={'Low','Base','High'}
    assert select_deck(d,'High').oil_usd_bbl.mean()>select_deck(d,'Base').oil_usd_bbl.mean()

def test_reserves_cap():
    r=reserves_profile(2027,100,.3,12,life=30); assert r.oil_mmbbl.sum()<=30.000001

def test_fiscal_v2_columns():
    cf=calculate_cashflow(profile(),Assumptions(tax_mode='ncs_v2')); assert {'ordinary_tax_mnok','special_tax_mnok','tax_mnok'}<=set(cf.columns)

def test_analysis_studio_curve():
    x=curve(profile(),Assumptions(),'Oil price'); assert len(x)==9 and x.value.notna().all()

def test_uncertainty_diagnostics():
    d,c=diagnostics(np.array([-1,0,1,2]),pd.DataFrame({'oil':[.8,.9,1.1,1.2]})); assert d['prob_negative']==.25 and c is not None

def test_reporting_and_snapshot():
    b=decision_report_text('Demo',{'npv_mnok':1}); assert b'Demo' in b
    assert b'v1' in dumps_snapshots([snapshot('Demo','v1',{'npv':1})])

def test_decision_tree_branch_cost_and_delay():
    from economics.decision_tree import evaluate_tree
    tree={'nodes':[{'id':'d','type':'decision'},{'id':'a','type':'outcome','value':100},{'id':'b','type':'outcome','value':80}], 'edges':[{'id':'ea','source':'d','target':'a','cost_mnok':30},{'id':'eb','source':'d','target':'b','cost_mnok':0}]}
    r=evaluate_tree(tree); assert r['value']==80 and r['selected_edges']==['eb']
