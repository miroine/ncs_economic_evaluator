from __future__ import annotations
from dataclasses import dataclass, asdict

GATES=('Discovery','Appraisal','Concept Select','FEED','FID','Execute','Operate')
@dataclass
class DecisionGate:
    stage:str; status:str='Open'; continuation_value_mnok:float=0.0; remaining_cost_mnok:float=0.0; notes:str=''
    def __post_init__(self):
        if self.stage not in GATES: raise ValueError('Unknown decision gate')
    @property
    def net_continue_value_mnok(self): return float(self.continuation_value_mnok)-float(self.remaining_cost_mnok)

def gate_register(items):
    return [asdict(x if isinstance(x,DecisionGate) else DecisionGate(**x)) | {'net_continue_value_mnok':(x if isinstance(x,DecisionGate) else DecisionGate(**x)).net_continue_value_mnok} for x in items]
