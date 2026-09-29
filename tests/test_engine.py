import pandas as pd
from economics.engine import Assumptions, calculate_cashflow, metrics

def test_cashflow_columns():
    p=pd.DataFrame({'year':[2027,2028],'oil_mmbbl':[0,1],'gas_msm3':[0,0],'capex_mnok':[100,0],'opex_mnok':[0,0],'decom_mnok':[0,0]})
    df=calculate_cashflow(p,Assumptions())
    assert 'after_tax_cf_mnok' in df
    assert isinstance(metrics(df)['npv_mnok'], float)
