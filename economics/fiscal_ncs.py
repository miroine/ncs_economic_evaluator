"""NCS petroleum fiscal model.

Baseline for post-2022 qualifying offshore investments. This is an analytical model,
not tax advice. Transitional section 11 assets are deliberately represented as a
separate regime because their uplift/vintage treatment must be supplied explicitly.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass
class FiscalRegime:
    name: str = "post_2022_cashflow"
    ordinary_rate: float = 0.22
    special_rate: float = 0.718
    ordinary_depreciation_years: int = 6
    special_immediate_investment_deduction: bool = True
    loss_refund_special: bool = True
    source_version: str = "Skatteetaten petroleum tax regulations, checked 2026-09-29"


def _depreciation_schedule(capex: np.ndarray, years: int) -> np.ndarray:
    dep = np.zeros_like(capex, dtype=float)
    for lag in range(min(years, capex.shape[-1])):
        dep[..., lag:] += np.maximum(capex[..., :capex.shape[-1]-lag], 0) / years
    return dep


def tax_ledger_arrays(revenue, opex, capex, decom, ordinary_rate=.22,
                      special_rate=.718, depreciation_years=6,
                      loss_interest=0., special_loss_refund=True):
    """Shared fiscal ledger for one case or a batch, with time on the last axis."""
    dep = _depreciation_schedule(capex, depreciation_years)
    margin = revenue - opex - decom
    ordinary_base = np.zeros_like(margin)
    loss_balance = np.zeros_like(margin)
    loss = np.zeros(margin.shape[:-1])
    for i in range(margin.shape[-1]):
        net = margin[..., i] - dep[..., i] + loss * (1 + loss_interest)
        ordinary_base[..., i] = np.maximum(net, 0)
        loss = np.minimum(net, 0)
        loss_balance[..., i] = loss
    ordinary_tax = ordinary_base * ordinary_rate
    special_base = margin - capex - ordinary_tax
    special_tax = (special_base if special_loss_refund else np.maximum(special_base, 0)) * special_rate
    return {
        'ordinary_depreciation_mnok': dep,
        'ordinary_tax_base_mnok': ordinary_base,
        'ordinary_loss_cf_mnok': loss_balance,
        'ordinary_tax_mnok': ordinary_tax,
        'special_tax_base_mnok': special_base,
        'special_tax_mnok': special_tax,
        'tax_mnok': ordinary_tax + special_tax,
    }


def calculate_post_2022_tax(df: pd.DataFrame, regime: FiscalRegime | None = None) -> pd.DataFrame:
    """Calculate a transparent project-level post-2022 NCS tax approximation.

    Excludes financing allocation, norm-price adjustments, company portfolio offsets,
    non-qualifying assets and temporary-rule uplift. Special-tax losses are modelled
    as same-period tax value/refund for analytical neutrality.
    """
    r = regime or FiscalRegime()
    out = df.copy()
    capex = out['capex_mnok'].to_numpy(float)
    ledger = tax_ledger_arrays(
        out['revenue_mnok'].to_numpy(float), out['opex_mnok'].to_numpy(float),
        capex, out['decom_mnok'].to_numpy(float),
        r.ordinary_rate, r.special_rate, r.ordinary_depreciation_years,
    )
    for column, values in ledger.items():
        out[column] = values
    return out


def fiscal_audit(regime: FiscalRegime | None = None) -> dict:
    r = regime or FiscalRegime()
    return {
        'regime': r.name,
        'ordinary_rate': r.ordinary_rate,
        'special_rate': r.special_rate,
        'combined_marginal_rate': 0.78,
        'ordinary_depreciation_years': r.ordinary_depreciation_years,
        'special_investment_deduction': '100% in investment year for qualifying post-2022 offshore investment',
        'limitations': ['project-level approximation','no financing allocation','no norm-price adjustment','no temporary-rule uplift','no company portfolio tax position'],
        'source_version': r.source_version,
    }
