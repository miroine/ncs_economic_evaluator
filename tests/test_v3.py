import pandas as pd
from economics.engine import Assumptions
from economics.scenarios import Scenario, evaluate_scenarios
from economics.decision_tree import evaluate_tree
from economics.monte_carlo import run_monte_carlo, summary

def profile():
    return pd.DataFrame({'year':[2027,2028,2029],'oil_mmbbl':[0,1,1],'gas_msm3':[0,0,0],'capex_mnok':[100,0,0],'opex_mnok':[0,0,0],'decom_mnok':[0,0,0]})

def test_scenario_evaluation():
    df,_=evaluate_scenarios(profile(),Assumptions(),[Scenario('Base'),Scenario('High',production_factor=1.2)])
    assert len(df)==2 and df.loc[1,'npv_mnok']>df.loc[0,'npv_mnok']

def test_tree_scenario_link_and_decision():
    tree={'nodes':[{'id':'d','type':'decision'},{'id':'a','type':'outcome','scenario_key':'A'},{'id':'b','type':'outcome','scenario_key':'B'}], 'edges':[{'id':'e1','source':'d','target':'a'},{'id':'e2','source':'d','target':'b'}]}
    r=evaluate_tree(tree,{'A':10,'B':20}); assert r['value']==20 and 'e2' in r['selected_edges']

def test_chance_emv():
    tree={'nodes':[{'id':'c','type':'chance'},{'id':'a','type':'outcome','value':10},{'id':'b','type':'outcome','value':30}], 'edges':[{'source':'c','target':'a','probability':.25},{'source':'c','target':'b','probability':.75}]}
    assert evaluate_tree(tree)['value']==25

def test_monte_carlo_reproducible():
    x=run_monte_carlo(profile(),Assumptions(),iterations=50,seed=7); y=run_monte_carlo(profile(),Assumptions(),iterations=50,seed=7)
    assert (x==y).all() and 0 <= summary(x)['prob_npv_positive'] <= 1
