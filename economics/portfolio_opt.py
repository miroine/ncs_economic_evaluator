from __future__ import annotations
import itertools

def optimize_portfolio(projects, annual_capex_limits=None, max_projects=None):
    """Exact small-portfolio optimizer under annual CAPEX and project-count constraints."""
    ps=list(projects); best={'selected':[],'total_value_mnok':0.0,'annual_capex':{}}
    for r in range(len(ps)+1):
        if max_projects is not None and r>max_projects: continue
        for combo in itertools.combinations(ps,r):
            cap={}
            for p in combo:
                for y,v in p.get('annual_capex',{}).items(): cap[y]=cap.get(y,0.0)+float(v)
            if annual_capex_limits and any(cap.get(y,0)>float(lim) for y,lim in annual_capex_limits.items()): continue
            val=sum(float(p.get('value_mnok',0)) for p in combo)
            if val>best['total_value_mnok']: best={'selected':[p['name'] for p in combo],'total_value_mnok':val,'annual_capex':cap}
    return best
