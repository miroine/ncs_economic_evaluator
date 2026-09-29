from __future__ import annotations
import numpy as np
from .schedule_v12 import validate_schedule
from .uncertainty_register_v12 import validate_register

def validate_model(profile=None, physical=None, schedule=None, register=None, corr=None, fx_deck=None):
    checks=[]
    def add(name,ok,severity='ERROR',detail=''):
        checks.append({'check':name,'status':'PASS' if ok else severity,'detail':detail})
    if profile is not None:
        add('Profile has unique periods',not profile['year'].duplicated().any() if 'period' not in profile else not profile['period'].duplicated().any())
        for c in ['oil_mmbbl','gas_msm3','capex_mnok','opex_mnok','decom_mnok']:
            if c in profile: add(f'{c} non-negative',bool((profile[c]>=0).all()))
    if physical is not None:
        add('Oil resource balance',bool((physical['remaining_oil_mmbbl']>=-1e-9).all()))
        add('Oil <= well capacity',bool((physical['oil_mmbbl']<=physical['well_oil_capacity_mmbbl']+1e-9).all()))
        add('Oil <= facility capacity',bool((physical['oil_mmbbl']<=physical['facility_oil_capacity_mmbbl']+1e-9).all()))
    if schedule is not None:
        issues=validate_schedule(schedule); add('Schedule dependencies',not issues,detail='; '.join(issues))
    if register is not None:
        issues=validate_register(register,corr); add('Uncertainty register',not issues,detail='; '.join(issues))
    if fx_deck is not None:
        add('FX rates positive',bool((fx_deck[['USD','EUR','GBP']]>0).all().all()))
    return checks

def has_errors(checks): return any(x['status']=='ERROR' for x in checks)
