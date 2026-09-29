from __future__ import annotations
import numpy as np

def model_health(profile=None, market_deck=None, probabilities=None, cutoff_info=None, recoverable_oil_mmbbl=None, money_basis=None, discount_basis=None):
    checks=[]
    def add(name,ok,message): checks.append({'check':name,'status':'PASS' if ok else 'WARN','message':message})
    if profile is not None and recoverable_oil_mmbbl is not None:
        produced=float(profile.get('oil_mmbbl',[]).sum()); add('Reserves balance',produced<=float(recoverable_oil_mmbbl)+1e-9,f'Produced {produced:.1f} vs recoverable {recoverable_oil_mmbbl:.1f} MMbbl')
    if market_deck is not None and profile is not None and 'year' in profile and 'year' in market_deck:
        ok=float(market_deck.year.min())<=float(profile.year.min()) and float(market_deck.year.max())>=float(profile.year.max()); add('Market deck coverage',ok,'Deck covers project life' if ok else 'Deck does not cover full project life')
    if probabilities is not None:
        s=float(np.sum(probabilities)); add('Probability total',np.isclose(s,1.0),f'Probability sum = {s:.6f}')
    if cutoff_info is not None:
        cy=cutoff_info.get('cessation_year'); dy=cutoff_info.get('decom_year'); ok=cy is None or dy is None or dy>=cy; add('Decommissioning timing',ok,'Decommissioning is not before cessation' if ok else 'Decommissioning precedes cessation')
    if money_basis and discount_basis: add('Money/discount basis',str(money_basis).lower()==str(discount_basis).lower(),f'{money_basis} cash flow / {discount_basis} discount rate')
    return checks
