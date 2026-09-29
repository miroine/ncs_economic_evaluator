from __future__ import annotations
import numpy as np
import pandas as pd

def reserves_profile(start_year:int, stoiip_mmbbl:float, recovery_factor:float, plateau_mmbbl:float, decline_rate:float=.15, ramp_years:int=2, plateau_years:int=4, life:int=30, gas_oil_ratio_msm3_per_mmbbl:float=20.0, uptime:float=.95, facility_capacity_mmbbl:float|None=None):
    recoverable=max(0.,float(stoiip_mmbbl)*float(recovery_factor)); cap=facility_capacity_mmbbl or plateau_mmbbl
    rates=[]
    for i in range(life):
        if i<ramp_years: q=plateau_mmbbl*(i+1)/max(ramp_years,1)
        elif i<ramp_years+plateau_years: q=plateau_mmbbl
        else: q=plateau_mmbbl*(1-decline_rate)**(i-ramp_years-plateau_years+1)
        rates.append(min(q*uptime,cap))
    rates=np.asarray(rates,float); cum=np.cumsum(rates); over=cum>recoverable
    if over.any():
        i=int(np.argmax(over)); before=cum[i-1] if i else 0.; rates[i]=max(0.,recoverable-before); rates[i+1:]=0
    gas=rates*gas_oil_ratio_msm3_per_mmbbl
    return pd.DataFrame({'year':np.arange(start_year,start_year+life),'oil_mmbbl':rates,'gas_msm3':gas,'cumulative_oil_mmbbl':np.cumsum(rates),'recoverable_oil_mmbbl':recoverable})
