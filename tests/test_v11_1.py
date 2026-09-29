import numpy as np
import pandas as pd
import pytest
from economics.conventions import money_factor, oil_factor, gas_factor, BBL_PER_SM3, BOE_PER_SM3_GAS
from economics.periods import expand_profile
from economics.engine import Assumptions, calculate_cashflow
from economics.commercial import apply_commercial_terms


def base_profile():
    return pd.DataFrame({'year':[2027,2028], 'oil_mmbbl':[1.,2.], 'gas_msm3':[10.,20.], 'capex_mnok':[120.,0.], 'opex_mnok':[24.,48.], 'decom_mnok':[0.,60.]})


def test_money_roundtrip_scales():
    x=12.345
    for unit in ['NOK','kNOK','MNOK','BNOK']:
        shown=x*money_factor(unit)
        assert np.isclose(shown/money_factor(unit),x)


def test_oil_roundtrip_scales():
    x=3.2
    for unit in ['bbl','kbbl','MMbbl','MSm3 oil']:
        shown=x*oil_factor(unit)
        assert np.isclose(shown/oil_factor(unit),x)
    assert np.isclose(oil_factor('MSm3 oil')*BBL_PER_SM3,1.0)


def test_gas_roundtrip_scales():
    x=170.
    for unit in ['Sm3','kSm3','MSm3','BCM','MMboe']:
        shown=x*gas_factor(unit)
        assert np.isclose(shown/gas_factor(unit),x)
    assert np.isclose(gas_factor('MMboe'),BOE_PER_SM3_GAS)


def test_revenue_dimensional_identities():
    p=pd.DataFrame({'year':[2027],'oil_mmbbl':[1.],'gas_msm3':[1.],'capex_mnok':[0.],'opex_mnok':[0.],'decom_mnok':[0.]})
    c=calculate_cashflow(p,Assumptions(oil_price_usd_bbl=80,gas_price_usd_sm3=.30,usd_nok=10,tax_mode='simple',ordinary_tax=0,special_tax=0))
    assert np.isclose(c.oil_revenue_mnok.iloc[0],800.)
    assert np.isclose(c.gas_revenue_mnok.iloc[0],3.)


def test_subannual_annual_total_reconciliation():
    p=base_profile()
    for freq in ['quarterly','monthly']:
        x=expand_profile(p,freq,cost_basis='annual_total')
        for col in ['oil_mmbbl','gas_msm3','capex_mnok','opex_mnok','decom_mnok']:
            assert np.allclose(x.groupby('year')[col].sum().to_numpy(),p[col].to_numpy())


def test_per_period_semantics_do_not_divide_again():
    p=pd.DataFrame({'year':[2027]*4,'oil_mmbbl':[1.]*4,'gas_msm3':[0.]*4,'capex_mnok':[10.]*4,'opex_mnok':[5.]*4,'decom_mnok':[0.]*4})
    x=expand_profile(p,'quarterly',cost_basis='per_period')
    assert len(x)==4 and np.isclose(x.opex_mnok.sum(),20) and np.isclose(x.capex_mnok.sum(),40)


def test_invalid_cost_basis_rejected():
    with pytest.raises(ValueError): expand_profile(base_profile(),'monthly',cost_basis='mystery')


def test_gross_field_commercial_terms_scale_with_wi():
    cf=pd.DataFrame({'oil_mmbbl':[1.],'gas_msm3':[0.],'after_tax_cf_mnok':[100.]})
    x=apply_commercial_terms(cf,tariff_nok_boe=10,third_party_income_mnok=20,working_interest=.5,commercial_basis='gross_field',base_cf_basis='gross_field')
    # base 50 - tariff 5 + income 10
    assert np.isclose(x.commercial_cf_mnok.iloc[0],55.)


def test_net_company_commercial_terms_not_scaled_twice():
    cf=pd.DataFrame({'oil_mmbbl':[1.],'gas_msm3':[0.],'after_tax_cf_mnok':[50.]})
    x=apply_commercial_terms(cf,tariff_nok_boe=10,third_party_income_mnok=20,working_interest=.5,commercial_basis='net_company',base_cf_basis='net_company')
    assert np.isclose(x.commercial_cf_mnok.iloc[0],60.)


def test_invalid_working_interest_rejected():
    cf=pd.DataFrame({'oil_mmbbl':[1.],'gas_msm3':[0.],'after_tax_cf_mnok':[50.]})
    with pytest.raises(ValueError): apply_commercial_terms(cf,working_interest=1.2)


def test_mboe_capacity_scale_is_thousand_boe():
    cf=pd.DataFrame({'oil_mmbbl':[2.],'gas_msm3':[0.],'oil_revenue_mnok':[100.],'after_tax_cf_mnok':[50.]})
    x=apply_commercial_terms(cf,host_capacity_mboe=1000)
    assert np.isclose(x.oil_mmbbl.iloc[0],1.)


def test_fiscal_v2_annual_tax_totals_reconcile_subannual():
    p=base_profile(); a=Assumptions(tax_mode='ncs_v2')
    annual=calculate_cashflow(expand_profile(p,'annual'),a)
    for freq in ['quarterly','monthly']:
        sub=calculate_cashflow(expand_profile(p,freq),a)
        assert np.isclose(sub.tax_mnok.sum(),annual.tax_mnok.sum())
        assert np.isclose(sub.ordinary_tax_mnok.sum(),annual.ordinary_tax_mnok.sum())
        assert np.isclose(sub.special_tax_mnok.sum(),annual.special_tax_mnok.sum())
