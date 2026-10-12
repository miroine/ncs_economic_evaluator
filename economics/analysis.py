import numpy as np
import pandas as pd
from .engine import Assumptions, calculate_cashflow, metrics


def tornado(profile, assumptions, low=0.8, high=1.2, market_deck=None, cutoff=None):
    base = metrics(calculate_cashflow(profile, assumptions, market_deck, cutoff))['npv_mnok']
    specs = ['Oil price','Gas price','Production','CAPEX','OPEX']
    rows=[]
    for name in specs:
        vals=[]
        for factor in (low, high):
            p=profile.copy(); a=Assumptions(**assumptions.__dict__)
            deck=None if market_deck is None else market_deck.copy()
            if name=='Oil price':
                if deck is None: a.oil_price_usd_bbl*=factor
                else: deck['oil_usd_bbl']*=factor
            elif name=='Gas price':
                if deck is None: a.gas_price_usd_sm3*=factor
                else: deck['gas_usd_sm3']*=factor
            elif name=='Production':
                p['oil_mmbbl']*=factor; p['gas_msm3']*=factor
            elif name=='CAPEX': p['capex_mnok']*=factor
            elif name=='OPEX': p['opex_mnok']*=factor
            vals.append(metrics(calculate_cashflow(p,a,deck,cutoff))['npv_mnok'])
        rows.append({'variable':name,'low_npv':vals[0],'high_npv':vals[1],
                     'low_delta':vals[0]-base,'high_delta':vals[1]-base,
                     'swing':abs(vals[1]-vals[0])})
    return pd.DataFrame(rows).sort_values('swing',ascending=True), base


def sensitivity_curve(profile, assumptions, variable, factors=None, market_deck=None, cutoff=None):
    factors=np.asarray(factors if factors is not None else np.linspace(.6,1.4,17))
    rows=[]
    for f in factors:
        p=profile.copy(); a=Assumptions(**assumptions.__dict__)
        deck=None if market_deck is None else market_deck.copy()
        if variable=='Oil price':
            if deck is None: a.oil_price_usd_bbl*=f
            else: deck['oil_usd_bbl']*=f
        elif variable=='Gas price':
            if deck is None: a.gas_price_usd_sm3*=f
            else: deck['gas_usd_sm3']*=f
        elif variable=='Production': p[['oil_mmbbl','gas_msm3']]*=f
        elif variable=='CAPEX': p['capex_mnok']*=f
        elif variable=='OPEX': p['opex_mnok']*=f
        rows.append({'factor':f,'change_pct':(f-1)*100,'npv_mnok':metrics(calculate_cashflow(p,a,deck,cutoff))['npv_mnok']})
    return pd.DataFrame(rows)


def npv_waterfall(cf):
    components={
        'Oil revenue': cf['oil_revenue_mnok'].sum(),
        'Gas revenue': cf['gas_revenue_mnok'].sum(),
        'CAPEX': -cf['capex_mnok'].sum(),
        'OPEX': -cf['opex_mnok'].sum(),
        'Decommissioning': -cf['decom_mnok'].sum(),
        'Tax': -cf['tax_mnok'].sum(),
    }
    return components
