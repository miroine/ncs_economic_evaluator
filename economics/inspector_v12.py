from __future__ import annotations

def inspect_period(cf,index=0):
    r=cf.iloc[index]
    oil=float(r.get('oil_mmbbl',0)); op=float(r.get('oil_price_usd_bbl',0)); fx=float(r.get('usd_nok',0)); gas=float(r.get('gas_msm3',0)); gp=float(r.get('gas_price_usd_sm3',0))
    return {'period':r.get('period',r.get('year')),'oil_volume_mmbbl':oil,'oil_price_usd_bbl':op,'usd_nok':fx,
            'oil_revenue_formula_mnok':oil*op*fx,'oil_revenue_reported_mnok':float(r.get('oil_revenue_mnok',0)),
            'gas_volume_msm3':gas,'gas_price_usd_sm3':gp,'gas_revenue_formula_mnok':gas*gp*fx,'gas_revenue_reported_mnok':float(r.get('gas_revenue_mnok',0)),
            'capex_mnok':float(r.get('capex_mnok',0)),'opex_mnok':float(r.get('opex_mnok',0)),'tax_mnok':float(r.get('tax_mnok',0)),
            'after_tax_cf_mnok':float(r.get('after_tax_cf_mnok',0)),'discount_factor':float(r.get('discount_factor',1)),'discounted_cf_mnok':float(r.get('discounted_cf_mnok',0))}
