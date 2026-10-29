from dataclasses import dataclass
import numpy as np
import pandas as pd
from .scenarios import apply_scenario
from .decision_tree import evaluate_tree
from .batch import npv_cases

@dataclass
class VariableSpec:
    distribution: str = 'lognormal'  # lognormal, normal, triangular
    sigma_pct: float = 0.20
    low: float = 0.8
    mode: float = 1.0
    high: float = 1.2

@dataclass
class Uncertainty:
    oil_price_pct: float = 0.20
    gas_price_pct: float = 0.20
    capex_pct: float = 0.20
    opex_pct: float = 0.15
    production_pct: float = 0.15
    oil_distribution: str = 'lognormal'
    gas_distribution: str = 'lognormal'
    capex_distribution: str = 'lognormal'
    opex_distribution: str = 'lognormal'
    production_distribution: str = 'lognormal'
    price_correlation: float = 0.35
    cost_correlation: float = 0.40
    resource_cost_correlation: float = 0.15

_NAMES=('oil','gas','capex','opex','production')

def _nearest_psd_corr(c):
    c=np.asarray(c,float); c=(c+c.T)/2
    vals,vecs=np.linalg.eigh(c); vals=np.maximum(vals,1e-8)
    c=(vecs*vals)@vecs.T; d=np.sqrt(np.diag(c)); c=c/np.outer(d,d)
    return c

def correlation_matrix(u: Uncertainty):
    c=np.eye(5)
    c[0,1]=c[1,0]=np.clip(u.price_correlation,-.95,.95)
    c[2,3]=c[3,2]=np.clip(u.cost_correlation,-.95,.95)
    c[2,4]=c[4,2]=np.clip(u.resource_cost_correlation,-.95,.95)
    return _nearest_psd_corr(c)

def _normal_cdf(z):
    # Fast erf approximation adequate for simulation copula transforms.
    sign=np.sign(z); x=np.abs(z)/np.sqrt(2); t=1/(1+0.3275911*x)
    erf=1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-0.284496736)*t+0.254829592)*t*np.exp(-x*x)
    return .5*(1+sign*erf)

def _factor_from_z(z, sigma, distribution):
    sigma=max(float(sigma),0.0)
    if sigma==0: return np.ones_like(z)
    if distribution=='normal': return np.maximum(0.01,1+sigma*z)
    if distribution=='triangular':
        u=np.clip(_normal_cdf(z),1e-9,1-1e-9); lo=max(.01,1-2*sigma); hi=1+2*sigma; mode=1.; f=(mode-lo)/(hi-lo)
        return np.where(u<f, lo+np.sqrt(u*(hi-lo)*(mode-lo)), hi-np.sqrt((1-u)*(hi-lo)*(hi-mode)))
    s=np.sqrt(np.log1p(sigma*sigma)); mu=-.5*s*s
    return np.exp(mu+s*z)

def sample_factors(u=Uncertainty(), iterations=2000, seed=42):
    rng=np.random.default_rng(seed); z=rng.multivariate_normal(np.zeros(5),correlation_matrix(u),size=iterations)
    sig=[u.oil_price_pct,u.gas_price_pct,u.capex_pct,u.opex_pct,u.production_pct]
    dist=[u.oil_distribution,u.gas_distribution,u.capex_distribution,u.opex_distribution,u.production_distribution]
    arr=np.column_stack([_factor_from_z(z[:,i],sig[i],dist[i]) for i in range(5)])
    return pd.DataFrame(arr,columns=_NAMES)

def run_monte_carlo(profile, assumptions, uncertainty=Uncertainty(), iterations=2000, seed=42, return_factors=False, market_deck=None, cutoff=None):
    factors=sample_factors(uncertainty,iterations,seed)
    cases=np.column_stack([factors.to_numpy(float),np.ones(iterations)])
    out=npv_cases(profile,assumptions,cases,market_deck,cutoff)
    return (out,factors) if return_factors else out

def run_tree_monte_carlo(profile, assumptions, scenarios, tree, uncertainty=Uncertainty(), iterations=1000, seed=42, market_deck=None, cutoff=None):
    factors=sample_factors(uncertainty,iterations,seed); tree_values=np.empty(iterations); scenario_rows=[]
    cases=np.column_stack([factors.to_numpy(float),np.ones(iterations)])
    scenario_samples={}
    for s in scenarios:
        p,a=apply_scenario(profile,assumptions,s)
        deck=None if market_deck is None else market_deck.copy()
        if deck is not None:
            deck['oil_usd_bbl']*=s.oil_factor
            deck['gas_usd_sm3']*=s.gas_factor
        scenario_samples[s.name]=npv_cases(p,a,cases,deck,cutoff)
    for i in range(iterations):
        vals={name:values[i] for name,values in scenario_samples.items()}
        tr=evaluate_tree(tree,vals); tree_values[i]=tr['value']
        scenario_rows.append(vals)
    return tree_values,pd.DataFrame(scenario_rows),factors

def summary(values):
    values=np.asarray(values,float); q=np.percentile(values,[10,50,90])
    return {'P10':float(q[0]),'P50':float(q[1]),'P90':float(q[2]),'mean':float(np.mean(values)),'prob_npv_positive':float(np.mean(values>0))}
