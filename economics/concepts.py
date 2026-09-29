from __future__ import annotations
from dataclasses import dataclass
import copy
import pandas as pd
from .engine import calculate_cashflow, metrics

@dataclass
class DevelopmentConcept:
    name:str
    capex_factor:float=1.0
    opex_factor:float=1.0
    production_factor:float=1.0
    schedule_shift_years:int=0
    oil_price_factor:float=1.0
    gas_price_factor:float=1.0

def apply_concept(profile,a,c):
    p=profile.copy(); aa=copy.deepcopy(a)
    p['capex_mnok']*=c.capex_factor; p['opex_mnok']*=c.opex_factor
    p[['oil_mmbbl','gas_msm3']]*=c.production_factor; p['year']=p['year'].astype(int)+int(c.schedule_shift_years)
    aa.oil_price_usd_bbl*=c.oil_price_factor; aa.gas_price_usd_sm3*=c.gas_price_factor
    return p,aa

def compare_concepts(profile,a,concepts,market_deck=None,cutoff=None):
    rows=[]
    for c in concepts:
        p,aa=apply_concept(profile,a,c); cf=calculate_cashflow(p,aa,market_deck,cutoff); m=metrics(cf)
        rows.append({'concept':c.name,**m,'capex_mnok':float(cf.capex_mnok.sum()),'opex_mnok':float(cf.opex_mnok.sum()),'cutoff_year':cf.attrs.get('cutoff_year'),'cutoff_reason':cf.attrs.get('cutoff_reason')})
    return pd.DataFrame(rows)
