from __future__ import annotations
import numpy as np, pandas as pd

def simulate_schedule_risk(stages, iterations=5000, seed=42, value_per_month_delay_mnok=0.0):
    """Simulate additive stage delays. Stage dict: name, min_months, mode_months, max_months."""
    rng=np.random.default_rng(seed); total=np.zeros(int(iterations)); by={}
    for s in stages:
        x=rng.triangular(float(s['min_months']),float(s['mode_months']),float(s['max_months']),int(iterations))
        by[s['name']]=x; total+=x
    out=pd.DataFrame(by); out['total_delay_months']=total; out['npv_impact_mnok']=-total*float(value_per_month_delay_mnok)
    return out

def schedule_summary(samples):
    x=np.asarray(samples['total_delay_months'],float)
    return {'P10_months':float(np.percentile(x,10)),'P50_months':float(np.percentile(x,50)),'P90_months':float(np.percentile(x,90)),'mean_months':float(x.mean())}
