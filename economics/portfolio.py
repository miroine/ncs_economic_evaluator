from __future__ import annotations
from dataclasses import dataclass, asdict
import json, datetime

@dataclass
class ProjectSnapshot:
    name:str
    version:str
    created_at:str
    metrics:dict
    notes:str=''

def snapshot(name,version,metrics,notes=''):
    return ProjectSnapshot(name,version,datetime.datetime.now(datetime.timezone.utc).isoformat(),dict(metrics),notes)

def dumps_snapshots(items):
    return json.dumps([asdict(x) if hasattr(x,'__dataclass_fields__') else x for x in items],indent=2).encode()
