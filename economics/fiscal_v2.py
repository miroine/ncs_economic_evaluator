from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .fiscal_ncs import _depreciation_schedule

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
    dep=_depreciation_schedule(capex,max(1,s.depreciation_years))
    tariffs=annual.get('tariff_mnok',pd.Series(np.zeros(n),index=annual.index)).to_numpy(float)
    decom=annual.decom_mnok.to_numpy(float) if s.abandonment_deductible else np.zeros(n)
    margin=annual.revenue_mnok.to_numpy(float)-annual.opex_mnok.to_numpy(float)-decom-(tariffs if s.tariff_deductible else 0)
    ordinary_tax=np.zeros(n); ordinary_base=np.zeros(n); loss_cf=np.zeros(n); loss=0.
    for i,b in enumerate(margin-dep):
        loss*=1+s.ordinary_loss_interest
        net=b+loss
        if net>0: ordinary_base[i]=net; ordinary_tax[i]=net*s.ordinary_rate; loss=0.
        else: loss=net
        loss_cf[i]=loss
    special_base=margin-capex-ordinary_tax
    special_tax=special_base*s.special_rate if s.special_loss_refund else np.maximum(special_base,0)*s.special_rate
    result=annual[['year']].copy()
    result['ordinary_depreciation_mnok']=dep; result['ordinary_tax_base_mnok']=ordinary_base; result['ordinary_loss_cf_mnok']=loss_cf
    result['ordinary_tax_mnok']=ordinary_tax; result['special_tax_base_mnok']=special_base; result['special_tax_mnok']=special_tax; result['tax_mnok']=ordinary_tax+special_tax
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
    for c in cols: out[c]=0.0
    # Book annual tax ledger in the last period of each year; cumulative loss is a balance.
    for _,row in ledger.iterrows():
        idx=out.index[out['year'].astype(int)==int(row.year)]
        if len(idx):
            last=idx[-1]
            for c in cols: out.loc[last,c]=float(row[c])
    out.attrs['fiscal_time_basis']='annual tax approximation; allocated to final model period of each calendar year'
    return out


def government_take(df):
    tax=float(df.get('tax_mnok',pd.Series(dtype=float)).sum()); pretax=float(df.pre_tax_cf_mnok.sum())
    denom=pretax+tax
    return tax/denom if denom>0 else np.nan
