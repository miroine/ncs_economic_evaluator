import json
import io
import numpy as np
import pandas as pd

SCHEMA_VERSION = 2
PROFILE_COLUMNS = ('year', 'oil_mmbbl', 'gas_msm3', 'capex_mnok', 'opex_mnok', 'decom_mnok')

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


def validate_profile_table(profile):
    """Normalize and validate a production/cost profile in canonical model units."""
    frame = pd.DataFrame(profile).copy()
    aliases = {
        'oil_mmbl': 'oil_mmbbl',
        'oil_mm_bbl': 'oil_mmbbl',
        'gas_msm3': 'gas_msm3',
    }
    frame.columns = [aliases.get(str(column).strip().lower().replace(' ', '_'),
                                 str(column).strip().lower().replace(' ', '_'))
                     for column in frame.columns]
    missing = [column for column in PROFILE_COLUMNS if column not in frame.columns and column != 'decom_mnok']
    if missing:
        raise ValueError(f"Missing profile columns: {', '.join(missing)}")
    if 'decom_mnok' not in frame.columns:
        frame['decom_mnok'] = 0.0
    frame = frame.loc[:, PROFILE_COLUMNS]
    for column in PROFILE_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    if frame[list(PROFILE_COLUMNS)].isna().any().any() or not np.isfinite(frame[list(PROFILE_COLUMNS)].to_numpy()).all():
        raise ValueError('Profile values must all be finite numbers.')
    if (frame['oil_mmbbl'] < 0).any() or (frame['gas_msm3'] < 0).any():
        raise ValueError('Oil and gas production volumes cannot be negative.')
    if (frame['year'] % 1 != 0).any() or frame['year'].duplicated().any():
        raise ValueError('Profile years must be unique whole numbers.')
    frame['year'] = frame['year'].astype(int)
    return frame.sort_values('year').reset_index(drop=True)


def load_profile_table(raw, filename):
    """Load CSV or Excel profile data and return a validated canonical-unit table."""
    name = str(filename).lower()
    if name.endswith('.csv'):
        frame = pd.read_csv(io.BytesIO(raw))
    elif name.endswith(('.xlsx', '.xlsm')):
        frame = pd.read_excel(io.BytesIO(raw))
    else:
        raise ValueError('Choose a CSV or Excel (.xlsx) profile file.')
    return validate_profile_table(frame)
