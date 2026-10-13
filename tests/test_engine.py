import pandas as pd
import pytest
from economics.engine import Assumptions, calculate_cashflow, metrics, breakeven_oil_price, minimum_economic_volume

def test_cashflow_columns():
    p=pd.DataFrame({'year':[2027,2028],'oil_mmbbl':[0,1],'gas_msm3':[0,0],'capex_mnok':[100,0],'opex_mnok':[0,0],'decom_mnok':[0,0]})
    df=calculate_cashflow(p,Assumptions())
    assert 'after_tax_cf_mnok' in df
    assert isinstance(metrics(df)['npv_mnok'], float)


def test_pre_and_after_tax_npv_metrics():
    p=pd.DataFrame({'year':[2027],'oil_mmbbl':[1],'gas_msm3':[0],'capex_mnok':[100],'opex_mnok':[0],'decom_mnok':[0]})
    a=Assumptions(oil_price_usd_bbl=50,usd_nok=10,discount_rate=0,tax_mode='legacy')
    result=metrics(calculate_cashflow(p,a))
    assert result['pre_tax_npv_mnok']==400
    assert result['after_tax_npv_mnok']==10
    assert result['npv_mnok']==result['after_tax_npv_mnok']


def test_oil_breakeven_and_minimum_economic_volume():
    p=pd.DataFrame({'year':[2027],'oil_mmbbl':[1],'gas_msm3':[0],'capex_mnok':[100],'opex_mnok':[0],'decom_mnok':[0]})
    a=Assumptions(oil_price_usd_bbl=50,usd_nok=10,discount_rate=0,tax_mode='legacy',ordinary_tax=0,special_tax=0)
    assert breakeven_oil_price(p,a)==pytest.approx(10)
    assert minimum_economic_volume(p,a)==pytest.approx(.2)


def test_oil_breakeven_returns_none_when_no_root():
    p=pd.DataFrame({'year':[2027],'oil_mmbbl':[0],'gas_msm3':[0],'capex_mnok':[100],'opex_mnok':[0],'decom_mnok':[0]})
    assert breakeven_oil_price(p,Assumptions()) is None


def test_package_and_engine_exports():
    import economics
    import economics.engine as ee
    assert hasattr(economics, 'minimum_economic_volume')
    assert hasattr(ee, 'minimum_economic_volume')
    assert 'minimum_economic_volume' in economics.__all__
    assert 'minimum_economic_volume' in ee.__all__
    assert economics.minimum_economic_volume is ee.minimum_economic_volume

