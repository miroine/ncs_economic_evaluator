"""Explicit, all-or-nothing analysis of a canonical input snapshot."""
import hashlib
import json
from dataclasses import asdict, replace

import numpy as np
import pandas as pd

from .advanced_analysis import breakeven_table, extended_breakeven_suite, spider
from .analysis import sensitivity_curve, tornado
from .assurance import model_health
from .concepts import DevelopmentConcept, compare_concepts
from .conventions import consistent_discount_rate
from .decision_tree import evaluate_tree
from .cutoff import CutoffSettings
from .engine import Assumptions, breakeven_oil_price, calculate_cashflow, calculate_npv, metrics, minimum_economic_volume
from .exploration import DiscoveryCase, discovery_distribution, prospect_emv
from .market import REQUIRED, validate_market_deck
from .monte_carlo import Uncertainty, run_monte_carlo
from .periods import expand_profile
from .project_io import validate_profile_table
from .scenarios import Scenario, evaluate_scenarios


def input_key(inputs):
    """Include every draft model input; omit presentation-only selections."""
    def encode(value):
        if isinstance(value, pd.DataFrame):
            return json.loads(value.to_json(orient='split', double_precision=15))
        raise TypeError(f'Unsupported input type: {type(value).__name__}')

    return hashlib.sha256(json.dumps(inputs, default=encode, sort_keys=True).encode()).hexdigest()


def _named_cases(table, cls, label):
    if table.empty:
        raise ValueError(f'Add at least one {label}')
    cases = []
    names = set()
    for row in table.to_dict('records'):
        case = cls(**row)
        if not isinstance(case.name, str) or not case.name.strip() or case.name in names:
            raise ValueError(f'{label.title()} names must be non-empty and unique')
        names.add(case.name)
        for key, value in row.items():
            if key == 'name':
                continue
            if not isinstance(value, (int, float)) or not np.isfinite(value):
                raise ValueError(f'{label.title()} {case.name}: {key} must be finite')
            if key.endswith('_factor') and value < 0:
                raise ValueError(f'{label.title()} {case.name}: factors cannot be negative')
            if key.endswith(('years',)) and int(value) != value:
                raise ValueError(f'{label.title()} {case.name}: delays must be whole years')
        if hasattr(case, 'start_delay_years'):
            if case.start_delay_years < 0:
                raise ValueError('Scenario delay cannot be negative')
            case.start_delay_years = int(case.start_delay_years)
        if hasattr(case, 'schedule_shift_years'):
            case.schedule_shift_years = int(case.schedule_shift_years)
        cases.append(case)
    return cases


def _number(value, label, minimum=None, maximum=None, whole=False):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not np.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    if whole and int(value) != value:
        raise ValueError(f'{label} must be a whole number')
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ValueError(f'{label} must be between {minimum} and {maximum}')


def run_all(inputs):
    """Return a complete result bundle; callers publish it only on success."""
    profile = validate_profile_table(inputs['profile'])
    if profile.empty:
        raise ValueError('Add at least one production/cost profile row')
    a = Assumptions(**inputs['assumptions'])
    if not all(np.isfinite(v) for v in asdict(a).values() if isinstance(v, (int, float))):
        raise ValueError('Assumptions must be finite')
    for key in ('oil_price_usd_bbl', 'gas_price_usd_sm3', 'discount_rate'):
        _number(getattr(a, key), key, 0)
    _number(a.usd_nok, 'USD/NOK', np.finfo(float).eps)
    _number(a.base_year, 'Base year', 1900, 2300, whole=True)
    for key in ('general_inflation', 'oil_escalation', 'gas_escalation', 'cost_escalation'):
        _number(getattr(a, key), key, -.99)
    if a.money_basis not in ('real', 'nominal') or a.discount_rate_basis not in ('real', 'nominal'):
        raise ValueError('Money and discount-rate bases must be real or nominal')
    if a.tax_mode not in ('ncs_v2', 'ncs_post_2022'):
        raise ValueError('Choose a supported fiscal engine')
    if inputs['resolution'] not in ('annual', 'quarterly', 'monthly') or inputs['capex_phasing'] not in ('even', 'front'):
        raise ValueError('Choose a supported resolution and CAPEX phasing')
    deck = inputs['market_deck'] if inputs['use_deck'] else None
    if deck is not None:
        issues = validate_market_deck(deck)
        if deck.empty:
            issues.append('The market deck cannot be empty')
        if issues:
            raise ValueError(' '.join(issues))
        deck = deck.copy()
        deck[REQUIRED] = deck[REQUIRED].apply(pd.to_numeric, errors='coerce')
        if not np.isfinite(deck[REQUIRED].to_numpy()).all():
            raise ValueError('Market deck values must be finite numbers')
        if (deck.year % 1 != 0).any() or deck.year.duplicated().any():
            raise ValueError('Market deck years must be unique whole numbers')
        if (deck.usd_nok <= 0).any():
            raise ValueError('Market deck USD/NOK must be positive')
    cutoff = CutoffSettings(**inputs['cutoff'])
    if cutoff.mode not in ('none', 'hard', 'negative_ocf', 'economic_limit'):
        raise ValueError('Choose a supported cutoff rule')
    if cutoff.mode == 'hard' and cutoff.hard_cutoff_year is None:
        raise ValueError('Hard cutoff requires a boundary year')
    if cutoff.hard_cutoff_year is not None:
        _number(cutoff.hard_cutoff_year, 'Cutoff year', 1900, 2300, whole=True)
    for key in ('consecutive_negative_periods', 'lookahead_periods', 'decom_lag_periods'):
        _number(getattr(cutoff, key), key, 0 if key == 'decom_lag_periods' else 1, 10, whole=True)
    for key in ('minimum_oil_mmbbl', 'minimum_gas_msm3'):
        _number(getattr(cutoff, key), key, 0)
    scenarios = _named_cases(inputs['scenarios'], Scenario, 'scenario')
    concepts = _named_cases(inputs['concepts'], DevelopmentConcept, 'concept')
    u = Uncertainty(**inputs['uncertainty'])
    for key, value in asdict(u).items():
        if key.endswith('_distribution'):
            if value not in ('normal', 'lognormal', 'triangular'):
                raise ValueError(f'{key}: choose normal, lognormal or triangular')
        else:
            _number(value, key, -.9 if key.endswith('_correlation') else 0,
                    .9 if key.endswith('_correlation') else 1)
    iterations, seed = inputs['iterations'], inputs['seed']
    _number(iterations, 'Monte Carlo iterations', 500, 10000, whole=True)
    _number(seed, 'Monte Carlo seed', 0, 999999, whole=True)
    exploration = inputs['exploration']
    for key in ('cos', 'dry', 'small', 'large'):
        _number(exploration[key], f'Exploration {key}')
    if not 0 <= exploration['cos'] <= 1 or exploration['dry'] < 0:
        raise ValueError('Exploration chance must be between 0 and 1; dry-hole cost cannot be negative')
    p = expand_profile(profile, inputs['resolution'], inputs['capex_phasing'])
    cf = calculate_cashflow(p, a, deck, cutoff)
    scenario_results, scenario_cfs = evaluate_scenarios(p, a, scenarios, deck, cutoff)
    scenario_values = dict(zip(scenario_results.scenario, scenario_results.npv_mnok))
    tree = evaluate_tree(inputs['tree'], scenario_values, consistent_discount_rate(
        a.discount_rate, a.discount_rate_basis, a.money_basis, a.general_inflation))
    # Do not publish a success-shaped rollback for an invalid tree.
    if tree['warnings']:
        raise ValueError('Decision tree: ' + '; '.join(tree['warnings']))
    be = breakeven_oil_price(p, a, cutoff=cutoff) if deck is None else None
    bet = breakeven_table(p, a, deck, cutoff=cutoff)
    oil_factor = bet.loc[bet.variable == 'Oil price', 'breakeven_factor'].iloc[0]
    deck_be = None if deck is None or pd.isna(oil_factor) else float(oil_factor)
    price_curve = pd.DataFrame()
    if be is not None:
        prices = np.linspace(max(0, be*.45), max(be*1.65, a.oil_price_usd_bbl*1.4, 20), 31)
        price_curve = pd.DataFrame({
            'oil_price': prices,
            'npv_mnok': [calculate_npv(p, replace(a, oil_price_usd_bbl=float(price)), cutoff=cutoff) for price in prices],
        })
    samples, factors = run_monte_carlo(p, a, u, int(iterations), int(seed), True, deck, cutoff)
    cases = [DiscoveryCase('Small', .55, exploration['small']), DiscoveryCase('Large', .45, exploration['large'])]
    return {
        'key': input_key(inputs),
        'profile': p, 'cashflow': cf, 'metrics': metrics(cf),
        'be': be, 'deck_be': deck_be, 'mev': minimum_economic_volume(p, a, deck, cutoff),
        'breakevens': bet, 'extended_breakevens': extended_breakeven_suite(p, a, deck, cutoff),
        'price_curve': price_curve,
        'tornado': tornado(p, a, market_deck=deck, cutoff=cutoff),
        'curves': {v: sensitivity_curve(p, a, v, market_deck=deck, cutoff=cutoff)
                   for v in ('Oil price', 'Gas price', 'Production', 'CAPEX', 'OPEX')},
        'spider': spider(p, a, deck, cutoff=cutoff),
        'scenarios': scenario_results, 'scenario_cfs': scenario_cfs, 'scenario_values': scenario_values,
        'concepts': compare_concepts(p, a, concepts, deck, cutoff),
        'samples': samples, 'factors': factors, 'tree': tree,
        'exploration': prospect_emv(exploration['cos'], exploration['dry'], cases),
        'discoveries': pd.DataFrame(discovery_distribution(exploration['cos'], exploration['dry'], cases)),
        'health': model_health(profile, deck, [.55,.45],
                               {'cessation_year':cf.attrs.get('cutoff_year'),'decom_year':None},
                               recoverable_oil_mmbbl=float(profile.oil_mmbbl.sum())*1.05,
                               money_basis=a.money_basis, discount_basis=a.discount_rate_basis),
    }
