import numpy as np

def evpi_from_payoffs(payoffs, probabilities):
    """EVPI for alternatives x states payoff matrix."""
    x=np.asarray(payoffs,float); p=np.asarray(probabilities,float)
    if x.ndim != 2 or p.ndim != 1 or x.shape[1] != len(p): raise ValueError('Shape mismatch')
    if np.any(p < 0) or not np.isclose(p.sum(),1.0): raise ValueError('Probabilities must sum to 1')
    current=float(np.max(x @ p))
    perfect=float(np.sum(np.max(x,axis=0)*p))
    return {'current_ev':current,'ev_with_perfect_information':perfect,'evpi':perfect-current}

def evsi_from_signals(payoffs, state_probabilities, signal_given_state, information_cost=0.0):
    """EVSI for alternatives x states payoffs and signals x states likelihoods."""
    x=np.asarray(payoffs,float); p=np.asarray(state_probabilities,float); l=np.asarray(signal_given_state,float)
    if x.ndim!=2 or l.ndim!=2 or x.shape[1]!=len(p) or l.shape[1]!=len(p): raise ValueError('Shape mismatch')
    if np.any(p<0) or not np.isclose(p.sum(),1): raise ValueError('State probabilities must sum to 1')
    if np.any(l<0) or not np.allclose(l.sum(axis=0),1): raise ValueError('Signal likelihoods must sum to 1 by state')
    prior=float(np.max(x@p)); informed=0.0
    for row in l:
        ps=float(row@p)
        if ps<=0: continue
        posterior=row*p/ps; informed += ps*float(np.max(x@posterior))
    evsi=informed-prior
    return {'current_ev':prior,'ev_with_sample_information':informed,'evsi':evsi,'information_cost':float(information_cost),'net_value_of_information':evsi-float(information_cost)}
