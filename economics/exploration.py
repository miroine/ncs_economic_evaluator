from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass
class DiscoveryCase:
    name: str
    conditional_probability: float
    development_npv_mnok: float

def prospect_emv(chance_of_success, dry_hole_cost_mnok, discovery_cases):
    """Risked exploration EMV. Discovery probabilities are conditional on success."""
    cos=float(chance_of_success); dry=float(dry_hole_cost_mnok)
    if not 0 <= cos <= 1: raise ValueError('Chance of success must be between 0 and 1')
    cases=[c if isinstance(c,DiscoveryCase) else DiscoveryCase(**c) for c in discovery_cases]
    p=np.array([c.conditional_probability for c in cases],float)
    if len(cases)==0 or np.any(p<0) or not np.isclose(p.sum(),1): raise ValueError('Conditional discovery probabilities must sum to 1')
    success_value=float(sum(c.conditional_probability*c.development_npv_mnok for c in cases))
    emv=cos*success_value-(1-cos)*dry
    return {'chance_of_success':cos,'success_case_ev_mnok':success_value,'dry_hole_cost_mnok':dry,'risked_emv_mnok':emv}

def discovery_distribution(chance_of_success, dry_hole_cost_mnok, discovery_cases):
    cases=[c if isinstance(c,DiscoveryCase) else DiscoveryCase(**c) for c in discovery_cases]
    rows=[{'state':'Dry','probability':1-float(chance_of_success),'value_mnok':-float(dry_hole_cost_mnok)}]
    rows += [{'state':c.name,'probability':float(chance_of_success)*c.conditional_probability,'value_mnok':c.development_npv_mnok} for c in cases]
    return rows
