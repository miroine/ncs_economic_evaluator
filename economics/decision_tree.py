def evaluate_tree(tree: dict, scenario_values=None, discount_rate: float=0.0):
    """Rollback a decision tree.

    V10 edges may include cost_mnok and delay_years. Edge value is the delayed child
    value less branch cost. Existing V9 trees without these fields are unchanged.
    """
    tree=tree or {}
    scenario_values=scenario_values or {}
    warnings=[]; selected=[]; visiting=set(); edge_values={}
    raw_nodes=tree.get('nodes',[])
    nodes={}
    for node in raw_nodes:
        node_id=node.get('id')
        if not node_id:
            warnings.append('A tree node is missing its id and was ignored')
        elif node_id in nodes:
            warnings.append(f"Duplicate node id '{node_id}'")
        else:
            nodes[node_id]=node
    edges=tree.get('edges',[]); outgoing={}; incoming=set(); valid_edges=[]
    for edge in edges:
        source,target=edge.get('source'),edge.get('target')
        if source not in nodes or target not in nodes:
            warnings.append(f"Edge '{edge.get('id', '?')}' has an unknown source or target and was ignored")
            continue
        valid_edges.append(edge)
    edges=valid_edges
    for e in edges:
        outgoing.setdefault(e['source'],[]).append(e); incoming.add(e['target'])
    roots=[n for n in nodes if n not in incoming]
    if len(roots)>1:
        warnings.append('Tree has multiple unconnected roots; only the first root is evaluated')
    if nodes and not roots:
        warnings.append('Tree has no root; check for a cycle')

    def ev(nid):
        if nid in visiting:
            warnings.append(f'Cycle detected at {nid}'); return 0.0
        visiting.add(nid); n=nodes[nid]; es=outgoing.get(nid,[])
        if not es:
            key=n.get('scenario_key')
            if key and key not in scenario_values:
                warnings.append(f"Outcome '{n.get('label', nid)}' references missing scenario '{key}'; using fallback value")
            val=float(scenario_values.get(key,n.get('value',0) or 0)); visiting.remove(nid); return val
        vals=[]
        for e in es:
            child=ev(e['target']); delay=max(0.,float(e.get('delay_years',0) or 0)); cost=float(e.get('cost_mnok',0) or 0)
            branch=child/((1+discount_rate)**delay)-cost if discount_rate>-1 else child-cost
            vals.append(branch); edge_values[e.get('id',f'{nid}->{e["target"]}')]=branch
        if n.get('type')=='chance':
            probs=[float(e.get('probability',0) or 0) for e in es]
            if any(p < 0 for p in probs): warnings.append(f"Probabilities from '{n.get('label',nid)}' include a negative value")
            if abs(sum(probs)-1)>1e-6: warnings.append(f"Probabilities from '{n.get('label',nid)}' sum to {sum(probs):.3f}")
            val=sum(p*v for p,v in zip(probs,vals))
        else:
            j=max(range(len(vals)),key=lambda i: vals[i]); selected.append(es[j].get('id',f'{nid}->{es[j]["target"]}')); val=vals[j]
        visiting.remove(nid); return val
    return {'value':ev(roots[0]) if roots else 0.0,'selected_edges':selected,'edge_values':edge_values,'warnings':warnings}

def expected_value(tree: dict) -> float: return evaluate_tree(tree)['value']
