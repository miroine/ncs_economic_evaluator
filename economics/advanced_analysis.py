from __future__ import annotations
from dataclasses import replace
import copy
import io
import numpy as np
import pandas as pd
from .engine import calculate_cashflow, metrics

VARIABLES=('Oil price','Gas price','Production','CAPEX','OPEX','FX')

def _case(profile,a,variable,factor,market_deck=None,cutoff=None):
    p=profile.copy(); aa=copy.deepcopy(a); deck=None if market_deck is None else market_deck.copy()
    if variable=='Oil price':
        if deck is None: aa.oil_price_usd_bbl*=factor
        else: deck['oil_usd_bbl']*=factor
    elif variable=='Gas price':
        if deck is None: aa.gas_price_usd_sm3*=factor
        else: deck['gas_usd_sm3']*=factor
    elif variable=='FX':
        if deck is None: aa.usd_nok*=factor
        else: deck['usd_nok']*=factor
    elif variable=='Production': p[['oil_mmbbl','gas_msm3']]*=factor
    elif variable=='CAPEX': p['capex_mnok']*=factor
    elif variable=='OPEX': p['opex_mnok']*=factor
    return metrics(calculate_cashflow(p,aa,deck,cutoff))['npv_mnok']


def spider(profile,a,market_deck=None,variables=VARIABLES,changes=(-40,-30,-20,-10,0,10,20,30,40),cutoff=None):
    rows=[]
    for v in variables:
        for pct in changes: rows.append({'variable':v,'change_pct':pct,'npv_mnok':_case(profile,a,v,1+pct/100,market_deck,cutoff)})
    return pd.DataFrame(rows)


def breakeven_factor(profile,a,variable,market_deck=None,low=0.05,high=5.0,iterations=70,cutoff=None):
    f0=_case(profile,a,variable,low,market_deck,cutoff); f1=_case(profile,a,variable,high,market_deck,cutoff)
    if f0==0: return low
    if f1==0: return high
    if f0*f1>0: return None
    lo,hi=low,high
    for _ in range(iterations):
        mid=(lo+hi)/2; fm=_case(profile,a,variable,mid,market_deck,cutoff)
        if (f0<=0<=fm) or (f0>=0>=fm): hi=mid
        else: lo=mid; f0=fm
    return (lo+hi)/2

def breakeven_table(profile,a,market_deck=None,cutoff=None):
    rows=[]
    for v in VARIABLES:
        b=breakeven_factor(profile,a,v,market_deck,cutoff=cutoff)
        rows.append({'variable':v,'breakeven_factor':b,'breakeven_change_pct':None if b is None else (b-1)*100})
    return pd.DataFrame(rows)

def exceedance_curve(values):
    x=np.sort(np.asarray(values,float)); n=len(x)
    return pd.DataFrame({'npv_mnok':x,'exceedance_pct':100*(1-(np.arange(1,n+1)-.5)/n)})

def tax_bridge(cf):
    cols=[]
    for key,label in [('pre_tax_cf_mnok','Pre-tax cash flow'),('ordinary_tax_mnok','Ordinary tax'),('special_tax_mnok','Special tax')]:
        if key in cf: cols.append({'component':label,'value_mnok':float(cf[key].sum()) if key=='pre_tax_cf_mnok' else -float(cf[key].sum())})
    if len(cols)==1 and 'tax_mnok' in cf: cols.append({'component':'Tax','value_mnok':-float(cf['tax_mnok'].sum())})
    cols.append({'component':'After-tax cash flow','value_mnok':float(cf['after_tax_cf_mnok'].sum())})
    return pd.DataFrame(cols)

def excel_workbook(assumptions, profile, cashflow, market_deck, scenarios=None, monte_carlo=None, metadata=None):
    buf=io.BytesIO()
    with pd.ExcelWriter(buf,engine='openpyxl') as xw:
        pd.DataFrame([assumptions.__dict__]).to_excel(xw,sheet_name='Assumptions',index=False)
        profile.to_excel(xw,sheet_name='Profile',index=False); cashflow.to_excel(xw,sheet_name='Cash Flow',index=False)
        market_deck.to_excel(xw,sheet_name='Market Deck',index=False)
        if scenarios is not None: scenarios.to_excel(xw,sheet_name='Scenarios',index=False)
        if monte_carlo is not None: pd.DataFrame({'npv_mnok':np.asarray(monte_carlo)}).to_excel(xw,sheet_name='Monte Carlo',index=False)
        if metadata: pd.DataFrame([metadata]).to_excel(xw,sheet_name='Metadata',index=False)
    return buf.getvalue()

def breakeven_suite(profile,a,market_deck=None,cutoff=None):
    variables=('Oil price','Gas price','Production','CAPEX','OPEX','FX')
    rows=[]
    for v in variables:
        def val(f):
            p=profile.copy(); aa=copy.deepcopy(a); deck=None if market_deck is None else market_deck.copy()
            if v=='Oil price': (setattr(aa,'oil_price_usd_bbl',aa.oil_price_usd_bbl*f) if deck is None else deck.__setitem__('oil_usd_bbl',deck['oil_usd_bbl']*f))
            elif v=='Gas price': (setattr(aa,'gas_price_usd_sm3',aa.gas_price_usd_sm3*f) if deck is None else deck.__setitem__('gas_usd_sm3',deck['gas_usd_sm3']*f))
            elif v=='FX': (setattr(aa,'usd_nok',aa.usd_nok*f) if deck is None else deck.__setitem__('usd_nok',deck['usd_nok']*f))
            elif v=='Production': p[['oil_mmbbl','gas_msm3']]*=f
            elif v=='CAPEX': p['capex_mnok']*=f
            elif v=='OPEX': p['opex_mnok']*=f
            return metrics(calculate_cashflow(p,aa,deck,cutoff))['npv_mnok']
        lo,hi=.02,6.; flo,fhi=val(lo),val(hi); b=None
        if flo==0: b=lo
        elif fhi==0: b=hi
        elif flo*fhi<0:
            for _ in range(70):
                mid=(lo+hi)/2; fm=val(mid)
                if flo*fm<=0: hi=mid; fhi=fm
                else: lo=mid; flo=fm
            b=(lo+hi)/2
        rows.append({'variable':v,'breakeven_factor':b,'breakeven_change_pct':None if b is None else (b-1)*100})
    return pd.DataFrame(rows)

def extended_breakeven_suite(profile,a,market_deck=None,cutoff=None):
    """Broader V10 breakevens. Multipliers are used except start delay (years) and discount rate (%)."""
    base=breakeven_suite(profile,a,market_deck,cutoff)
    rows=base.to_dict('records')
    # Latest start delay that retains non-negative NPV.
    last=None
    for delay in range(0,21):
        p=profile.copy(); p['year']=p['year'].astype(int)+delay
        v=metrics(calculate_cashflow(p,a,market_deck,cutoff))['npv_mnok']
        if v>=0: last=delay
        else: break
    rows.append({'variable':'Start delay','breakeven_factor':last,'breakeven_change_pct':None,'unit':'years'})
    # Discount-rate crossing in absolute annual rate.
    lo,hi=0.,.50; flo=None; root=None
    for _ in range(70):
        mid=(lo+hi)/2; aa=copy.deepcopy(a); aa.discount_rate=mid
        fm=metrics(calculate_cashflow(profile,aa,market_deck,cutoff))['npv_mnok']
        if flo is None:
            aa0=copy.deepcopy(a); aa0.discount_rate=lo; flo=metrics(calculate_cashflow(profile,aa0,market_deck,cutoff))['npv_mnok']
        if flo*fm<=0: hi=mid; root=(lo+hi)/2
        else: lo=mid; flo=fm
    rows.append({'variable':'Discount rate','breakeven_factor':root,'breakeven_change_pct':None,'unit':'annual rate'})
    return pd.DataFrame(rows)
