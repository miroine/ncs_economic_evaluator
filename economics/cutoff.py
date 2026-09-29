from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass
class CutoffSettings:
    mode: str = 'none'  # none | hard | negative_ocf | economic_limit
    hard_cutoff_year: int | None = None
    consecutive_negative_periods: int = 1
    lookahead_periods: int = 3
    minimum_oil_mmbbl: float = 0.0
    minimum_gas_msm3: float = 0.0
    decom_lag_periods: int = 1
    move_decom: bool = True


def _first_consecutive(mask, n):
    n=max(1,int(n)); run=0
    for i,v in enumerate(mask):
        run=run+1 if bool(v) else 0
        if run>=n: return i-n+1
    return None


def determine_cutoff(df: pd.DataFrame, settings: CutoffSettings):
    if settings is None or settings.mode=='none': return None, 'none'
    years=df['year'].astype(int).to_numpy(); candidates=[]
    if settings.hard_cutoff_year is not None:
        ix=np.where(years>=int(settings.hard_cutoff_year))[0]
        if len(ix): candidates.append((int(ix[0]),'hard cutoff'))
    rate_mask=((df['oil_mmbbl'].to_numpy() < settings.minimum_oil_mmbbl) &
               (df['gas_msm3'].to_numpy() < settings.minimum_gas_msm3))
    if (settings.minimum_oil_mmbbl>0 or settings.minimum_gas_msm3>0):
        ix=np.where(rate_mask)[0]
        if len(ix): candidates.append((int(ix[0]),'minimum production rate'))
    ocf=(df['revenue_mnok']-df['opex_mnok']).to_numpy(float)
    if settings.mode=='negative_ocf':
        ix=_first_consecutive(ocf<0,settings.consecutive_negative_periods)
        if ix is not None: candidates.append((ix,f'{settings.consecutive_negative_periods} consecutive negative operating period(s)'))
    elif settings.mode=='economic_limit':
        horizon=max(1,int(settings.lookahead_periods)); ix=None
        for i in range(len(ocf)):
            # continuation must recover operating losses within the look-ahead window.
            if ocf[i] < 0 and np.sum(ocf[i:min(len(ocf),i+horizon)]) <= 0:
                ix=i; break
        if ix is not None: candidates.append((ix,f'negative incremental operating value over {horizon}-period look-ahead'))
    if not candidates: return None, 'no cutoff triggered'
    return min(candidates,key=lambda x:x[0])


def apply_cutoff(df: pd.DataFrame, settings: CutoffSettings):
    out=df.copy(); ix,reason=determine_cutoff(out,settings)
    out['cutoff_active']=False
    if ix is None:
        out.attrs['cutoff_year']=None; out.attrs['cutoff_reason']=reason; return out
    decom_total=float(out['decom_mnok'].sum())
    out.loc[out.index[ix:],'oil_mmbbl']=0.0; out.loc[out.index[ix:],'gas_msm3']=0.0
    out.loc[out.index[ix:],'opex_mnok']=0.0
    out.loc[out.index[ix:],'oil_revenue_mnok']=0.0; out.loc[out.index[ix:],'gas_revenue_mnok']=0.0; out.loc[out.index[ix:],'revenue_mnok']=0.0
    out.loc[out.index[ix:],'cutoff_active']=True
    if settings.move_decom and decom_total:
        out['decom_mnok']=0.0; target=min(ix+max(0,int(settings.decom_lag_periods)),len(out)-1)
        out.loc[out.index[target],'decom_mnok']=decom_total
    out.attrs['cutoff_year']=int(out.iloc[ix]['year']); out.attrs['cutoff_reason']=reason
    return out
