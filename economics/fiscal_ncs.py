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
    for i, amount in enumerate(capex):
        if amount <= 0: continue
        annual = amount / years
        dep[i:min(len(capex), i + years)] += annual
    return dep


def calculate_post_2022_tax(df: pd.DataFrame, regime: FiscalRegime | None = None) -> pd.DataFrame:
    """Calculate a transparent project-level post-2022 NCS tax approximation.

    Excludes financing allocation, norm-price adjustments, company portfolio offsets,
    non-qualifying assets and temporary-rule uplift. Special-tax losses are modelled
    as same-period tax value/refund for analytical neutrality.
    """
    r = regime or FiscalRegime()
    out = df.copy()
    capex = out['capex_mnok'].to_numpy(float)
    dep = _depreciation_schedule(capex, r.ordinary_depreciation_years)
    operating_margin = (out['revenue_mnok'] - out['opex_mnok'] - out['decom_mnok']).to_numpy(float)

    ordinary_base_pre_loss = operating_margin - dep
    ordinary_tax = np.zeros(len(out)); loss_cf = 0.0
    ordinary_loss_cf = np.zeros(len(out))
    ordinary_tax_base = np.zeros(len(out))
    for i, base in enumerate(ordinary_base_pre_loss):
        net = base + loss_cf
        if net >= 0:
            ordinary_tax_base[i] = net
            ordinary_tax[i] = net * r.ordinary_rate
            loss_cf = 0.0
        else:
            ordinary_tax_base[i] = 0.0
            loss_cf = net
        ordinary_loss_cf[i] = loss_cf

    # Special tax: qualifying investment deducted immediately; calculated ordinary
    # company tax is deducted from the special-tax base.
    special_base = operating_margin - capex - ordinary_tax
    special_tax = special_base * r.special_rate  # negative => analytical refund/tax value

    out['ordinary_depreciation_mnok'] = dep
    out['ordinary_tax_base_mnok'] = ordinary_tax_base
    out['ordinary_loss_cf_mnok'] = ordinary_loss_cf
    out['ordinary_tax_mnok'] = ordinary_tax
    out['special_tax_base_mnok'] = special_base
    out['special_tax_mnok'] = special_tax
    out['tax_mnok'] = ordinary_tax + special_tax
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
