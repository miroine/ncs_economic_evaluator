from dataclasses import dataclass

BBL_PER_SM3 = 6.28981077
BOE_PER_SM3_GAS = 1.0 / 169.9  # approximate energy-equivalent conversion

@dataclass
class EconomicConventions:
    money_basis: str = 'real'  # real | nominal
    base_year: int = 2027
    general_inflation: float = 0.025
    oil_escalation: float = 0.025
    gas_escalation: float = 0.025
    cost_escalation: float = 0.025
    discount_rate_basis: str = 'real'  # real | nominal


def real_to_nominal_rate(real_rate: float, inflation: float) -> float:
    return (1 + real_rate) * (1 + inflation) - 1


def nominal_to_real_rate(nominal_rate: float, inflation: float) -> float:
    return (1 + nominal_rate) / (1 + inflation) - 1


def consistent_discount_rate(rate: float, rate_basis: str, money_basis: str, inflation: float) -> float:
    if rate_basis == money_basis:
        return rate
    if money_basis == 'nominal':
        return real_to_nominal_rate(rate, inflation)
    return nominal_to_real_rate(rate, inflation)


def money_factor(unit: str) -> float:
    # canonical internal unit is MNOK. Returned factor converts MNOK -> display unit.
    return {'NOK': 1e6, 'kNOK': 1e3, 'MNOK': 1.0, 'BNOK': 1e-3}.get(unit, 1.0)


def oil_factor(unit: str) -> float:
    # canonical internal unit is MMbbl
    return {'bbl': 1e6, 'kbbl': 1e3, 'MMbbl': 1.0, 'MSm3 oil': 1.0 / BBL_PER_SM3}.get(unit, 1.0)


def gas_factor(unit: str) -> float:
    # canonical internal unit is MSm3
    return {'Sm3': 1e6, 'kSm3': 1e3, 'MSm3': 1.0, 'BCM': 1e-3, 'MMboe': BOE_PER_SM3_GAS}.get(unit, 1.0)


def display_frame(frame, money_unit='MNOK', oil_unit='MMbbl', gas_unit='MSm3'):
    """Convert canonical columns and their labels together, without mutating data."""
    out = frame.copy()
    conversions = {
        '_mnok': (money_factor(money_unit), money_unit),
        '_mmbbl': (oil_factor(oil_unit), oil_unit),
        '_msm3': (gas_factor(gas_unit), gas_unit),
    }
    labels = {}
    for column in out.columns:
        for suffix, (factor, unit) in conversions.items():
            if column.endswith(suffix):
                out[column] = out[column] * factor
                labels[column] = f'{column[:-len(suffix)]} ({unit})'
                break
    return out.rename(columns=labels)
