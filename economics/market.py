from __future__ import annotations
import numpy as np
import pandas as pd

REQUIRED = ['year','oil_usd_bbl','gas_usd_sm3','usd_nok']

def default_market_deck(years, oil=75.0, gas=0.35, usd_nok=10.5):
    return pd.DataFrame({'year':list(years),'oil_usd_bbl':oil,'gas_usd_sm3':gas,'usd_nok':usd_nok})

def validate_market_deck(deck: pd.DataFrame) -> list[str]:
    missing=[c for c in REQUIRED if c not in deck.columns]
    if missing: return ['Missing market-deck columns: '+', '.join(missing)]
    issues=[]
    if deck['year'].duplicated().any(): issues.append('Market-deck years must be unique.')
    for c in REQUIRED[1:]:
        x=pd.to_numeric(deck[c],errors='coerce')
        if x.isna().any(): issues.append(f'{c} contains non-numeric values.')
        if (x<0).any(): issues.append(f'{c} contains negative values.')
    return issues

def aligned_market_deck(years, deck: pd.DataFrame):
    issues=validate_market_deck(deck)
    if issues: raise ValueError(' '.join(issues))
    y=pd.DataFrame({'year':pd.Series(years,dtype=int)})
    d=deck.copy(); d['year']=d['year'].astype(int); d=d.sort_values('year')
    out=y.merge(d,on='year',how='left')
    for c in REQUIRED[1:]: out[c]=out[c].interpolate(limit_direction='both')
    return out
