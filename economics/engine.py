from dataclasses import dataclass
import numpy as np
import pandas as pd
import numpy_financial as npf

@dataclass
class Assumptions:
    oil_price_usd_bbl: float = 75.0
    gas_price_usd_sm3: float = 0.35
    usd_nok: float = 10.5
    discount_rate: float = 0.08
    ordinary_tax: float = 0.22
    special_tax: float = 0.56  # legacy simplified mode only
    tax_mode: str = 'ncs_post_2022'
    money_basis: str = 'real'
    base_year: int = 2027
    general_inflation: float = 0.025
    oil_escalation: float = 0.025
    gas_escalation: float = 0.025
    cost_escalation: float = 0.025
    discount_rate_basis: str = 'real'


def calculate_cashflow(profile: pd.DataFrame, a: Assumptions, market_deck: pd.DataFrame | None = None, cutoff=None) -> pd.DataFrame:
    df = profile.copy()
    from .conventions import consistent_discount_rate
    years = df['year'].astype(int)
    dt = (years - int(a.base_year)).clip(lower=0)
    if a.money_basis == 'nominal':
        oil_price = a.oil_price_usd_bbl * (1 + a.oil_escalation) ** dt
        gas_price = a.gas_price_usd_sm3 * (1 + a.gas_escalation) ** dt
        cost_factor = (1 + a.cost_escalation) ** dt
        for c in ['capex_mnok','opex_mnok','decom_mnok']:
            df[c] = df[c] * cost_factor
    else:
        oil_price = a.oil_price_usd_bbl
        gas_price = a.gas_price_usd_sm3
    if market_deck is not None:
        from .market import aligned_market_deck
        md=aligned_market_deck(df['year'],market_deck)
        oil_price=md['oil_usd_bbl'].to_numpy(); gas_price=md['gas_usd_sm3'].to_numpy(); fx=md['usd_nok'].to_numpy()
    else:
        fx=a.usd_nok
    df['oil_price_usd_bbl'] = oil_price
    df['gas_price_usd_sm3'] = gas_price
    df['usd_nok'] = fx
    df['oil_revenue_mnok'] = df['oil_mmbbl'] * oil_price * fx
    df['gas_revenue_mnok'] = df['gas_msm3'] * gas_price * fx
    df['revenue_mnok'] = df['oil_revenue_mnok'] + df['gas_revenue_mnok']
    if cutoff is not None:
        from .cutoff import apply_cutoff
        df = apply_cutoff(df, cutoff)
    df['pre_tax_cf_mnok'] = df['revenue_mnok'] - df['capex_mnok'] - df['opex_mnok'] - df['decom_mnok']
    if a.tax_mode == 'ncs_v2':
        from .fiscal_v2 import calculate_fiscal_v2
        df = calculate_fiscal_v2(df)
    elif a.tax_mode == 'ncs_post_2022':
        from .fiscal_ncs import calculate_post_2022_tax
        df = calculate_post_2022_tax(df)
    else:
        taxable = np.maximum(df['revenue_mnok'] - df['opex_mnok'], 0)
        df['tax_mnok'] = taxable * (a.ordinary_tax + a.special_tax)
    df['after_tax_cf_mnok'] = df['pre_tax_cf_mnok'] - df['tax_mnok']
    from .periods import period_year_fraction
    t = period_year_fraction(df)
    effective_rate = consistent_discount_rate(a.discount_rate, a.discount_rate_basis, a.money_basis, a.general_inflation)
    df['effective_discount_rate'] = effective_rate
    df['discount_factor'] = 1 / (1 + effective_rate) ** t
    df['discounted_cf_mnok'] = df['after_tax_cf_mnok'] * df['discount_factor']
    df['cumulative_cf_mnok'] = df['after_tax_cf_mnok'].cumsum()
    df['cumulative_npv_mnok'] = df['discounted_cf_mnok'].cumsum()
    return df


def metrics(df: pd.DataFrame):
    cf = df['after_tax_cf_mnok'].to_numpy()
    ppy=int(df['periods_per_year'].iloc[0]) if 'periods_per_year' in df and len(df) else 1
    period_irr = npf.irr(cf) if len(cf) > 1 else np.nan
    irr = (1+period_irr)**ppy-1 if np.isfinite(period_irr) and period_irr>-1 else period_irr
    cum = np.cumsum(cf)
    payback = (df.loc[np.where(cum >= 0)[0][0], 'period'] if 'period' in df.columns else df.loc[np.where(cum >= 0)[0][0], 'year']) if np.any(cum >= 0) else None
    return {'npv_mnok': float(df['discounted_cf_mnok'].sum()), 'irr': float(irr) if np.isfinite(irr) else None, 'payback_year': payback}


def breakeven_oil_price(profile, assumptions, low=0.0, high=250.0, iterations=80, cutoff=None):
    for _ in range(iterations):
        mid = (low + high) / 2
        trial = Assumptions(**{**assumptions.__dict__, 'oil_price_usd_bbl': mid})
        npv = metrics(calculate_cashflow(profile, trial, cutoff=cutoff))['npv_mnok']
        if npv >= 0: high = mid
        else: low = mid
    return (low + high) / 2
