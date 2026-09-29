from __future__ import annotations
import numpy as np, pandas as pd

def validate_register(register, corr=None):
    issues=[]; names=[]
    for x in register:
        name=x['name']; names.append(name); d=x.get('distribution','normal')
        if d not in {'normal','lognormal','triangular','uniform'}: issues.append(f'{name}: unsupported distribution')
        if d=='triangular' and not (x['low']<=x['mode']<=x['high']): issues.append(f'{name}: invalid triangular bounds')
        if d=='uniform' and x['low']>x['high']: issues.append(f'{name}: invalid uniform bounds')
        if d in {'normal','lognormal'} and float(x.get('std',0))<0: issues.append(f'{name}: negative std')
    if len(names)!=len(set(names)): issues.append('Duplicate uncertainty names')
    if corr is not None:
        c=np.asarray(corr,float)
        if c.shape!=(len(names),len(names)): issues.append('Correlation matrix shape mismatch')
        elif not np.allclose(c,c.T,atol=1e-8) or not np.allclose(np.diag(c),1): issues.append('Correlation matrix must be symmetric with unit diagonal')
        elif np.min(np.linalg.eigvalsh(c)) < -1e-8: issues.append('Correlation matrix is not positive semidefinite')
    return issues

def sample_register(register,n=1000,corr=None,seed=42):
    issues=validate_register(register,corr); 
    if issues: raise ValueError('; '.join(issues))
    rng=np.random.default_rng(seed); k=len(register); z=rng.standard_normal((n,k))
    if corr is not None: z=z@np.linalg.cholesky(np.asarray(corr,float)+np.eye(k)*1e-12).T
    from statistics import NormalDist
    nd=NormalDist(); u=np.vectorize(nd.cdf)(z); out={}
    for j,x in enumerate(register):
        d=x.get('distribution','normal'); zz=z[:,j]; uu=u[:,j]
        if d=='normal': v=float(x['mean'])+float(x.get('std',0))*zz
        elif d=='lognormal': v=np.exp(np.log(float(x['median']))+float(x.get('sigma',0))*zz)
        elif d=='uniform': v=float(x['low'])+(float(x['high'])-float(x['low']))*uu
        else:
            lo,mo,hi=map(float,(x['low'],x['mode'],x['high'])); c=(mo-lo)/(hi-lo) if hi>lo else 0
            v=np.where(uu<c,lo+np.sqrt(uu*(hi-lo)*(mo-lo)),hi-np.sqrt((1-uu)*(hi-lo)*(hi-mo))) if hi>lo else np.full(n,lo)
        out[x['name']]=v
    return pd.DataFrame(out)
