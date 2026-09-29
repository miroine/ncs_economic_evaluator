from __future__ import annotations
import io
import pandas as pd

def decision_report_text(project_name, metrics, cutoff_year=None, cutoff_reason=None, concept_table=None):
    lines=[f'# Investment Decision Summary — {project_name}','', 'Made by Merouane Hamdani — educational purposes only, non-commercial.','', '## Core economics']
    for k,v in metrics.items(): lines.append(f'- {k}: {v}')
    lines += ['', '## Economic limit', f'- Cessation: {cutoff_year if cutoff_year is not None else "Not triggered"}', f'- Reason: {cutoff_reason or "n/a"}']
    if concept_table is not None and len(concept_table):
        lines += ['', '## Development concepts', concept_table.to_csv(index=False)]
    lines += ['', '## Important limitation','Analytical educational model. Validate fiscal, reserves, engineering, commercial and company-specific assumptions before decisions.']
    return '\n'.join(lines).encode('utf-8')
