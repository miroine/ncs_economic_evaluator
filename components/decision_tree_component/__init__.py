from pathlib import Path
import streamlit.components.v1 as components
_component=components.declare_component('ncs_decision_tree',path=str(Path(__file__).parent/'frontend'))
def decision_tree(value, scenario_values=None, key=None, height=700):
    return _component(value=value,scenario_values=scenario_values or {},height=height,key=key,default=value)
