import numpy as np
import pandas as pd
from economics.engine import Assumptions
from economics.monte_carlo import Uncertainty, sample_factors, correlation_matrix, run_tree_monte_carlo
from economics.scenarios import Scenario

def profile():
    return pd.DataFrame({'year':[2027,2028,2029],'oil_mmbbl':[0,1,1],'gas_msm3':[0,0,0],'capex_mnok':[100,0,0],'opex_mnok':[0,10,10],'decom_mnok':[0,0,0]})

def test_correlated_samples_are_positive_for_lognormal():
    u=Uncertainty(price_correlation=.7)
    f=sample_factors(u,3000,7)
    assert (f>0).all().all()
    assert f[['oil','gas']].corr().iloc[0,1] > .55

def test_corr_matrix_is_psd():
    u=Uncertainty(price_correlation=.9,cost_correlation=.9,resource_cost_correlation=.9)
    eig=np.linalg.eigvalsh(correlation_matrix(u))
    assert eig.min() > -1e-8

def test_tree_mc_returns_expected_shapes():
    tree={'nodes':[{'id':'d','type':'decision'},{'id':'o','type':'outcome','scenario_key':'Base'}], 'edges':[{'id':'e','source':'d','target':'o'}]}
    tv,sv,f=run_tree_monte_carlo(profile(),Assumptions(),[Scenario('Base')],tree,Uncertainty(),25,1)
    assert len(tv)==25 and len(sv)==25 and len(f)==25
    assert np.isfinite(tv).all()
