from __future__ import annotations
import numpy as np
import pandas as pd

def generated_profile(start_year:int, years:int=20, oil_reserves_mmbbl:float=100, oil_plateau_mmbbl:float=12, gas_plateau_msm3:float=250, ramp_years:int=2, plateau_years:int=4, decline_rate:float=.15, capex_mnok:float=12000, opex_mnok:float=600, decom_mnok:float=2000):
    ys=np.arange(start_year,start_year+years); oil=[]; gas=[]
    for i in range(years):
        if i<ramp_years: f=(i+1)/max(ramp_years,1)
        elif i<ramp_years+plateau_years: f=1.0
        else: f=(1-decline_rate)**(i-ramp_years-plateau_years+1)
        oil.append(oil_plateau_mmbbl*f); gas.append(gas_plateau_msm3*f)
    oil=np.asarray(oil); total=oil.sum()
    if total>oil_reserves_mmbbl and total>0: oil*=oil_reserves_mmbbl/total
    cap=np.zeros(years); cap[:min(3,years)]=capex_mnok/ min(3,years)
    op=np.where((np.asarray(oil)>0)|(np.asarray(gas)>0),opex_mnok,0.0); dec=np.zeros(years); dec[-1]=decom_mnok
    return pd.DataFrame({'year':ys,'oil_mmbbl':oil,'gas_msm3':gas,'capex_mnok':cap,'opex_mnok':op,'decom_mnok':dec})
