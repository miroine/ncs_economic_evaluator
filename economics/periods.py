from __future__ import annotations
import numpy as np
import pandas as pd

FREQS={"annual":1,"quarterly":4,"monthly":12}
FLOW_COLUMNS=("oil_mmbbl","gas_msm3","capex_mnok","opex_mnok","decom_mnok")

def expand_profile(profile: pd.DataFrame, frequency: str="annual", capex_phasing: str="even", cost_basis: str="annual_total") -> pd.DataFrame:
    """Expand annual profile rows into periods.

    cost_basis='annual_total' means annual CAPEX/OPEX/decommissioning values are
    annual totals and are allocated across periods.  'per_period' is for a table
    already expressed at the requested frequency and prevents accidental x4/x12
    multiplication when users edit fine-period data directly.
    """
    frequency=frequency.lower(); n=FREQS.get(frequency)
    if n is None: raise ValueError("frequency must be annual, quarterly or monthly")
    if cost_basis not in ("annual_total","per_period"):
        raise ValueError("cost_basis must be annual_total or per_period")
    p=profile.copy().sort_values("year").reset_index(drop=True)
    if n==1:
        p["period"]=p["year"].astype(str); p["periods_per_year"]=1; p["time_years"]=np.arange(len(p),dtype=float)
        p["cost_input_basis"]=cost_basis
        return p
    # A per-period table is already at the desired resolution: add timing metadata only.
    if cost_basis=="per_period":
        out=p.copy(); out["periods_per_year"]=n
        if "period" not in out:
            counts=out.groupby("year").cumcount()+1
            out["period"]=[f"{int(y)}-Q{int(k)}" if n==4 else f"{int(y)}-{int(k):02d}" for y,k in zip(out.year,counts)]
        out["time_years"]=np.arange(len(out),dtype=float)/n; out["cost_input_basis"]="per_period"
        return out
    rows=[]
    for _,r in p.iterrows():
        y=int(r["year"])
        weights=np.arange(n,0,-1,dtype=float) if capex_phasing=="front" else np.ones(n)
        weights=weights/weights.sum()
        for k in range(n):
            d=r.to_dict(); d["periods_per_year"]=n
            d["period"]=f"{y}-Q{k+1}" if n==4 else f"{y}-{k+1:02d}"; d["period_index"]=k+1
            for c in ("oil_mmbbl","gas_msm3","opex_mnok","decom_mnok"):
                if c in d: d[c]=float(r[c])/n
            if "capex_mnok" in d: d["capex_mnok"]=float(r["capex_mnok"])*weights[k]
            d["cost_input_basis"]="annual_total"
            rows.append(d)
    out=pd.DataFrame(rows); out["time_years"]=np.arange(len(out),dtype=float)/n
    return out

def period_year_fraction(df: pd.DataFrame) -> np.ndarray:
    if "time_years" in df: return pd.to_numeric(df["time_years"]).to_numpy(float)
    ppy=int(df["periods_per_year"].iloc[0]) if "periods_per_year" in df and len(df) else 1
    return np.arange(len(df),dtype=float)/max(ppy,1)
