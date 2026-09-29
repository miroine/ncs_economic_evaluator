from __future__ import annotations
import numpy as np
import pandas as pd

def diagnostics(npvs, factors:pd.DataFrame|None=None):
    x=np.asarray(npvs,float); q=np.percentile(x,[5,10,50,90,95])
    out={'P5':q[0],'P10':q[1],'P50':q[2],'P90':q[3],'P95':q[4],'mean':x.mean(),'std':x.std(),'prob_negative':float(np.mean(x<0)),'downside_p10_mean':float(x[x<=q[1]].mean()) if np.any(x<=q[1]) else q[1]}
    corr=None
    if factors is not None and len(factors)==len(x):
        z=factors.copy(); z['npv_mnok']=x; corr=z.corr(numeric_only=True)['npv_mnok'].drop('npv_mnok').sort_values(key=lambda s:s.abs(),ascending=False)
    return out,corr
