from __future__ import annotations
import pandas as pd
from .market import default_market_deck, validate_market_deck

def named_decks(years, oil=75., gas=.35, fx=10.5):
    base=default_market_deck(years,oil,gas,fx)
    low=base.copy(); low['oil_usd_bbl']*=.75; low['gas_usd_sm3']*=.80; low['deck']='Low'
    high=base.copy(); high['oil_usd_bbl']*=1.25; high['gas_usd_sm3']*=1.20; high['deck']='High'
    base['deck']='Base'
    return pd.concat([base,low,high],ignore_index=True)

def select_deck(table: pd.DataFrame, name: str):
    if 'deck' not in table: return table.copy()
    out=table[table['deck'].astype(str)==str(name)].drop(columns='deck').copy()
    if out.empty: raise ValueError(f'Unknown deck: {name}')
    issues=validate_market_deck(out)
    if issues: raise ValueError(' '.join(issues))
    return out
