import json

SCHEMA_VERSION = 2

def project_payload(profile, assumptions, scenarios, tree, metadata=None, market_deck=None, concepts=None, settings=None, snapshots=None):
    version=2 if any(x is not None for x in (market_deck,concepts,settings,snapshots)) else 1
    return {'schema_version':version,'metadata':metadata or {},'profile':profile.to_dict('records'),'assumptions':assumptions.__dict__,'scenarios':scenarios.to_dict('records') if hasattr(scenarios,'to_dict') else scenarios,'decision_tree':tree,'market_deck':None if market_deck is None else market_deck.to_dict('records'),'concepts':None if concepts is None else (concepts.to_dict('records') if hasattr(concepts,'to_dict') else concepts),'settings':settings or {},'snapshots':snapshots or []}

def dumps_project(*args, **kwargs): return json.dumps(project_payload(*args, **kwargs), indent=2).encode('utf-8')

def loads_project(raw):
    if hasattr(raw,'read'): raw=raw.read()
    if isinstance(raw,bytes): raw=raw.decode('utf-8')
    data=json.loads(raw); version=int(data.get('schema_version',1))
    if version not in (1,2): raise ValueError('Unsupported project schema version')
    if version==1:
        data.setdefault('market_deck',None); data.setdefault('concepts',None); data.setdefault('settings',{}); data.setdefault('snapshots',[])
    return data
