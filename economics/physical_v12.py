from __future__ import annotations
from dataclasses import dataclass
import calendar
import numpy as np, pandas as pd

@dataclass
class ResourceCase:
    stoiip_mmbbl: float
    oil_recovery_factor: float
    giip_bsm3: float = 0.0
    gas_recovery_factor: float = 0.0

@dataclass
class FacilityLimits:
    oil_kbopd: float = 1e9
    gas_msm3_day: float = 1e9
    uptime: float = 1.0


def recoverable_resources(case: ResourceCase):
    if case.stoiip_mmbbl < 0 or case.giip_bsm3 < 0: raise ValueError('In-place volumes cannot be negative')
    if not 0 <= case.oil_recovery_factor <= 1 or not 0 <= case.gas_recovery_factor <= 1: raise ValueError('Recovery factors must be 0..1')
    return {'oil_mmbbl': case.stoiip_mmbbl*case.oil_recovery_factor,
            'gas_msm3': case.giip_bsm3*1000*case.gas_recovery_factor}


def _period_frame(periods):
    """Return year, period label and actual/fallback days for each model row."""
    if isinstance(periods, pd.DataFrame):
        p=periods.copy().reset_index(drop=True)
        if 'year' not in p: raise ValueError('period table requires year')
    else:
        p=pd.DataFrame({'year':np.asarray(periods,int)})
    p['year']=pd.to_numeric(p['year']).astype(int)
    if 'periods_per_year' in p:
        ppy=pd.to_numeric(p['periods_per_year'],errors='coerce').fillna(1).astype(int).clip(lower=1)
    else:
        counts=p.groupby('year')['year'].transform('size')
        ppy=counts.clip(lower=1).astype(int)
    days=[]
    for i,r in p.iterrows():
        y=int(r['year']); n=int(ppy.iloc[i]); label=str(r.get('period',''))
        if n==12:
            try: month=int(label.rsplit('-',1)[-1]); days.append(float(calendar.monthrange(y,month)[1])); continue
            except Exception: pass
        if n==4:
            try:
                q=int(label.upper().rsplit('Q',1)[-1]);
                days.append(float(sum(calendar.monthrange(y,m)[1] for m in range((q-1)*3+1,q*3+1)))); continue
            except Exception: pass
        if n==1: days.append(float(366 if calendar.isleap(y) else 365))
        else: days.append((366.0 if calendar.isleap(y) else 365.0)/n)
    p['_days']=days; p['_ppy']=ppy.to_numpy()
    return p


def integrated_profile(periods, case: ResourceCase, wells, facility: FacilityLimits, reservoir_oil_mmbbl=None, reservoir_gas_msm3=None):
    """Generate a resource-capped production profile.

    Daily well/facility rates are converted with each row's actual period days,
    so annual, quarterly and monthly models remain dimensionally consistent.
    """
    cal=_period_frame(periods); years=cal['year'].to_numpy(int); days=cal['_days'].to_numpy(float); n=len(cal)
    rec=recoverable_resources(case)
    if not 0 < facility.uptime <= 1: raise ValueError('Facility uptime must be >0 and <=1')
    well_oil=np.zeros(n); well_gas=np.zeros(n)
    for w in wells:
        y=int(w['onstream_year'])
        # Optional onstream_month makes monthly/quarterly activation more precise.
        om=int(w.get('onstream_month',1))
        active=years>y
        same=years==y
        if same.any():
            labels=cal.get('period',pd.Series(['']*n)).astype(str)
            months=[]
            for lab,ppy in zip(labels,cal['_ppy']):
                try:
                    months.append(int(lab.rsplit('-',1)[-1]) if ppy==12 else (int(lab.upper().rsplit('Q',1)[-1])-1)*3+1 if ppy==4 else 1)
                except Exception: months.append(1)
            active |= same & (np.asarray(months)>=om)
        well_oil[active]+=float(w.get('oil_kbopd',0))*days[active]/1000*facility.uptime
        well_gas[active]+=float(w.get('gas_msm3_day',0))*days[active]*facility.uptime
    ro=np.full(n,np.inf) if reservoir_oil_mmbbl is None else np.broadcast_to(np.asarray(reservoir_oil_mmbbl,float),n)
    rg=np.full(n,np.inf) if reservoir_gas_msm3 is None else np.broadcast_to(np.asarray(reservoir_gas_msm3,float),n)
    fac_o=float(facility.oil_kbopd)*days/1000*facility.uptime
    fac_g=float(facility.gas_msm3_day)*days*facility.uptime
    oil=np.minimum.reduce([ro,well_oil,fac_o]); gas=np.minimum.reduce([rg,well_gas,fac_g])
    for arr,total in ((oil,rec['oil_mmbbl']),(gas,rec['gas_msm3'])):
        remaining=total
        for i in range(n):
            arr[i]=max(0,min(arr[i],remaining)); remaining-=arr[i]
    out=pd.DataFrame({'year':years,'period_days':days,'reservoir_oil_mmbbl':ro,'well_oil_capacity_mmbbl':well_oil,'facility_oil_capacity_mmbbl':fac_o,'oil_mmbbl':oil,
                      'reservoir_gas_msm3':rg,'well_gas_capacity_msm3':well_gas,'facility_gas_capacity_msm3':fac_g,'gas_msm3':gas})
    if 'period' in cal: out.insert(1,'period',cal['period'].to_numpy())
    out['cumulative_oil_mmbbl']=out.oil_mmbbl.cumsum(); out['remaining_oil_mmbbl']=np.maximum(0,rec['oil_mmbbl']-out.cumulative_oil_mmbbl)
    out['cumulative_gas_msm3']=out.gas_msm3.cumsum(); out['remaining_gas_msm3']=np.maximum(0,rec['gas_msm3']-out.cumulative_gas_msm3)
    return out
