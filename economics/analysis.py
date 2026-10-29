import numpy as np
import pandas as pd
from .batch import FACTOR_NAMES, npv_cases


def tornado(profile, assumptions, low=0.8, high=1.2, market_deck=None, cutoff=None):
    base = float(npv_cases(profile, assumptions, np.ones((1, 6)), market_deck, cutoff)[0])
    specs = ['Oil price','Gas price','Production','CAPEX','OPEX']
    rows=[]
    for name in specs:
        cases=np.ones((2,6))
        cases[:,FACTOR_NAMES.index(name)]=[low,high]
        vals=npv_cases(profile,assumptions,cases,market_deck,cutoff)
        rows.append({'variable':name,'low_npv':vals[0],'high_npv':vals[1],
                     'low_delta':vals[0]-base,'high_delta':vals[1]-base,
                     'swing':abs(vals[1]-vals[0])})
    return pd.DataFrame(rows).sort_values('swing',ascending=True), base


def sensitivity_curve(profile, assumptions, variable, factors=None, market_deck=None, cutoff=None):
    factors=np.asarray(factors if factors is not None else np.linspace(.6,1.4,17))
    cases=np.ones((len(factors),6))
    cases[:,FACTOR_NAMES.index(variable)]=factors
    values=npv_cases(profile,assumptions,cases,market_deck,cutoff)
    return pd.DataFrame({'factor':factors,'change_pct':(factors-1)*100,'npv_mnok':values})


def npv_waterfall(cf):
    components={
        'Oil revenue': cf['oil_revenue_mnok'].sum(),
        'Gas revenue': cf['gas_revenue_mnok'].sum(),
        'CAPEX': -cf['capex_mnok'].sum(),
        'OPEX': -cf['opex_mnok'].sum(),
        'Decommissioning': -cf['decom_mnok'].sum(),
        'Tax': -cf['tax_mnok'].sum(),
    }
    return components
