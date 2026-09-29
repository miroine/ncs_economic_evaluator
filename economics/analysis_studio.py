from __future__ import annotations
import copy
import numpy as np
import pandas as pd
from .engine import calculate_cashflow, metrics

VARS=('Oil price','Gas price','FX','Production / reserves','CAPEX','OPEX','Discount rate','Start delay')

def evaluate(profile,a,variable,change_pct,deck=None,cutoff=None):
    p=profile.copy(); aa=copy.deepcopy(a); d=None if deck is None else deck.copy(); f=1+change_pct/100
    if variable=='Oil price': d.__setitem__('oil_usd_bbl',d.oil_usd_bbl*f) if d is not None else setattr(aa,'oil_price_usd_bbl',aa.oil_price_usd_bbl*f)
    elif variable=='Gas price': d.__setitem__('gas_usd_sm3',d.gas_usd_sm3*f) if d is not None else setattr(aa,'gas_price_usd_sm3',aa.gas_price_usd_sm3*f)
    elif variable=='FX': d.__setitem__('usd_nok',d.usd_nok*f) if d is not None else setattr(aa,'usd_nok',aa.usd_nok*f)
    elif variable=='Production / reserves': p[['oil_mmbbl','gas_msm3']]*=f
    elif variable=='CAPEX': p['capex_mnok']*=f
    elif variable=='OPEX': p['opex_mnok']*=f
    elif variable=='Discount rate': aa.discount_rate=max(-.95,aa.discount_rate*f)
    elif variable=='Start delay': p['year']=p['year'].astype(int)+int(round(change_pct/10))
    cf=calculate_cashflow(p,aa,d,cutoff); m=metrics(cf)
    m['undiscounted_after_tax_mnok']=float(cf.after_tax_cf_mnok.sum()); m['unit_cost_nok_boe']=float((cf.capex_mnok.sum()+cf.opex_mnok.sum())*1e6/max((cf.oil_mmbbl.sum()+cf.gas_msm3.sum()/159)*1e6,1))
    return m

def curve(profile,a,variable,metric='npv_mnok',changes=(-40,-30,-20,-10,0,10,20,30,40),deck=None,cutoff=None):
    return pd.DataFrame([{'change_pct':x,'value':evaluate(profile,a,variable,x,deck,cutoff).get(metric),'variable':variable,'metric':metric} for x in changes])
