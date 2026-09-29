from __future__ import annotations
import pandas as pd, numpy as np


def _months(v): return float(v)

def _normalized(a):
    """Normalize activity to calendar months on an arbitrary month-zero axis.

    V12.1 preferred fields: start_month, duration_months, delay_*_months.
    Legacy V12 start/end decimal-year fields remain readable and are converted
    to months, preserving old projects without ambiguous new inputs.
    """
    x=dict(a)
    if 'start_month' in x:
        start=_months(x['start_month'])
        dur=_months(x.get('duration_months',0))
    else:
        start=float(x['start'])*12.0
        dur=(float(x['end'])-float(x['start']))*12.0
    return {**x,'_start_month':start,'_duration_months':dur,
            '_delay_low_months':float(x.get('delay_low_months',float(x.get('delay_low',0))*12.0)),
            '_delay_mode_months':float(x.get('delay_mode_months',float(x.get('delay_mode',0))*12.0)),
            '_delay_high_months':float(x.get('delay_high_months',float(x.get('delay_high',0))*12.0))}


def validate_schedule(activities):
    aa=[_normalized(a) for a in activities]; by={a['name']:a for a in aa}; issues=[]
    for a in aa:
        if a['_duration_months'] < 0: issues.append(f"{a['name']}: duration cannot be negative")
        for dep in a.get('depends_on',[]):
            if dep not in by: issues.append(f"{a['name']}: missing dependency {dep}")
            elif a['_start_month'] < by[dep]['_start_month']+by[dep]['_duration_months']: issues.append(f"{a['name']}: starts before {dep} ends")
    return issues


def simulate_schedule(activities,n=1000,seed=42):
    issues=validate_schedule(activities)
    if issues: raise ValueError('; '.join(issues))
    aa=[_normalized(a) for a in activities]; rng=np.random.default_rng(seed); rows=[]
    baseline=max((a['_start_month']+a['_duration_months'] for a in aa),default=np.nan)
    for k in range(n):
        ends={}; starts={}
        for a in aa:
            hi=a['_delay_high_months']; lo=a['_delay_low_months']; mode=a['_delay_mode_months']
            delay=rng.triangular(lo,mode,hi) if hi>0 else 0.0
            base=a['_start_month']; dep=max([ends[d] for d in a.get('depends_on',[])],default=base)
            s=max(base,dep)+delay; starts[a['name']]=s; ends[a['name']]=s+a['_duration_months']
        completion=max(ends.values()) if ends else np.nan
        rows.append({'simulation':k,'completion_month':completion,'first_oil':completion/12.0 if np.isfinite(completion) else np.nan,
                     'total_delay_months':completion-baseline if ends else 0.0,'total_delay_years':(completion-baseline)/12.0 if ends else 0.0})
    return pd.DataFrame(rows)
