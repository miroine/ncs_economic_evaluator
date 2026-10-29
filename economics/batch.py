"""NPV-only evaluation with shared fiscal rules and vectorized case arithmetic."""
import numpy as np

from .engine import calculate_cashflow
from .fiscal_ncs import tax_ledger_arrays

FACTOR_NAMES = ('Oil price', 'Gas price', 'CAPEX', 'OPEX', 'Production', 'FX')


def npv_cases(profile, assumptions, factors, market_deck=None, cutoff=None):
    """Evaluate factor rows (oil, gas, CAPEX, OPEX, production, FX) in MNOK."""
    factors = np.asarray(factors, dtype=float)
    if factors.ndim != 2 or factors.shape[1] != len(FACTOR_NAMES):
        raise ValueError('Expected factor rows with six columns: ' + ', '.join(FACTOR_NAMES))
    if not np.isfinite(factors).all():
        raise ValueError('Analysis factors must be finite')
    base = calculate_cashflow(profile, assumptions, market_deck)
    results = []
    # Bound memory for long monthly profiles and large simulations.
    for start in range(0, len(factors), 512):
        f = factors[start:start + 512]
        oil = f[:, 4, None] * base['oil_mmbbl'].to_numpy(float)
        gas = f[:, 4, None] * base['gas_msm3'].to_numpy(float)
        revenue = (
            oil * base['oil_price_usd_bbl'].to_numpy(float) * f[:, 0, None]
            + gas * base['gas_price_usd_sm3'].to_numpy(float) * f[:, 1, None]
        ) * base['usd_nok'].to_numpy(float) * f[:, 5, None]
        capex = f[:, 2, None] * base['capex_mnok'].to_numpy(float)
        opex = f[:, 3, None] * base['opex_mnok'].to_numpy(float)
        decom = np.broadcast_to(base['decom_mnok'].to_numpy(float), revenue.shape).copy()
        n = len(base)
        if cutoff is not None and cutoff.mode != 'none':
            positions = np.arange(n)
            cessation = np.full(len(f), n)
            if cutoff.hard_cutoff_year is not None:
                hard = np.flatnonzero(base['year'].to_numpy(int) >= cutoff.hard_cutoff_year)
                if len(hard):
                    cessation[:] = hard[0]
            if cutoff.minimum_oil_mmbbl > 0 or cutoff.minimum_gas_msm3 > 0:
                mask = (oil < cutoff.minimum_oil_mmbbl) & (gas < cutoff.minimum_gas_msm3)
                cessation = np.minimum(cessation, np.where(mask, positions, n).min(axis=1))
            ocf = revenue - opex
            if cutoff.mode == 'negative_ocf':
                run = np.zeros(len(f), dtype=int)
                count = max(1, int(cutoff.consecutive_negative_periods))
                for i in range(n):
                    run = np.where(ocf[:, i] < 0, run + 1, 0)
                    cessation = np.minimum(cessation, np.where(run >= count, i - count + 1, n))
            elif cutoff.mode == 'economic_limit':
                horizon = max(1, int(cutoff.lookahead_periods))
                for i in range(n):
                    stop = (ocf[:, i] < 0) & (ocf[:, i:min(n, i + horizon)].sum(axis=1) <= 0)
                    cessation = np.minimum(cessation, np.where(stop, i, n))
            active = positions < cessation[:, None]
            revenue = np.where(active, revenue, 0)
            opex = np.where(active, opex, 0)
            if cutoff.move_decom:
                stopped = np.flatnonzero(cessation < n)
                total = decom[stopped].sum(axis=1)
                decom[stopped] = 0
                target = np.minimum(cessation[stopped] + max(0, int(cutoff.decom_lag_periods)), n - 1)
                decom[stopped, target] = total
        if assumptions.tax_mode == 'ncs_v2':
            years = base['year'].to_numpy(int)
            unique_years = np.unique(years)
            annual = [np.column_stack([x[:, years == year].sum(axis=1) for year in unique_years])
                      for x in (revenue, opex, capex, decom)]
            if 'tariff_mnok' in base:
                annual[1] += np.array([base.loc[years == year, 'tariff_mnok'].sum() for year in unique_years])
            annual_tax = tax_ledger_arrays(*annual)['tax_mnok']
            tax = np.zeros_like(revenue)
            last = [np.flatnonzero(years == year)[-1] for year in unique_years]
            tax[:, last] = annual_tax
        elif assumptions.tax_mode == 'ncs_post_2022':
            tax = tax_ledger_arrays(revenue, opex, capex, decom)['tax_mnok']
        else:
            tax = np.maximum(revenue - opex, 0) * (assumptions.ordinary_tax + assumptions.special_tax)
        results.append(((revenue - capex - opex - decom - tax) * base['discount_factor'].to_numpy(float)).sum(axis=1))
    return np.concatenate(results) if results else np.empty(0)
