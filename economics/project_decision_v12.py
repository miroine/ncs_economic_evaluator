from __future__ import annotations
from .engine import Assumptions, calculate_cashflow, metrics
from .decision_tree import evaluate_tree

_FLOW_COLS=('oil_mmbbl','gas_msm3','capex_mnok','opex_mnok','decom_mnok')

def _periods_per_year(profile):
    if 'periods_per_year' in profile and len(profile): return max(1,int(profile['periods_per_year'].iloc[0]))
    if 'year' in profile and len(profile): return max(1,int(profile.groupby('year').size().max()))
    return 1

def _delay_flows(profile,months):
    p=profile.copy(); ppy=_periods_per_year(p)
    rows=max(0,int(round(float(months)*ppy/12.0)))
    for c in _FLOW_COLS:
        if c in p: p[c]=p[c].shift(rows,fill_value=0.0)
    return p,rows

def terminal_project_values(profile, assumptions:Assumptions, terminal_states, market_deck=None, cutoff=None):
    values={}
    for key,o in terminal_states.items():
        p=profile.copy(); a=Assumptions(**assumptions.__dict__)
        for col,mult in [('oil_mmbbl','production_multiplier'),('gas_msm3','production_multiplier'),('capex_mnok','capex_multiplier'),('opex_mnok','opex_multiplier')]:
            if col in p: p[col]=p[col]*float(o.get(mult,1.0))
        a.oil_price_usd_bbl*=float(o.get('oil_price_multiplier',1.0)); a.gas_price_usd_sm3*=float(o.get('gas_price_multiplier',1.0)); a.usd_nok*=float(o.get('fx_multiplier',1.0))
        months=float(o.get('delay_months',float(o.get('delay_years',0))*12.0))
        p,_=_delay_flows(p,months)
        values[key]=metrics(calculate_cashflow(p,a,market_deck,cutoff))['npv_mnok']
    return values

def evaluate_project_tree(tree,profile,assumptions,terminal_states,market_deck=None,cutoff=None):
    vals=terminal_project_values(profile,assumptions,terminal_states,market_deck,cutoff)
    return evaluate_tree(tree,vals,discount_rate=assumptions.discount_rate), vals
