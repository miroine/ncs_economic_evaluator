from __future__ import annotations
import numpy as np, pandas as pd
from .conventions import BOE_PER_SM3_GAS, pandas as pd

def _basis_factor(basis, wi):
    if basis not in ("gross_field","net_company"):
        raise ValueError("basis must be gross_field or net_company")
    return wi if basis=="gross_field" else np.ones_like(wi,dtype=float)

def apply_commercial_terms(cf, tariff_nok_boe=0.0, transport_mnok=0.0, host_capacity_mboe=None, third_party_income_mnok=0.0, working_interest=None, commercial_basis="gross_field", base_cf_basis="gross_field"):
    """Apply commercial adjustments with explicit gross-field/net-company semantics.

    commercial_basis controls tariffs, transport and third-party income.
    base_cf_basis controls whether the incoming after/pre-tax CF is 100% field or
    already net to the company.  This prevents double ownership scaling.
    """
    out=cf.copy(); oil=np.asarray(out.get("oil_mmbbl",0),float); gas=np.asarray(out.get("gas_msm3",0),float)
    boe=oil*1e6 + gas*1e6*BOE_PER_SM3_GAS
    if host_capacity_mboe is not None:
        cap=float(host_capacity_mboe)*1e3
        scale=np.minimum(1.0,np.divide(cap,boe,out=np.ones_like(boe,dtype=float),where=boe>0))
        for col in ("oil_mmbbl","gas_msm3","oil_revenue_mnok","gas_revenue_mnok","revenue_mnok"):
            if col in out: out[col]=np.asarray(out[col],float)*scale
        boe=boe*scale
    gross_tariff=boe*float(tariff_nok_boe)/1e6 + float(transport_mnok)
    gross_income=np.full(len(out),float(third_party_income_mnok))
    wi=np.ones(len(out)) if working_interest is None else np.broadcast_to(np.asarray(working_interest,float),len(out)).astype(float)
    if np.any((wi<0)|(wi>1)): raise ValueError("working_interest must be between 0 and 1")
    out["working_interest"]=wi; out["commercial_basis"]=commercial_basis; out["base_cf_basis"]=base_cf_basis
    factor=_basis_factor(commercial_basis,wi)
    out["tariff_mnok"]=gross_tariff*factor
    out["third_party_income_mnok"]=gross_income*factor
    base=np.asarray(out.get("after_tax_cf_mnok",out.get("pre_tax_cf_mnok",0)),float)
    company_base=base*_basis_factor(base_cf_basis,wi)
    out["commercial_cf_mnok"]=company_base-out["tariff_mnok"]+out["third_party_income_mnok"]
    return out

def phased_costs(periods, categories):
    """Create category CAPEX schedule; each category has total, weights and escalation."""
    n=len(periods); data={"period":list(periods)}
    for c in categories:
        w=np.asarray(c.get("weights",[1/n]*n),float)
        if len(w)!=n or w.sum()<=0: raise ValueError("Cost weights must match periods and sum positive")
        w=w/w.sum(); esc=float(c.get("escalation",0)); data[c["name"]]=float(c["total_mnok"])*w*(1+esc)**np.arange(n)
    df=pd.DataFrame(data); df["total_capex_mnok"]=df.drop(columns="period").sum(axis=1) if categories else 0.0
    return df
