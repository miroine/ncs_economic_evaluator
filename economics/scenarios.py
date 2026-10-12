from dataclasses import dataclass, asdict
import copy
import pandas as pd
from .engine import Assumptions, calculate_cashflow, metrics

@dataclass
class Scenario:
    name: str
    oil_factor: float = 1.0
    gas_factor: float = 1.0
    capex_factor: float = 1.0
    opex_factor: float = 1.0
    production_factor: float = 1.0
    start_delay_years: int = 0

    def to_dict(self): return asdict(self)

def apply_scenario(profile: pd.DataFrame, assumptions: Assumptions, scenario: Scenario):
    p = profile.copy()
    a = copy.deepcopy(assumptions)
    a.oil_price_usd_bbl *= scenario.oil_factor
    a.gas_price_usd_sm3 *= scenario.gas_factor
    p['oil_mmbbl'] *= scenario.production_factor
    p['gas_msm3'] *= scenario.production_factor
    p['capex_mnok'] *= scenario.capex_factor
    p['opex_mnok'] *= scenario.opex_factor
    p['decom_mnok'] *= scenario.capex_factor
    if scenario.start_delay_years:
        cols = ['oil_mmbbl','gas_msm3','capex_mnok','opex_mnok','decom_mnok']
        for c in cols:
            p[c] = p[c].shift(scenario.start_delay_years, fill_value=0)
    return p, a

def evaluate_scenarios(profile, assumptions, scenarios, market_deck=None, cutoff=None):
    rows=[]; cashflows={}
    for s in scenarios:
        p,a=apply_scenario(profile, assumptions, s)
        deck=None if market_deck is None else market_deck.copy()
        if deck is not None:
            deck['oil_usd_bbl']*=s.oil_factor
            deck['gas_usd_sm3']*=s.gas_factor
        cf=calculate_cashflow(p,a,deck,cutoff); m=metrics(cf)
        rows.append({'scenario':s.name, **m})
        cashflows[s.name]=cf
    return pd.DataFrame(rows), cashflows
