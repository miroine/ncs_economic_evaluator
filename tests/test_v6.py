import pandas as pd
from economics.engine import Assumptions, calculate_cashflow
from economics.conventions import real_to_nominal_rate, nominal_to_real_rate, money_factor, oil_factor, gas_factor
from economics.analysis import tornado

def profile():
    return pd.DataFrame({'year':[2027,2028,2029], 'oil_mmbbl':[0,1,1], 'gas_msm3':[0,0,0], 'capex_mnok':[100,0,0], 'opex_mnok':[0,10,10], 'decom_mnok':[0,0,0]})

def test_fisher_roundtrip():
    r=.08; i=.025
    assert abs(nominal_to_real_rate(real_to_nominal_rate(r,i),i)-r)<1e-12

def test_units():
    assert money_factor('BNOK') == .001
    assert oil_factor('MMbbl') == 1
    assert gas_factor('BCM') == .001

def test_nominal_escalates_prices_and_costs():
    a=Assumptions(money_basis='nominal', oil_escalation=.1, gas_escalation=.1, cost_escalation=.1)
    df=calculate_cashflow(profile(),a)
    assert df.loc[2,'oil_price_usd_bbl'] > df.loc[1,'oil_price_usd_bbl']
    assert df.loc[2,'opex_mnok'] > df.loc[1,'opex_mnok']

def test_tornado_rows():
    t,b=tornado(profile(),Assumptions())
    assert len(t)==5 and 'swing' in t.columns
