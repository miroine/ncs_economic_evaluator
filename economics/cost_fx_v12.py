from __future__ import annotations
import pandas as pd
SUPPORTED={'NOK','USD','EUR','GBP'}

def convert_cost_lines(lines, fx_deck, base_year=None):
    df=pd.DataFrame(lines).copy()
    if df.empty: return pd.DataFrame(columns=['year','category','currency','amount','fx_nok_per_unit','cost_mnok'])
    if not set(df.currency).issubset(SUPPORTED): raise ValueError('Unsupported currency')
    fx=pd.DataFrame(fx_deck).copy(); req={'year','USD','EUR','GBP'}
    if not req.issubset(fx.columns): raise ValueError('FX deck requires year, USD, EUR, GBP')
    m=df.merge(fx,on='year',how='left',validate='many_to_one')
    if m[['USD','EUR','GBP']].isna().any().any(): raise ValueError('FX deck does not cover all cost years')
    def rate(r): return 1.0 if r.currency=='NOK' else float(r[r.currency])
    m['fx_nok_per_unit']=m.apply(rate,axis=1); m['cost_mnok']=m['amount']*m['fx_nok_per_unit']/1e6
    if 'escalation' in m:
        by=int(base_year if base_year is not None else m.year.min()); m['cost_mnok']*= (1+m['escalation'].fillna(0))**(m.year-by)
    return m
