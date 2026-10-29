from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
import pandas as pd
from .conventions import BOE_PER_SM3_GAS
from .reserves import reserves_profile

FIELD_TYPES = ('Oil with associated gas', 'Dry gas', 'Gas with condensate', 'Independent oil and gas')


@dataclass
class FieldProfileSettings:
    field_type: str = 'Oil with associated gas'
    start_year: int = 2027
    development_years: int = 2
    production_years: int = 20
    oil_resources_mmbbl: float = 100.
    gas_resources_msm3: float = 2000.
    oil_plateau_mmbbl: float = 12.
    gas_plateau_msm3: float = 250.
    oil_recovery_factor: float = 1.
    gas_recovery_factor: float = 1.
    oil_ramp_years: int = 2
    gas_ramp_years: int = 2
    oil_plateau_years: int = 4
    gas_plateau_years: int = 4
    oil_decline_rate: float = .15
    gas_decline_rate: float = .15
    uptime: float = .95
    associated_gas_msm3_per_mmbbl: float = 20.
    condensate_mmbbl_per_msm3: float = .002
    capex_mnok: float = 12000.
    annual_opex_mnok: float = 600.
    variable_opex_nok_boe: float = 0.
    decom_mnok: float = 2000.
    decom_lag_years: int = 1


def field_profile(settings: FieldProfileSettings) -> pd.DataFrame:
    """Annual sales-volume screening profile, bounded by recoverable resources.

    Linked fluids share the primary-fluid shape and stop together when either
    recoverable resource cap is reached. Condensate is booked as oil-equivalent
    liquid volume and priced with the model's oil price.
    """
    s = settings
    if s.field_type not in FIELD_TYPES:
        raise ValueError('Choose a supported field type')
    for name in ('start_year', 'development_years', 'production_years', 'oil_ramp_years',
                 'gas_ramp_years', 'oil_plateau_years', 'gas_plateau_years', 'decom_lag_years'):
        value = getattr(s, name)
        if not math.isfinite(value) or int(value) != value:
            raise ValueError(f'{name} must be a whole number')
        minimum = 1 if name in ('start_year', 'production_years') else 0
        if value < minimum:
            raise ValueError(f'{name} must be at least {minimum}')
    for name in ('oil_resources_mmbbl', 'gas_resources_msm3', 'oil_plateau_mmbbl',
                 'gas_plateau_msm3', 'associated_gas_msm3_per_mmbbl',
                 'condensate_mmbbl_per_msm3', 'capex_mnok', 'annual_opex_mnok',
                 'variable_opex_nok_boe', 'decom_mnok'):
        if not math.isfinite(getattr(s, name)) or getattr(s, name) < 0:
            raise ValueError(f'{name} must be finite and non-negative')
    for name in ('oil_recovery_factor', 'gas_recovery_factor', 'oil_decline_rate', 'gas_decline_rate', 'uptime'):
        if not math.isfinite(getattr(s, name)) or not 0 <= getattr(s, name) <= 1:
            raise ValueError(f'{name} must be between 0 and 1')
    if s.uptime == 0:
        raise ValueError('Uptime must be greater than zero')
    oil_resource = s.oil_resources_mmbbl * s.oil_recovery_factor
    gas_resource = s.gas_resources_msm3 * s.gas_recovery_factor
    if s.field_type == 'Dry gas':
        oil_resource = 0.
    required = ('gas',) if s.field_type in ('Dry gas', 'Gas with condensate') else ('oil',)
    if s.field_type == 'Independent oil and gas':
        required = ('oil', 'gas')
    for fluid in required:
        resource = oil_resource if fluid == 'oil' else gas_resource
        plateau = s.oil_plateau_mmbbl if fluid == 'oil' else s.gas_plateau_msm3
        if resource <= 0 or plateau <= 0:
            raise ValueError(f'{fluid.title()} requires positive recoverable resources and plateau rate')

    first_production = s.start_year + s.development_years

    def rates(resource, plateau, ramp, flat, decline):
        # Reuse the resource-capped ramp/plateau/decline convention. The helper is
        # dimensionless apart from column names, so it also supplies the gas shape.
        return reserves_profile(
            first_production, resource, 1., plateau, decline, ramp, flat,
            s.production_years, gas_oil_ratio_msm3_per_mmbbl=0., uptime=s.uptime,
        )['oil_mmbbl'].to_numpy()

    oil = np.zeros(s.production_years)
    gas = np.zeros(s.production_years)
    if s.field_type == 'Oil with associated gas':
        ratio = s.associated_gas_msm3_per_mmbbl
        if ratio > 0:
            oil_resource = min(oil_resource, gas_resource / ratio)
        oil = rates(oil_resource, s.oil_plateau_mmbbl, s.oil_ramp_years, s.oil_plateau_years, s.oil_decline_rate)
        gas = oil * ratio
    elif s.field_type in ('Dry gas', 'Gas with condensate'):
        ratio = s.condensate_mmbbl_per_msm3 if s.field_type == 'Gas with condensate' else 0.
        if ratio > 0:
            gas_resource = min(gas_resource, oil_resource / ratio)
        gas = rates(gas_resource, s.gas_plateau_msm3, s.gas_ramp_years, s.gas_plateau_years, s.gas_decline_rate)
        oil = gas * ratio
    else:
        oil = rates(oil_resource, s.oil_plateau_mmbbl, s.oil_ramp_years, s.oil_plateau_years, s.oil_decline_rate)
        gas = rates(gas_resource, s.gas_plateau_msm3, s.gas_ramp_years, s.gas_plateau_years, s.gas_decline_rate)
    producing = (oil > 0) | (gas > 0)
    if not producing.any():
        raise ValueError('The selected resources and fluid ratio produce no sales volumes')
    last_production = s.development_years + int(np.flatnonzero(producing)[-1])
    decom_index = last_production + s.decom_lag_years
    n = max(s.development_years + s.production_years, decom_index + 1)
    out = pd.DataFrame({
        'year': np.arange(s.start_year, s.start_year + n),
        'oil_mmbbl': np.zeros(n), 'gas_msm3': np.zeros(n),
        'capex_mnok': np.zeros(n), 'opex_mnok': np.zeros(n), 'decom_mnok': np.zeros(n),
    })
    production_slice = slice(s.development_years, s.development_years + s.production_years)
    out.loc[out.index[production_slice], 'oil_mmbbl'] = oil
    out.loc[out.index[production_slice], 'gas_msm3'] = gas
    capex_periods = max(1, s.development_years)
    out.loc[:capex_periods - 1, 'capex_mnok'] = s.capex_mnok / capex_periods
    boe = out.oil_mmbbl + out.gas_msm3 * BOE_PER_SM3_GAS
    out['opex_mnok'] = np.where(boe > 0, s.annual_opex_mnok, 0.) + boe * s.variable_opex_nok_boe
    out.loc[decom_index, 'decom_mnok'] = s.decom_mnok
    out.attrs['first_production_year'] = first_production
    out.attrs['last_production_year'] = s.start_year + last_production
    out.attrs['decommissioning_year'] = s.start_year + decom_index
    return out

def generated_profile(start_year:int, years:int=20, oil_reserves_mmbbl:float=100, oil_plateau_mmbbl:float=12, gas_plateau_msm3:float=250, ramp_years:int=2, plateau_years:int=4, decline_rate:float=.15, capex_mnok:float=12000, opex_mnok:float=600, decom_mnok:float=2000):
    ys=np.arange(start_year,start_year+years); oil=[]; gas=[]
    for i in range(years):
        if i<ramp_years: f=(i+1)/max(ramp_years,1)
        elif i<ramp_years+plateau_years: f=1.0
        else: f=(1-decline_rate)**(i-ramp_years-plateau_years+1)
        oil.append(oil_plateau_mmbbl*f); gas.append(gas_plateau_msm3*f)
    oil=np.asarray(oil); total=oil.sum()
    if total>oil_reserves_mmbbl and total>0: oil*=oil_reserves_mmbbl/total
    cap=np.zeros(years); cap[:min(3,years)]=capex_mnok/ min(3,years)
    op=np.where((np.asarray(oil)>0)|(np.asarray(gas)>0),opex_mnok,0.0); dec=np.zeros(years); dec[-1]=decom_mnok
    return pd.DataFrame({'year':ys,'oil_mmbbl':oil,'gas_msm3':gas,'capex_mnok':cap,'opex_mnok':op,'decom_mnok':dec})
