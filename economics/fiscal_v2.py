from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .fiscal_ncs import tax_ledger_arrays

@dataclass
class FiscalV2Settings:
    ordinary_rate:float=.22
    special_rate:float=.718
    depreciation_years:int=6
    ordinary_loss_interest:float=0.0
    special_loss_refund:bool=True
    abandonment_deductible:bool=True
    tariff_deductible:bool=True
    vintage:str='post_2022'


def _annual_ledger(annual: pd.DataFrame, s: FiscalV2Settings) -> pd.DataFrame:
    """Annual analytical NCS tax ledger. Subannual cash flows are aggregated here."""
    n=len(annual)
    capex=annual.capex_mnok.to_numpy(float)
    tariffs=annual.get('tariff_mnok',pd.Series(np.zeros(n),index=annual.index)).to_numpy(float)
    decom=annual.decom_mnok.to_numpy(float) if s.abandonment_deductible else np.zeros(n)
    result=annual[['year']].copy()
    ledger=tax_ledger_arrays(
        annual.revenue_mnok.to_numpy(float),
        annual.opex_mnok.to_numpy(float)+(tariffs if s.tariff_deductible else 0),
        capex, decom, s.ordinary_rate, s.special_rate, max(1,s.depreciation_years),
        s.ordinary_loss_interest, s.special_loss_refund,
    )
    for column,values in ledger.items(): result[column]=values
    return result


def calculate_fiscal_v2(df:pd.DataFrame, settings:FiscalV2Settings|None=None):
    """Calculate project-level NCS fiscal approximation on an annual tax basis.

    For quarterly/monthly economics, taxable items are aggregated by calendar year,
    the annual ledger is calculated, and annual tax is allocated back to the final
    model period of each year. This preserves annual tax totals and avoids treating
    subannual periods as independent statutory tax years.
    """
    s=settings or FiscalV2Settings(); out=df.copy(); n=len(out)
    if not n: return out
    needed=['revenue_mnok','opex_mnok','capex_mnok','decom_mnok']
    tmp=out.copy(); tmp['_tax_year']=tmp['year'].astype(int)
    annual=tmp.groupby('_tax_year',as_index=False)[needed].sum().rename(columns={'_tax_year':'year'})
    if 'tariff_mnok' in out:
        annual['tariff_mnok']=tmp.groupby('_tax_year')['tariff_mnok'].sum().reindex(annual['year']).to_numpy()
    ledger=_annual_ledger(annual,s)
    cols=[c for c in ledger.columns if c!='year']
    values=np.zeros((n,len(cols)))
    last_positions=np.flatnonzero(~tmp['_tax_year'].duplicated(keep='last').to_numpy())
    annual_positions=pd.Index(ledger['year']).get_indexer(tmp['_tax_year'].iloc[last_positions])
    values[last_positions]=ledger[cols].to_numpy(float)[annual_positions]
    out[cols]=values
    out.attrs['fiscal_time_basis']='annual tax approximation; allocated to final model period of each calendar year'
    return out


def government_take(df):
    tax=float(df.get('tax_mnok',pd.Series(dtype=float)).sum()); pretax=float(df.pre_tax_cf_mnok.sum())
    denom=pretax+tax
    return tax/denom if denom>0 else np.nan
