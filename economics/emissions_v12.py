from __future__ import annotations
import numpy as np, pandas as pd
from .conventions import BOE_PER_SM3_GAS

def emissions_economics(profile, kg_co2_per_boe, carbon_price_nok_tonne=0.0, electrification_reduction=0.0):
    if kg_co2_per_boe<0 or carbon_price_nok_tonne<0 or not 0<=electrification_reduction<=1: raise ValueError('Invalid emissions assumption')
    out=profile.copy(); boe=out['oil_mmbbl'].to_numpy(float)*1e6 + out['gas_msm3'].to_numpy(float)*1e6*BOE_PER_SM3_GAS
    tonnes=boe*kg_co2_per_boe/1000*(1-electrification_reduction)
    out['co2_tonnes']=tonnes; out['co2_kg_per_boe']=kg_co2_per_boe*(1-electrification_reduction); out['carbon_cost_mnok']=tonnes*carbon_price_nok_tonne/1e6
    return out
