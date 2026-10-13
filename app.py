import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from economics.engine import Assumptions, calculate_cashflow, metrics, breakeven_oil_price
try:
    from economics.engine import minimum_economic_volume
except ImportError:
    try:
        from economics import minimum_economic_volume
    except ImportError:
        import importlib
        import economics.engine
        importlib.reload(economics.engine)
        try:
            from economics.engine import minimum_economic_volume
        except ImportError:
            def minimum_economic_volume(profile, assumptions, market_deck=None, cutoff=None, max_factor=1_000_000):
                from economics.conventions import BOE_PER_SM3_GAS

                base_volume = float(profile['oil_mmbbl'].sum() + profile['gas_msm3'].sum() * BOE_PER_SM3_GAS)
                if not np.isfinite(base_volume) or base_volume <= 0:
                    return None

                def value(factor):
                    trial_profile = profile.copy()
                    trial_profile[['oil_mmbbl', 'gas_msm3']] *= factor
                    return metrics(calculate_cashflow(trial_profile, assumptions, market_deck, cutoff))['npv_mnok']

                low, high = 0.0, 1.0
                low_value, high_value = value(low), value(high)
                if low_value >= 0:
                    return 0.0
                while high_value < 0 and high < max_factor:
                    high = min(high * 2, max_factor)
                    high_value = value(high)
                if high_value < 0:
                    return None
                for _ in range(80):
                    mid = (low + high) / 2
                    if value(mid) >= 0:
                        high = mid
                    else:
                        low = mid
                return base_volume * (low + high) / 2
from economics.analysis import tornado, sensitivity_curve, npv_waterfall
from economics.market import default_market_deck, validate_market_deck
from economics.advanced_analysis import spider, breakeven_table, breakeven_factor, exceedance_curve, tax_bridge, excel_workbook, breakeven_suite, extended_breakeven_suite
from economics.conventions import money_factor, oil_factor, gas_factor, consistent_discount_rate
from economics.decision_tree import evaluate_tree
from economics.scenarios import Scenario, evaluate_scenarios
from components.decision_tree_component import decision_tree
from economics.monte_carlo import Uncertainty, run_monte_carlo, run_tree_monte_carlo, summary as mc_summary, correlation_matrix
from economics.cutoff import CutoffSettings
from economics.production import generated_profile
from economics.concepts import DevelopmentConcept, compare_concepts
from economics.value_of_information import evpi_from_payoffs, evsi_from_signals
from economics.periods import expand_profile
from economics.decks_v2 import named_decks, select_deck
from economics.reserves import reserves_profile
from economics.analysis_studio import curve as studio_curve
from economics.uncertainty_v2 import diagnostics as uncertainty_diagnostics
from economics.fiscal_v2 import government_take
from economics.reporting import decision_report_text
from economics.portfolio import snapshot, dumps_snapshots
from economics.project_io import dumps_project, loads_project, load_profile_table, validate_profile_table
from economics.exploration import DiscoveryCase, prospect_emv, discovery_distribution
from economics.commercial import phased_costs
from economics.schedule_risk import simulate_schedule_risk, schedule_summary
from economics.decision_gates import DecisionGate, gate_register
from economics.portfolio_opt import optimize_portfolio
from economics.assurance import model_health
from economics.physical_v12 import ResourceCase, FacilityLimits, recoverable_resources, integrated_profile
from economics.schedule_v12 import validate_schedule, simulate_schedule
from economics.cost_fx_v12 import convert_cost_lines
from economics.emissions_v12 import emissions_economics
from economics.uncertainty_register_v12 import validate_register, sample_register
from economics.inspector_v12 import inspect_period
from economics.validation_v12 import validate_model, has_errors
from economics.project_decision_v12 import evaluate_project_tree


st.set_page_config(page_title="NCS Economics Workbench", page_icon="🌊", layout="wide")

THEMES = {
    "North Sea": {"bg":"#071923","panel":"#0d2733","card":"#123746","text":"#edf7fa","muted":"#9fc0cb","accent":"#36b7c9","accent2":"#78d6b3","grid":"#244956","plot":"#0d2733"},
    "Midnight Offshore": {"bg":"#090d18","panel":"#111827","card":"#172033","text":"#f4f7fb","muted":"#9aa7bd","accent":"#60a5fa","accent2":"#a78bfa","grid":"#29344a","plot":"#111827"},
    "Arctic Light": {"bg":"#f4f8fa","panel":"#ffffff","card":"#eaf1f4","text":"#17313b","muted":"#5e7680","accent":"#087f8c","accent2":"#287271","grid":"#d6e2e6","plot":"#ffffff"},
}

def apply_theme(name):
    t=THEMES[name]
    pio.templates["ncs_workbench"] = go.layout.Template(layout=dict(
        paper_bgcolor=t["plot"], plot_bgcolor=t["plot"], font=dict(color=t["text"], family="Inter, system-ui, sans-serif"),
        title=dict(font=dict(size=18)), colorway=[t["accent"],t["accent2"],"#f59e0b","#ef6f6c","#94a3b8","#22c55e"],
        xaxis=dict(gridcolor=t["grid"], zerolinecolor=t["grid"]), yaxis=dict(gridcolor=t["grid"], zerolinecolor=t["grid"]),
        legend=dict(bgcolor="rgba(0,0,0,0)"), margin=dict(l=45,r=25,t=60,b=40)))
    pio.templates.default="ncs_workbench"
    st.markdown(f"""<style>
    .stApp {{background:{t['bg']}; color:{t['text']};}}
    [data-testid="stSidebar"] {{background:{t['panel']}; border-right:1px solid {t['grid']};}}
    [data-testid="stHeader"] {{background:rgba(0,0,0,0);}}
    h1,h2,h3 {{letter-spacing:-.02em;}}
    div[data-testid="stMetric"] {{background:{t['card']}; border:1px solid {t['grid']}; padding:16px 18px; border-radius:14px;}}
    div[data-testid="stMetricLabel"] {{color:{t['muted']};}}
    .stTabs [data-baseweb="tab-list"] {{gap:6px; border-bottom:1px solid {t['grid']};}}
    .stTabs [data-baseweb="tab"] {{border-radius:9px 9px 0 0; padding:8px 14px;}}
    .stTabs [aria-selected="true"] {{background:{t['card']}; color:{t['accent']};}}
    .ncs-hero {{padding:18px 22px; border:1px solid {t['grid']}; border-radius:16px; background:linear-gradient(135deg,{t['panel']},{t['card']}); margin-bottom:18px;}}
    .ncs-kicker {{color:{t['accent']}; font-size:.78rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase;}}
    .ncs-sub {{color:{t['muted']}; margin-top:4px;}}
    [data-testid="stHorizontalBlock"] {{flex-wrap:wrap;}}
    [data-testid="column"] {{min-width:260px;}}
    .stDataFrame, [data-testid="stDataEditor"] {{overflow-x:auto;}}
    @media (max-width: 900px) {{ .ncs-hero {{padding:14px 16px;}} [data-testid="column"] {{min-width:100% !important;}} }}
    .ncs-notice {{margin-top:22px; padding:12px 14px; border:1px solid {t['grid']}; border-radius:12px; color:{t['muted']}; font-size:.82rem; background:{t['card']};}}
    </style>""", unsafe_allow_html=True)

with st.sidebar:
    theme_name=st.selectbox("Interface theme", list(THEMES), index=0, key="theme_name")
apply_theme(theme_name)

st.markdown("""<div class="ncs-hero"><div class="ncs-kicker">NCS project economics</div><h1 style="margin:.15rem 0 .2rem 0">NCS Economics Workbench</h1><div class="ncs-sub">Project economics · fiscal modelling · uncertainty · decision analysis</div></div>""", unsafe_allow_html=True)

years = list(range(2027, 2042))
def default_profile():
    oil = [0,0,2,7,10,11,10,9,8,7,6,5,4,3,2]
    gas = [0,0,50,180,250,270,250,220,190,160,130,100,75,50,30]
    capex = [1500,4500,6000,3500,800]+[200]*10
    opex = [40,80,300,550,700,750,720,680,630,580,530,480,430,380,330]
    decom = [0]*14+[2500]
    return pd.DataFrame({'year':years,'oil_mmbbl':oil,'gas_msm3':gas,'capex_mnok':capex,'opex_mnok':opex,'decom_mnok':decom})

if 'profile' not in st.session_state: st.session_state.profile = default_profile()
if 'market_deck' not in st.session_state: st.session_state.market_deck = default_market_deck(years)

# Project imports are staged because Streamlit does not allow changing a widget's
# state after that widget has already been instantiated in the same rerun.
if '_pending_project_import' in st.session_state:
    loaded=st.session_state.pop('_pending_project_import')
    st.session_state.profile=validate_profile_table(loaded['profile'])
    if loaded.get('market_deck') is not None: st.session_state.market_deck=pd.DataFrame(loaded['market_deck'])
    if loaded.get('scenarios') is not None: st.session_state.scenario_table=pd.DataFrame(loaded['scenarios'])
    if loaded.get('decision_tree') is not None: st.session_state.decision_tree=loaded['decision_tree']
    if loaded.get('concepts') is not None: st.session_state.concept_table=pd.DataFrame(loaded['concepts'])
    st.session_state.snapshots=loaded.get('snapshots',[])
    la=loaded.get('assumptions',{}); ls=loaded.get('settings',{})
    amap={'oil_price_usd_bbl':'assump_oil','gas_price_usd_sm3':'assump_gas','usd_nok':'assump_fx','money_basis':'assump_money_basis','base_year':'assump_base_year','discount_rate_basis':'assump_rate_basis','tax_mode':'setting_fiscal_engine'}
    for src,dst in amap.items():
        if src in la: st.session_state[dst]=la[src]
    if 'discount_rate' in la: st.session_state.assump_disc_pct=float(la['discount_rate'])*100
    if 'general_inflation' in la: st.session_state.assump_inflation_pct=float(la['general_inflation'])*100
    if 'oil_escalation' in la: st.session_state.assump_oil_esc_pct=float(la['oil_escalation'])*100
    if 'gas_escalation' in la: st.session_state.assump_gas_esc_pct=float(la['gas_escalation'])*100
    if 'cost_escalation' in la: st.session_state.assump_cost_esc_pct=float(la['cost_escalation'])*100
    if 'time_resolution' in ls: st.session_state.setting_resolution=ls['time_resolution']
    if 'capex_phasing' in ls: st.session_state.setting_capex_phasing=ls['capex_phasing']

PAGES = ['Dashboard','Production & costs','Economics','Scenarios','Uncertainty','Sensitivity & breakeven','Decision tree','Data / audit','Market & advanced','Decision studio','Analysis studio','Projects & reports','Exploration & portfolio','Integrated field development']
with st.sidebar:
    st.subheader('Workspace')
    page = st.selectbox('Module', PAGES, key='active_page')
with st.sidebar:
    st.header('Case assumptions')
    oil = st.number_input('Oil price (USD/bbl)', 0.0, 300.0, 75.0, 1.0, key='assump_oil')
    gas = st.number_input('Gas price (USD/Sm³)', 0.0, 5.0, 0.35, .01, key='assump_gas')
    fx = st.number_input('USD/NOK', 1.0, 30.0, 10.5, .1, key='assump_fx')
    disc = st.number_input('Discount rate (%)', 0.0, 30.0, 8.0, .5, key='assump_disc_pct')/100
    st.divider()
    st.subheader('Economic conventions')
    money_basis = st.radio('Money basis', ['real','nominal'], horizontal=True, key='assump_money_basis')
    base_year = st.number_input('Money / price base year', 2000, 2100, years[0], 1, key='assump_base_year')
    inflation = st.number_input('General inflation (%)', 0.0, 15.0, 2.5, .1, key='assump_inflation_pct')/100
    rate_basis = st.radio('Entered discount rate is', ['real','nominal'], horizontal=True, key='assump_rate_basis')
    if money_basis == 'nominal':
        oil_esc = st.number_input('Oil escalation (%)', -10.0, 20.0, 2.5, .1, key='assump_oil_esc_pct')/100
        gas_esc = st.number_input('Gas escalation (%)', -10.0, 20.0, 2.5, .1, key='assump_gas_esc_pct')/100
        cost_esc = st.number_input('Cost escalation (%)', -10.0, 20.0, 2.5, .1, key='assump_cost_esc_pct')/100
    else:
        oil_esc = gas_esc = cost_esc = 0.0
    st.divider()
    st.subheader('Display units')
    money_unit = st.selectbox('Money', ['MNOK','BNOK','kNOK','NOK'])
    oil_unit = st.selectbox('Oil volume', ['MMbbl','kbbl','MSm3 oil','bbl'])
    gas_unit = st.selectbox('Gas volume', ['MSm3','BCM','MMboe','kSm3','Sm3'])
    st.caption('Canonical calculation units: MNOK, MMbbl and MSm³. Display conversions do not change economics.')
    use_deck = st.toggle('Use annual market deck', value=True, help='Use editable annual oil, gas and FX curves instead of flat assumptions.', key='setting_use_deck')
    st.divider()
    st.subheader('Economic cutoff')
    cutoff_mode=st.selectbox('Cutoff rule',['none','hard','negative_ocf','economic_limit'],format_func=lambda x:{'none':'None','hard':'Hard cutoff','negative_ocf':'Negative operating CF','economic_limit':'Economic limit / look-ahead'}[x])
    hard_year=st.number_input('Hard boundary / cutoff year',int(min(years)),int(max(years)+20),int(max(years)),1)
    neg_periods=st.number_input('Consecutive negative periods',1,10,2,1)
    lookahead=st.number_input('Economic-limit look-ahead periods',1,10,3,1)
    min_oil=st.number_input('Minimum oil rate (MMbbl/period)',0.0,100.0,0.0,.1)
    min_gas=st.number_input('Minimum gas rate (MSm³/period)',0.0,10000.0,0.0,10.0)
    decom_lag=st.number_input('Decommissioning lag (periods)',0,10,1,1)
    st.divider()
    st.subheader('Model resolution')
    time_resolution=st.selectbox('Cash-flow resolution',['annual','quarterly','monthly'],format_func=str.title,key='setting_resolution')
    capex_phasing=st.selectbox('Subannual CAPEX phasing',['even','front'],format_func=lambda x:'Even' if x=='even' else 'Front-loaded',key='setting_capex_phasing')
    fiscal_engine=st.selectbox('Fiscal engine',['ncs_v2','ncs_post_2022'],format_func=lambda x:'NCS fiscal V2' if x=='ncs_v2' else 'Legacy post-2022 baseline',key='setting_fiscal_engine')
    st.info('Fiscal calculations remain an analytical project-level model; validate vintage/company-specific tax treatment before investment decisions.')
    st.markdown('<div class="ncs-notice"><b>Made by Merouane Hamdani</b><br>For educational purposes only — non-commercial.<br><br>Not investment, tax, legal, reserves, or engineering advice.</div>', unsafe_allow_html=True)

a = Assumptions(oil, gas, fx, disc, tax_mode=fiscal_engine, money_basis=money_basis, base_year=int(base_year), general_inflation=inflation, oil_escalation=oil_esc, gas_escalation=gas_esc, cost_escalation=cost_esc, discount_rate_basis=rate_basis)
active_deck = st.session_state.market_deck if use_deck else None
cutoff = CutoffSettings(mode=cutoff_mode, hard_cutoff_year=int(hard_year) if cutoff_mode in ('hard','negative_ocf','economic_limit') else None, consecutive_negative_periods=int(neg_periods), lookahead_periods=int(lookahead), minimum_oil_mmbbl=float(min_oil), minimum_gas_msm3=float(min_gas), decom_lag_periods=int(decom_lag))
active_profile = expand_profile(st.session_state.profile, time_resolution, capex_phasing)
cf = calculate_cashflow(active_profile, a, active_deck, cutoff)
m = metrics(cf)
be = breakeven_oil_price(st.session_state.profile, a, cutoff=cutoff) if not use_deck and page in ('Dashboard', 'Sensitivity & breakeven') else None
deck_be = breakeven_factor(st.session_state.profile, a, 'Oil price', active_deck, cutoff=cutoff) if use_deck and page in ('Dashboard', 'Sensitivity & breakeven') else None
mev = minimum_economic_volume(st.session_state.profile, a, active_deck, cutoff) if page in ('Dashboard', 'Sensitivity & breakeven') else None

# Lightweight shared scenario state. Keep this outside individual pages because
# decision-tree, exports and audit views consume the same scenario economics.
if 'scenario_table' not in st.session_state:
    st.session_state.scenario_table = pd.DataFrame([
        {'name':'Base','oil_factor':1.0,'gas_factor':1.0,'capex_factor':1.0,'opex_factor':1.0,'production_factor':1.0,'start_delay_years':0},
        {'name':'High resource','oil_factor':1.0,'gas_factor':1.0,'capex_factor':1.05,'opex_factor':1.0,'production_factor':1.25,'start_delay_years':0},
        {'name':'Low resource','oil_factor':1.0,'gas_factor':1.0,'capex_factor':0.95,'opex_factor':1.0,'production_factor':0.75,'start_delay_years':0},
        {'name':'1-year delay','oil_factor':1.0,'gas_factor':1.0,'capex_factor':1.0,'opex_factor':1.0,'production_factor':1.0,'start_delay_years':1},
    ])
def current_scenarios():
    out=[]
    for row in st.session_state.scenario_table.to_dict('records'):
        try: out.append(Scenario(**row))
        except (TypeError, ValueError): pass
    return out
scenario_results = pd.DataFrame(columns=['scenario', 'npv_mnok', 'irr', 'payback_year'])
scenario_cfs = {}
if page in ('Scenarios', 'Decision tree', 'Data / audit', 'Market & advanced', 'Projects & reports'):
    scenarios=current_scenarios()
    scenario_results, scenario_cfs=evaluate_scenarios(st.session_state.profile,a,scenarios,active_deck,cutoff)
scenario_values=dict(zip(scenario_results['scenario'],scenario_results['npv_mnok'])) if not scenario_results.empty else {}

if page == 'Dashboard':
    c1,c2,c3,c4,c5,c6=st.columns(6)
    mf=money_factor(money_unit)
    c1.metric('Pre-tax NPV', f"{m['pre_tax_npv_mnok']*mf:,.2f} {money_unit}")
    c2.metric('After-tax NPV', f"{m['after_tax_npv_mnok']*mf:,.2f} {money_unit}")
    c3.metric('IRR after tax', '—' if m['irr'] is None else f"{m['irr']:.1%}")
    c4.metric('Oil breakeven', f'{deck_be:.3f}× deck' if use_deck and deck_be is not None else (f'${be:.1f}/bbl' if be is not None else '—'))
    c5.metric('MEV', '—' if mev is None else f'{mev:,.2f} MMboe')
    c6.metric('Payback', m['payback_year'] or '—')
    if cf.attrs.get('cutoff_year') is not None: st.info(f"Economic cessation: {cf.attrs.get('cutoff_year')} — {cf.attrs.get('cutoff_reason')}")
    st.caption(f"{money_basis.title()} money • entered {rate_basis} discount {disc:.2%} • effective {money_basis} discount {consistent_discount_rate(disc,rate_basis,money_basis,inflation):.2%}")
    chart_cf=cf[['year','pre_tax_cf_mnok','after_tax_cf_mnok']].copy(); chart_cf[['pre_tax_cf_mnok','after_tax_cf_mnok']]*=mf
    st.plotly_chart(px.bar(chart_cf, x='year', y=['pre_tax_cf_mnok','after_tax_cf_mnok'], barmode='group', title=f'Annual cash flow ({money_unit})'), use_container_width=True)
    cum=cf[['year','cumulative_cf_mnok','cumulative_npv_mnok']].copy(); cum[['cumulative_cf_mnok','cumulative_npv_mnok']]*=mf
    st.plotly_chart(px.line(cum,x='year',y=['cumulative_cf_mnok','cumulative_npv_mnok'],markers=True,title=f'Cumulative cash flow and NPV ({money_unit})'),use_container_width=True)
    prod=cf[['year','oil_mmbbl','gas_msm3']].copy(); prod['oil']=prod['oil_mmbbl']*oil_factor(oil_unit); prod['gas']=prod['gas_msm3']*gas_factor(gas_unit)
    st.plotly_chart(px.line(prod,x='year',y=['oil','gas'],markers=True,title=f'Production profile — oil {oil_unit}, gas {gas_unit}'),use_container_width=True)

if page == 'Production & costs':
    st.subheader('Production and cost profile')
    st.caption('Manual profile values use canonical units: oil MMbbl, gas MSm³, and costs MNOK. Changes take effect only when applied.')
    with st.form('profile_manual_form'):
        edited_profile=st.data_editor(st.session_state.profile,use_container_width=True,num_rows='dynamic',key='profile_editor')
        apply_manual=st.form_submit_button('Apply manual profile',type='primary')
    if apply_manual:
        try:
            st.session_state.profile=validate_profile_table(edited_profile)
            st.success('Manual profile applied.')
        except (TypeError,ValueError) as exc:
            st.error(f'Profile validation: {exc}')
    uploaded_profile=st.file_uploader('Import profile from CSV or Excel',type=['csv','xlsx','xlsm'],key='profile_upload')
    if uploaded_profile is not None:
        try:
            imported_profile=load_profile_table(uploaded_profile.getvalue(),uploaded_profile.name)
            st.dataframe(imported_profile,use_container_width=True,hide_index=True)
            if st.button('Apply imported profile',type='primary',key='apply_profile_import'):
                st.session_state.profile=imported_profile
                st.success('Imported profile applied.')
                st.rerun()
        except (TypeError,ValueError,ImportError) as exc:
            st.error(f'Could not import profile: {exc}')
    template=st.session_state.profile.iloc[:0].to_csv(index=False)
    st.download_button('Download profile CSV template',template,'profile_template.csv','text/csv')
if page == 'Economics':
    st.subheader('Economic cash-flow table')
    econ=cf.copy()
    for col in [c for c in econ.columns if c.endswith('_mnok')]: econ[col]=econ[col]*money_factor(money_unit)
    econ=econ.rename(columns={c:c.replace('_mnok',f'_{money_unit.lower()}') for c in econ.columns if c.endswith('_mnok')})
    econ=econ.drop(columns=['oil_mmbbl','gas_msm3'],errors='ignore')
    econ[f'oil_volume ({oil_unit})']=cf['oil_mmbbl']*oil_factor(oil_unit)
    econ[f'gas_volume ({gas_unit})']=cf['gas_msm3']*gas_factor(gas_unit)
    st.caption(f'Money shown in {money_unit}; oil in {oil_unit}; gas in {gas_unit}. Internal calculation basis remains MNOK / MMbbl / MSm³.')
    st.dataframe(econ.style.format(precision=2), use_container_width=True)

if page == 'Scenarios':
    st.subheader('Scenario manager')
    st.caption('Scenario factors modify the current base profile and assumptions. Each scenario exposes an NPV that can be linked to a decision-tree outcome.')
    st.session_state.scenario_table=st.data_editor(st.session_state.scenario_table,num_rows='dynamic',use_container_width=True,key='scenario_editor')
    scenarios=current_scenarios()
    scenario_results, scenario_cfs=evaluate_scenarios(st.session_state.profile,a,scenarios,active_deck,cutoff)
    scenario_values=dict(zip(scenario_results['scenario'],scenario_results['npv_mnok'])) if not scenario_results.empty else {}
    st.dataframe(scenario_results,use_container_width=True,hide_index=True)
    if not scenario_results.empty:
        st.plotly_chart(px.bar(scenario_results,x='scenario',y='npv_mnok',title='Scenario NPV'),use_container_width=True)

if page == 'Uncertainty':
    st.subheader('Monte Carlo uncertainty')
    st.caption('Choose marginal distributions and correlations. Correlated samples are generated with a Gaussian copula.')
    dists=['lognormal','normal','triangular']
    c1,c2,c3,c4,c5=st.columns(5)
    oil_sig=c1.number_input('Oil σ (%)',0.,100.,20.)/100; oil_dist=c1.selectbox('Oil distribution',dists,key='oil_dist')
    gas_sig=c2.number_input('Gas σ (%)',0.,100.,20.)/100; gas_dist=c2.selectbox('Gas distribution',dists,key='gas_dist')
    cap_sig=c3.number_input('CAPEX σ (%)',0.,100.,20.)/100; cap_dist=c3.selectbox('CAPEX distribution',dists,key='cap_dist')
    op_sig=c4.number_input('OPEX σ (%)',0.,100.,15.)/100; op_dist=c4.selectbox('OPEX distribution',dists,key='op_dist')
    prod_sig=c5.number_input('Production σ (%)',0.,100.,15.)/100; prod_dist=c5.selectbox('Production distribution',dists,key='prod_dist')
    r1,r2,r3=st.columns(3)
    price_corr=r1.slider('Oil ↔ gas correlation',-.9,.9,.35,.05)
    cost_corr=r2.slider('CAPEX ↔ OPEX correlation',-.9,.9,.40,.05)
    resource_cost_corr=r3.slider('Production ↔ CAPEX correlation',-.9,.9,.15,.05)
    u=Uncertainty(oil_sig,gas_sig,cap_sig,op_sig,prod_sig,oil_dist,gas_dist,cap_dist,op_dist,prod_dist,price_corr,cost_corr,resource_cost_corr)
    iterations=st.slider('Iterations',500,10000,2000,500); seed=st.number_input('Random seed',0,999999,42)
    if st.button('Run Monte Carlo', type='primary', key='run_mc'):
        samples,factors=run_monte_carlo(st.session_state.profile,a,u,iterations,int(seed),return_factors=True)
        st.session_state.mc_samples=samples; st.session_state.mc_factors=factors
    if 'mc_samples' in st.session_state:
        samples=st.session_state.mc_samples; factors=st.session_state.get('mc_factors'); ms=mc_summary(samples)
        x1,x2,x3,x4,x5=st.columns(5)
        x1.metric('P10',f"{ms['P10']:,.0f} MNOK"); x2.metric('P50',f"{ms['P50']:,.0f} MNOK"); x3.metric('P90',f"{ms['P90']:,.0f} MNOK"); x4.metric('Mean',f"{ms['mean']:,.0f} MNOK"); x5.metric('P(NPV > 0)',f"{ms['prob_npv_positive']:.1%}")
        st.plotly_chart(px.histogram(x=samples,nbins=60,labels={'x':'NPV (MNOK)'},title='NPV distribution'),use_container_width=True)
        with st.expander('Correlation / sample diagnostics'):
            st.write('Target factor correlation matrix'); st.dataframe(pd.DataFrame(correlation_matrix(u),index=['Oil','Gas','CAPEX','OPEX','Production'],columns=['Oil','Gas','CAPEX','OPEX','Production']))
            if factors is not None: st.write('Realized sampled-factor correlation'); st.dataframe(factors.corr())
    else:
        st.info('Set the uncertainty assumptions, then run Monte Carlo. Results are retained while you navigate between modules.')

if page == 'Sensitivity & breakeven':
    st.subheader('Sensitivity, tornado & breakeven')
    tdf, base_npv = tornado(st.session_state.profile,a,market_deck=active_deck,cutoff=cutoff)
    fig=go.Figure()
    fig.add_bar(y=tdf['variable'],x=tdf['low_delta']*money_factor(money_unit),orientation='h',name='Low case')
    fig.add_bar(y=tdf['variable'],x=tdf['high_delta']*money_factor(money_unit),orientation='h',name='High case')
    fig.update_layout(barmode='overlay',title=f'Tornado — change in NPV ({money_unit})',xaxis_title=f'ΔNPV ({money_unit})')
    st.plotly_chart(fig,use_container_width=True)

    c1,c2=st.columns(2)
    with c1:
        variable=st.selectbox('Sensitivity curve variable',['Oil price','Gas price','Production','CAPEX','OPEX'])
        curve=sensitivity_curve(st.session_state.profile,a,variable,market_deck=active_deck,cutoff=cutoff)
        curve['npv_display']=curve['npv_mnok']*money_factor(money_unit)
        figc=px.line(curve,x='change_pct',y='npv_display',markers=True,title=f'{variable} sensitivity curve')
        figc.add_hline(y=0,line_dash='dash'); figc.update_xaxes(title='Change from base (%)'); figc.update_yaxes(title=f'NPV ({money_unit})')
        st.plotly_chart(figc,use_container_width=True)
    with c2:
        if use_deck:
            deck_table=breakeven_table(st.session_state.profile,a,active_deck,cutoff=cutoff)
            oil_row=deck_table[deck_table['variable']=='Oil price'].iloc[0]
            if pd.isna(oil_row['breakeven_factor']): st.metric('Oil-deck breakeven','Outside search range')
            else: st.metric('Oil-deck breakeven',f"{oil_row['breakeven_factor']:.3f}× ({oil_row['breakeven_change_pct']:+.1f}%)")
            st.caption('With a market deck enabled, breakeven is a uniform multiplier applied to every annual oil-price point.')
        else:
            st.metric('Oil-price breakeven','Outside search range' if be is None else f'${be:,.2f}/bbl')
            if be is not None:
                prices=np.linspace(max(0,be*.45),max(be*1.65,oil*1.4,20),31)
                rows=[]
                for price in prices:
                    aa=Assumptions(**{**a.__dict__,'oil_price_usd_bbl':float(price)})
                    rows.append({'oil_price':price,'npv':metrics(calculate_cashflow(st.session_state.profile,aa,cutoff=cutoff))['npv_mnok']*money_factor(money_unit)})
                bedf=pd.DataFrame(rows)
                figb=px.line(bedf,x='oil_price',y='npv',title='Oil-price breakeven curve')
                figb.add_hline(y=0,line_dash='dash'); figb.add_vline(x=be,line_dash='dash'); figb.update_xaxes(title='Oil price (USD/bbl)'); figb.update_yaxes(title=f'NPV ({money_unit})')
                st.plotly_chart(figb,use_container_width=True)

        st.metric('Minimum economic volume (MMboe)','—' if mev is None else f'{mev:,.2f}')

    st.subheader('Value bridge / waterfall')
    wf=npv_waterfall(cf); labels=list(wf); values=[wf[k]*money_factor(money_unit) for k in labels]
    figw=go.Figure(go.Waterfall(name='Project value',orientation='v',measure=['relative']*len(values)+['total'],x=labels+['Undiscounted after-tax cash flow'],y=values+[0],connector={'line':{'width':1}}))
    figw.update_layout(title=f'Undiscounted project cash-flow bridge ({money_unit})',yaxis_title=money_unit)
    st.plotly_chart(figw,use_container_width=True)
    st.caption('The bridge reconciles undiscounted revenue, costs and tax. NPV additionally reflects timing through discounting.')

if page == 'Decision tree':
    st.subheader('Decision tree + scenario economics')
    default_tree={'nodes':[{'id':'n1','type':'decision','label':'Development concept','x':50,'y':220},{'id':'n2','type':'chance','label':'Resource outcome','x':300,'y':100},{'id':'n3','type':'outcome','label':'High','scenario_key':'High resource','value':0,'x':560,'y':40},{'id':'n4','type':'outcome','label':'Low','scenario_key':'Low resource','value':0,'x':560,'y':220},{'id':'n5','type':'outcome','label':'Base','scenario_key':'Base','value':0,'x':300,'y':390}], 'edges':[{'id':'e1','source':'n1','target':'n2','label':'Develop'},{'id':'e2','source':'n2','target':'n3','probability':0.35},{'id':'e3','source':'n2','target':'n4','probability':0.65},{'id':'e4','source':'n1','target':'n5','label':'Base'}]}
    if 'decision_tree' not in st.session_state: st.session_state.decision_tree=default_tree
    edited=decision_tree(st.session_state.decision_tree,scenario_values,key='economic_decision_tree')
    if edited: st.session_state.decision_tree=edited
    try:
        tr=evaluate_tree(st.session_state.decision_tree,scenario_values)
        c1,c2=st.columns(2); c1.metric('Current decision-tree value',f"{tr['value']:,.0f} MNOK"); c2.write('Selected decision edges: '+(', '.join(tr['selected_edges']) or '—'))
        for w in tr['warnings']: st.warning(w)
    except Exception as exc: st.error(f'Tree evaluation error: {exc}')
    with st.expander('Scenario values feeding outcome nodes'):
        st.dataframe(pd.DataFrame([{'scenario_key':k,'current_npv_mnok':v} for k,v in scenario_values.items()]),use_container_width=True,hide_index=True)
        st.json(st.session_state.decision_tree)
    st.markdown('**Decision-tree Monte Carlo**')
    tree_iterations=st.slider('Tree simulation iterations',250,5000,1000,250,key='tree_iterations')
    tree_u=Uncertainty(.20,.20,.20,.15,.15,'lognormal','lognormal','lognormal','lognormal','lognormal',.35,.40,.15)
    tree_seed=st.number_input('Tree random seed',0,999999,42,key='tree_seed')
    if st.button('Run decision-tree simulation',type='primary'):
        tv,sv,tf=run_tree_monte_carlo(st.session_state.profile,a,scenarios,st.session_state.decision_tree,tree_u,tree_iterations,int(tree_seed))
        st.session_state.tree_mc=tv
    if 'tree_mc' in st.session_state:
        tms=mc_summary(st.session_state.tree_mc); z1,z2,z3,z4=st.columns(4)
        z1.metric('Tree P10',f"{tms['P10']:,.0f} MNOK"); z2.metric('Tree P50',f"{tms['P50']:,.0f} MNOK"); z3.metric('Tree P90',f"{tms['P90']:,.0f} MNOK"); z4.metric('P(value > 0)',f"{tms['prob_npv_positive']:.1%}")
        st.plotly_chart(px.histogram(x=st.session_state.tree_mc,nbins=50,labels={'x':'Decision-tree value (MNOK)'},title='Decision-tree value distribution'),use_container_width=True)

if page == 'Data / audit':
    st.download_button('Download cash flow CSV',cf.to_csv(index=False),'cashflow.csv','text/csv')
    st.download_button('Download scenarios CSV',scenario_results.to_csv(index=False),'scenarios.csv','text/csv')
    st.json({'assumptions':a.__dict__,'display_units':{'money':money_unit,'oil':oil_unit,'gas':gas_unit},'effective_discount_rate':consistent_discount_rate(disc,rate_basis,money_basis,inflation),'metrics':m,'oil_breakeven_usd_bbl':be,'market_deck_enabled':use_deck,'scenario_npvs':scenario_values,'theme':theme_name,'attribution':{'author':'Merouane Hamdani','purpose':'Educational purposes only — non-commercial'}})


if page == 'Market & advanced':
    st.subheader('Market decks & advanced analysis')
    st.caption('Edit annual oil, gas and FX assumptions. When “Use annual market deck” is enabled, these curves drive the core cash-flow calculation.')
    deck_issues=validate_market_deck(st.session_state.market_deck)
    st.session_state.market_deck=st.data_editor(st.session_state.market_deck,use_container_width=True,num_rows='dynamic',key='market_deck_editor')
    if deck_issues:
        for issue in deck_issues: st.warning(issue)
    else:
        md=st.session_state.market_deck.copy()
        figm=go.Figure(); figm.add_trace(go.Scatter(x=md.year,y=md.oil_usd_bbl,name='Oil USD/bbl')); figm.add_trace(go.Scatter(x=md.year,y=md.usd_nok,name='USD/NOK',yaxis='y2'))
        figm.update_layout(title='Oil price and FX deck',yaxis_title='USD/bbl',yaxis2=dict(title='USD/NOK',overlaying='y',side='right'))
        st.plotly_chart(figm,use_container_width=True)
        st.plotly_chart(px.line(md,x='year',y='gas_usd_sm3',markers=True,title='Gas price deck (USD/Sm³)'),use_container_width=True)

    st.markdown('### Spider sensitivity')
    sp=spider(st.session_state.profile,a,active_deck,cutoff=cutoff)
    figsp=px.line(sp,x='change_pct',y='npv_mnok',color='variable',markers=True,title='NPV spider plot')
    figsp.add_hline(y=0,line_dash='dash'); figsp.update_xaxes(title='Input change (%)'); figsp.update_yaxes(title='NPV (MNOK)')
    st.plotly_chart(figsp,use_container_width=True)

    st.markdown('### Multi-variable breakeven')
    bet=breakeven_table(st.session_state.profile,a,active_deck,cutoff=cutoff)
    st.dataframe(bet.style.format({'breakeven_factor':'{:.3f}','breakeven_change_pct':'{:.1f}%'}),use_container_width=True,hide_index=True)
    available=bet.dropna(subset=['breakeven_change_pct'])
    if not available.empty:
        st.plotly_chart(px.bar(available,x='variable',y='breakeven_change_pct',title='Change required to reach NPV = 0',labels={'breakeven_change_pct':'Change from base (%)'}),use_container_width=True)

    cA,cB=st.columns(2)
    with cA:
        st.markdown('### Revenue stack')
        rev=cf[['year','oil_revenue_mnok','gas_revenue_mnok']].copy(); rev[['oil_revenue_mnok','gas_revenue_mnok']]*=money_factor(money_unit)
        st.plotly_chart(px.area(rev,x='year',y=['oil_revenue_mnok','gas_revenue_mnok'],title=f'Stacked revenue ({money_unit})'),use_container_width=True)
    with cB:
        st.markdown('### Tax bridge')
        tb=tax_bridge(cf); tb['value']=tb['value_mnok']*money_factor(money_unit)
        measures=['absolute']+['relative']*(max(len(tb)-2,0))+['total'] if len(tb)>1 else ['absolute']
        figtb=go.Figure(go.Waterfall(x=tb['component'],y=tb['value'],measure=measures))
        figtb.update_layout(title=f'Pre-tax to after-tax bridge ({money_unit})',yaxis_title=money_unit)
        st.plotly_chart(figtb,use_container_width=True)

    st.markdown('### Probability / S-curve')
    if 'mc_samples' in st.session_state:
        exc=exceedance_curve(st.session_state.mc_samples)
        st.plotly_chart(px.line(exc,x='npv_mnok',y='exceedance_pct',title='NPV exceedance curve',labels={'npv_mnok':'NPV (MNOK)','exceedance_pct':'Probability of exceedance (%)'}),use_container_width=True)
    else: st.info('Run Monte Carlo on the Uncertainty tab to populate the NPV S-curve.')

    st.markdown('### Excel model export')
    wb=excel_workbook(a,st.session_state.profile,cf,st.session_state.market_deck,scenario_results,st.session_state.get('mc_samples'),{'author':'Merouane Hamdani','purpose':'Educational purposes only — non-commercial','money_basis':money_basis,'display_money_unit':money_unit})
    st.download_button('Download analysis workbook (.xlsx)',wb,'ncs_economics_analysis.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


if page == 'Decision studio':
    st.subheader('Decision studio')
    st.caption('Cutoff-aware development concepts, generated production profiles, expanded breakevens, and value-of-information analysis.')
    st.markdown('### Production profile generator')
    g1,g2,g3,g4=st.columns(4)
    gres=g1.number_input('Recoverable oil (MMbbl)',1.0,2000.0,100.0,5.0)
    gplat=g2.number_input('Oil plateau (MMbbl/year)',.1,200.0,12.0,.5)
    gdecl=g3.number_input('Annual decline (%)',0.0,80.0,15.0,1.0)/100
    glife=g4.number_input('Profile periods',5,60,20,1)
    generated=generated_profile(int(st.session_state.profile.year.min()),int(glife),float(gres),float(gplat),250.0,2,4,float(gdecl),float(st.session_state.profile.capex_mnok.sum()),float(st.session_state.profile.opex_mnok[st.session_state.profile.opex_mnok>0].median() or 0),float(st.session_state.profile.decom_mnok.sum()))
    st.plotly_chart(px.line(generated,x='year',y=['oil_mmbbl','gas_msm3'],title='Generated ramp / plateau / decline profile'),use_container_width=True)
    if st.button('Use generated profile as project profile'):
        st.session_state.profile=generated; st.rerun()

    st.markdown('### Development concept comparison')
    if 'concept_table' not in st.session_state:
        st.session_state.concept_table=pd.DataFrame([
            {'name':'Subsea tie-back','capex_factor':.75,'opex_factor':.85,'production_factor':.90,'schedule_shift_years':-1},
            {'name':'FPSO','capex_factor':1.0,'opex_factor':1.0,'production_factor':1.0,'schedule_shift_years':0},
            {'name':'Fixed platform','capex_factor':1.30,'opex_factor':.90,'production_factor':1.12,'schedule_shift_years':1}])
    st.session_state.concept_table=st.data_editor(st.session_state.concept_table,num_rows='dynamic',use_container_width=True,key='concept_editor')
    concepts=[]
    for r in st.session_state.concept_table.to_dict('records'):
        try: concepts.append(DevelopmentConcept(**r))
        except (TypeError,ValueError): pass
    concept_results=compare_concepts(st.session_state.profile,a,concepts,active_deck,cutoff) if concepts else pd.DataFrame()
    st.dataframe(concept_results,use_container_width=True,hide_index=True)
    if not concept_results.empty: st.plotly_chart(px.bar(concept_results,x='concept',y='npv_mnok',title='Cutoff-aware concept NPV'),use_container_width=True)

    st.markdown('### Expanded cutoff-aware breakevens')
    v9be=breakeven_suite(st.session_state.profile,a,active_deck,cutoff)
    st.dataframe(v9be,use_container_width=True,hide_index=True)

    st.markdown('### Value of information — appraisal example')
    v1,v2,v3=st.columns(3)
    p_high=v1.slider('Probability high resource',.01,.99,.40,.01); info_cost=v2.number_input('Information cost (MNOK)',0.0,10000.0,400.0,50.0); accuracy=v3.slider('Appraisal signal accuracy',.50,.99,.80,.01)
    # Alternatives: do not develop vs develop; states: low/high. Editable economic payoffs keep VOI transparent.
    q1,q2=st.columns(2); low_value=q1.number_input('Develop payoff — low state (MNOK)',-50000.0,100000.0,-2000.0,250.0); high_value=q2.number_input('Develop payoff — high state (MNOK)',-50000.0,100000.0,12000.0,250.0)
    payoffs=np.array([[0.0,0.0],[low_value,high_value]]); probs=np.array([1-p_high,p_high]); likelihood=np.array([[accuracy,1-accuracy],[1-accuracy,accuracy]])
    vi=evpi_from_payoffs(payoffs,probs); vsi=evsi_from_signals(payoffs,probs,likelihood,info_cost)
    z1,z2,z3,z4=st.columns(4); z1.metric('Current EV',f"{vi['current_ev']:,.0f} MNOK"); z2.metric('EVPI',f"{vi['evpi']:,.0f} MNOK"); z3.metric('EVSI',f"{vsi['evsi']:,.0f} MNOK"); z4.metric('Net VOI',f"{vsi['net_value_of_information']:,.0f} MNOK")
    st.caption('EVPI is the ceiling on information value. EVSI reflects the specified signal accuracy; Net VOI subtracts appraisal/information cost.')

    st.markdown('### Cutoff audit')
    st.json({'mode':cutoff.mode,'cessation_year':cf.attrs.get('cutoff_year'),'reason':cf.attrs.get('cutoff_reason'),'consecutive_negative_periods':cutoff.consecutive_negative_periods,'lookahead_periods':cutoff.lookahead_periods,'minimum_oil_mmbbl':cutoff.minimum_oil_mmbbl,'minimum_gas_msm3':cutoff.minimum_gas_msm3,'decommissioning_lag_periods':cutoff.decom_lag_periods})

if page == 'Analysis studio':
    st.subheader('Analysis studio')
    st.caption('One workspace for timing, reserves, named decks, breakevens, concepts, uncertainty and fiscal diagnostics. All economics here use the selected cutoff rule.')
    r1,r2,r3,r4=st.columns(4)
    r1.metric('Resolution',time_resolution.title()); r2.metric('Periods',f'{len(cf):,}'); r3.metric('Government take', '—' if not np.isfinite(government_take(cf)) else f'{government_take(cf):.1%}'); r4.metric('Cessation',cf.attrs.get('cutoff_year') or 'Not triggered')
    st.markdown('### Reserves-driven production')
    q1,q2,q3,q4,q5=st.columns(5)
    stoiip=q1.number_input('STOIIP (MMbbl)',10.,10000.,250.,10.); rf=q2.number_input('Recovery factor (%)',1.,90.,40.,1.)/100
    plateau=q3.number_input('Facility oil capacity (MMbbl/y)',.1,500.,15.,.5); uptime=q4.number_input('Uptime (%)',10.,100.,95.,1.)/100; gor=q5.number_input('Gas/oil ratio (MSm³/MMbbl)',0.,1000.,20.,1.)
    rp=reserves_profile(int(st.session_state.profile.year.min()),stoiip,rf,plateau,gas_oil_ratio_msm3_per_mmbbl=gor,uptime=uptime,facility_capacity_mmbbl=plateau)
    st.plotly_chart(px.area(rp,x='year',y=['oil_mmbbl','gas_msm3'],title='Reserves-constrained production profile'),use_container_width=True)
    st.caption(f"Recoverable oil = {rp.recoverable_oil_mmbbl.iloc[0]:,.1f} MMbbl; generated cumulative oil = {rp.oil_mmbbl.sum():,.1f} MMbbl.")

    st.markdown('### Named market decks')
    decks=named_decks(sorted(st.session_state.profile.year.astype(int).unique()),oil,gas,fx)
    deck_name=st.radio('Deck',['Low','Base','High'],horizontal=True,key='v10_deck')
    selected=select_deck(decks,deck_name)
    st.plotly_chart(px.line(selected,x='year',y=['oil_usd_bbl','usd_nok'],markers=True,title=f'{deck_name} market deck'),use_container_width=True)

    st.markdown('### Configurable analysis')
    a1,a2=st.columns(2); studio_var=a1.selectbox('X variable',['Oil price','Gas price','FX','Production / reserves','CAPEX','OPEX','Discount rate','Start delay']); studio_metric=a2.selectbox('Metric',['npv_mnok','irr','undiscounted_after_tax_mnok','unit_cost_nok_boe'])
    sc=studio_curve(active_profile,a,studio_var,studio_metric,deck=active_deck,cutoff=cutoff)
    st.plotly_chart(px.line(sc,x='change_pct',y='value',markers=True,title=f'{studio_metric} vs {studio_var}'),use_container_width=True)

    st.markdown('### Full cutoff-aware breakeven suite')
    st.dataframe(extended_breakeven_suite(active_profile,a,active_deck,cutoff),use_container_width=True,hide_index=True)

    st.markdown('### Uncertainty diagnostics')
    if 'mc_samples' in st.session_state:
        ud,uc=uncertainty_diagnostics(st.session_state.mc_samples)
        u1,u2,u3,u4=st.columns(4); u1.metric('P(NPV < 0)',f"{ud['prob_negative']:.1%}"); u2.metric('P10',f"{ud['P10']:,.0f} MNOK"); u3.metric('P90',f"{ud['P90']:,.0f} MNOK"); u4.metric('Downside tail mean',f"{ud['downside_p10_mean']:,.0f} MNOK")
        if uc is not None: st.dataframe(uc.rename('NPV correlation').to_frame(),use_container_width=True)
    else: st.info('Run Monte Carlo first to populate downside and driver diagnostics.')

if page == 'Projects & reports':
    st.subheader('Projects & reports')
    project_name=st.text_input('Project name','NCS Development Case')
    version_name=st.text_input('Snapshot label','Baseline')
    if 'snapshots' not in st.session_state: st.session_state.snapshots=[]
    if st.button('Create economics snapshot'):
        st.session_state.snapshots.append(snapshot(project_name,version_name,m).__dict__)
    if st.session_state.snapshots: st.dataframe(pd.DataFrame(st.session_state.snapshots),use_container_width=True)
    st.download_button('Download version history (.json)',dumps_snapshots(st.session_state.snapshots),'project_versions.json','application/json')
    report=decision_report_text(project_name,m,cf.attrs.get('cutoff_year'),cf.attrs.get('cutoff_reason'),st.session_state.get('concept_table'))
    st.download_button('Download investment-decision summary (.md)',report,'investment_decision_summary.md','text/markdown')
    project_bytes=dumps_project(st.session_state.profile,a,st.session_state.scenario_table,st.session_state.get('decision_tree',{}),{'author':'Merouane Hamdani','purpose':'Educational purposes only — non-commercial','app_version':'V12.2-audit-fix'},st.session_state.market_deck,st.session_state.get('concept_table'),{'time_resolution':time_resolution,'capex_phasing':capex_phasing,'cutoff':cutoff.__dict__},st.session_state.snapshots)
    st.download_button('Save complete project (.json)',project_bytes,'ncs_project.json','application/json')
    uploaded=st.file_uploader('Load V9/V10/V11/V11.1/V12/V12.1 project JSON',type=['json'])
    if uploaded is not None:
        try:
            loaded=loads_project(uploaded); st.success(f"Project schema {loaded['schema_version']} validated.")
            st.json({'metadata':loaded.get('metadata',{}),'settings':loaded.get('settings',{}),'snapshots':loaded.get('snapshots',[])})
            if st.button('Apply loaded project',type='primary',key='apply_loaded_project'):
                loaded['profile']=validate_profile_table(loaded['profile']).to_dict('records')
                st.session_state._pending_project_import=loaded
                st.rerun()
        except Exception as e: st.error(f'Could not load project: {e}')

if page == 'Exploration & portfolio':
    st.subheader('Exploration + development decision system')
    st.caption('Risk prospects, quantify schedule/commercial exposure, manage decision gates, screen constrained portfolios, and run model-assurance checks.')
    e1,e2=st.columns(2)
    with e1:
        st.markdown('### Exploration risking')
        cos=st.slider('Geological chance of success',0.01,0.99,0.30,0.01)
        dry=st.number_input('Dry-hole cost (MNOK)',0.0,20000.0,900.0,50.0)
        small=st.number_input('Small discovery development NPV (MNOK)',-50000.0,100000.0,1500.0,100.0)
        large=st.number_input('Large discovery development NPV (MNOK)',-50000.0,200000.0,12000.0,250.0)
        pe=prospect_emv(cos,dry,[DiscoveryCase('Small',.55,small),DiscoveryCase('Large',.45,large)])
        st.metric('Risked exploration EMV',f"{pe['risked_emv_mnok']:,.0f} MNOK")
        st.dataframe(pd.DataFrame(discovery_distribution(cos,dry,[DiscoveryCase('Small',.55,small),DiscoveryCase('Large',.45,large)])),hide_index=True,use_container_width=True)
    with e2:
        st.markdown('### Schedule risk')
        stages=[{'name':'Approvals','min_months':0,'mode_months':2,'max_months':8},{'name':'Drilling','min_months':0,'mode_months':3,'max_months':12},{'name':'Construction','min_months':0,'mode_months':4,'max_months':18},{'name':'Commissioning','min_months':0,'mode_months':1,'max_months':6}]
        if st.button('Run schedule risk simulation', key='run_schedule_risk'):
            st.session_state.schedule_risk_samples=simulate_schedule_risk(stages,2000,42,max(abs(m.get('npv_mnok',0))*.002,1.0))
        if 'schedule_risk_samples' in st.session_state:
            sr=st.session_state.schedule_risk_samples; ss=schedule_summary(sr)
            st.dataframe(pd.DataFrame([ss]),hide_index=True,use_container_width=True)
            st.plotly_chart(px.histogram(sr,x='total_delay_months',nbins=35,title='First-production delay distribution'),use_container_width=True)
        else:
            st.info('Run the schedule risk simulation to view the first-production delay distribution.')
    st.markdown('### Decision gates')
    gates=[DecisionGate('Discovery','Complete',pe['risked_emv_mnok'],dry),DecisionGate('Appraisal','Open',max(pe['success_case_ev_mnok'],0),400),DecisionGate('Concept Select','Open',m.get('npv_mnok',0),250),DecisionGate('FEED','Open',m.get('npv_mnok',0),600),DecisionGate('FID','Open',m.get('npv_mnok',0),0)]
    st.dataframe(pd.DataFrame(gate_register(gates)),hide_index=True,use_container_width=True)
    st.markdown('### Illustrative constrained portfolio')
    projects=[{'name':'Current project','value_mnok':float(m.get('npv_mnok',0)),'annual_capex':{int(years[0]):float(st.session_state.profile.capex_mnok.iloc[0])}},{'name':'Prospect option','value_mnok':float(pe['risked_emv_mnok']),'annual_capex':{int(years[0]):dry}}]
    limit=st.number_input('First-year portfolio CAPEX limit (MNOK)',0.0,100000.0,5000.0,250.0)
    st.json(optimize_portfolio(projects,{int(years[0]):limit}))
    st.markdown('### Model assurance')
    health=model_health(st.session_state.profile,active_deck,[.55,.45],{'cessation_year':cf.attrs.get('cutoff_year'),'decom_year':None},recoverable_oil_mmbbl=float(st.session_state.profile.oil_mmbbl.sum())*1.05,money_basis=money_basis,discount_basis=rate_basis)
    st.dataframe(pd.DataFrame(health),hide_index=True,use_container_width=True)

if page == 'Integrated field development':
    st.subheader('Integrated field development')
    st.caption('Editable resources → wells → facilities → schedule → multi-currency costs → emissions → uncertainty → project-linked decisions → validation.')

    c1,c2,c3,c4=st.columns(4)
    stoiip=c1.number_input('STOIIP (MMbbl)',0.0,5000.0,250.0,10.0,key='v12_stoiip')
    rf=c2.slider('Oil recovery factor',0.0,0.8,0.35,0.01,key='v12_rf')
    facrate=c3.number_input('Facility oil capacity (kbopd)',0.0,500.0,70.0,5.0,key='v12_fac')
    uptime=c4.slider('Facility uptime',0.10,1.0,0.95,0.01,key='v12_uptime')

    if 'v12_well_table' not in st.session_state:
        st.session_state.v12_well_table=pd.DataFrame([
            {'name':f'P{i+1}','onstream_year':2029+i//2,'onstream_month':1 if i%2==0 else 7,'oil_kbopd':15.0,'gas_msm3_day':0.0}
            for i in range(6)])
    st.markdown('### Wells & physical constraints')
    st.session_state.v12_well_table=st.data_editor(st.session_state.v12_well_table,num_rows='dynamic',use_container_width=True,key='v12_well_editor')
    wells=[]
    for r in st.session_state.v12_well_table.to_dict('records'):
        try:
            wells.append({'onstream_year':int(r['onstream_year']),'onstream_month':int(r.get('onstream_month',1)),'oil_kbopd':float(r.get('oil_kbopd',0)),'gas_msm3_day':float(r.get('gas_msm3_day',0))})
        except (TypeError,ValueError,KeyError): pass
    period_cols=[c for c in ['year','period','periods_per_year'] if c in active_profile.columns]
    phys=integrated_profile(active_profile[period_cols],ResourceCase(stoiip,rf),wells,FacilityLimits(oil_kbopd=facrate,uptime=uptime))
    rr=recoverable_resources(ResourceCase(stoiip,rf))
    k1,k2,k3=st.columns(3); k1.metric('Technical recoverable oil',f"{rr['oil_mmbbl']:,.1f} MMbbl"); k2.metric('Produced in horizon',f"{phys.oil_mmbbl.sum():,.1f} MMbbl"); k3.metric('Remaining / stranded',f"{phys.remaining_oil_mmbbl.iloc[-1]:,.1f} MMbbl")
    xaxis='period' if 'period' in phys.columns else 'year'
    st.plotly_chart(px.line(phys,x=xaxis,y=['oil_mmbbl','well_oil_capacity_mmbbl','facility_oil_capacity_mmbbl'],title='Oil production and constraints'),use_container_width=True)
    if st.button('Apply integrated production to project profile',key='v12_apply_physical'):
        annual=phys.groupby('year',as_index=False)[['oil_mmbbl','gas_msm3']].sum()
        base=st.session_state.profile.drop(columns=['oil_mmbbl','gas_msm3'],errors='ignore').merge(annual,on='year',how='left')
        base[['oil_mmbbl','gas_msm3']]=base[['oil_mmbbl','gas_msm3']].fillna(0.0)
        st.session_state.profile=base; st.success('Integrated physical production applied to the project profile.'); st.rerun()

    st.markdown('### Emissions economics')
    e1,e2,e3=st.columns(3); intensity=e1.number_input('CO₂ intensity (kg/boe)',0.0,200.0,18.0,1.0,key='v12_co2'); carbon=e2.number_input('Carbon price (NOK/t)',0.0,10000.0,1000.0,100.0,key='v12_carbon'); reduction=e3.slider('Electrification reduction',0.0,1.0,0.0,.05,key='v12_elec')
    em=emissions_economics(phys,intensity,carbon,reduction)
    q1,q2=st.columns(2); q1.metric('Lifecycle CO₂',f"{em.co2_tonnes.sum()/1e6:,.2f} Mt"); q2.metric('Carbon cost',f"{em.carbon_cost_mnok.sum():,.0f} MNOK")

    st.markdown('### Development schedule')
    if 'v12_schedule_table' not in st.session_state:
        st.session_state.v12_schedule_table=pd.DataFrame([
            {'name':'FEED','start_year':2027.0,'duration_months':12.0,'depends_on':''},
            {'name':'FID','start_year':2028.0,'duration_months':3.0,'depends_on':'FEED'},
            {'name':'Facilities','start_year':2028.25,'duration_months':21.0,'depends_on':'FID'},
            {'name':'Drilling','start_year':2028.25,'duration_months':21.0,'depends_on':'FID'}])
    st.session_state.v12_schedule_table=st.data_editor(st.session_state.v12_schedule_table,num_rows='dynamic',use_container_width=True,key='v12_schedule_editor')
    acts=[]
    for r in st.session_state.v12_schedule_table.to_dict('records'):
        try:
            deps=[x.strip() for x in str(r.get('depends_on','')).split(',') if x.strip()]
            acts.append({'name':str(r['name']),'start_month':float(r['start_year'])*12.0,'duration_months':float(r['duration_months']),'depends_on':deps})
        except (TypeError,ValueError,KeyError): pass
    sched_issues=validate_schedule(acts)
    if sched_issues:
        for issue in sched_issues: st.error(issue)
    elif st.button('Run schedule simulation',key='v12_run_schedule'):
        st.session_state.v12_schedule_samples=simulate_schedule(acts,1000,42)
    if 'v12_schedule_samples' in st.session_state:
        sched=st.session_state.v12_schedule_samples; st.caption(f"P50 simulated completion: {sched.first_oil.median():.2f}"); st.plotly_chart(px.histogram(sched,x='first_oil',nbins=30,title='Schedule completion distribution'),use_container_width=True)

    st.markdown('### Multi-currency cost breakdown')
    if 'v12_fxdeck' not in st.session_state: st.session_state.v12_fxdeck=pd.DataFrame({'year':[2028,2029,2030],'USD':[10.5]*3,'EUR':[11.5]*3,'GBP':[13.5]*3})
    if 'v12_costlines' not in st.session_state: st.session_state.v12_costlines=pd.DataFrame([
        {'year':2028,'category':'Wells','currency':'USD','amount':250e6},{'year':2029,'category':'Subsea/SURF','currency':'EUR','amount':300e6},{'year':2030,'category':'Host modifications','currency':'NOK','amount':2500e6}])
    fxcol,costcol=st.columns(2)
    with fxcol: st.caption('FX deck — NOK per currency unit'); st.session_state.v12_fxdeck=st.data_editor(st.session_state.v12_fxdeck,num_rows='dynamic',use_container_width=True,key='v12_fx_editor')
    with costcol: st.caption('Cost lines'); st.session_state.v12_costlines=st.data_editor(st.session_state.v12_costlines,num_rows='dynamic',use_container_width=True,key='v12_cost_editor')
    try:
        cfx=convert_cost_lines(st.session_state.v12_costlines.to_dict('records'),st.session_state.v12_fxdeck); st.dataframe(cfx,use_container_width=True,hide_index=True); st.metric('Structured CAPEX',f"{cfx.cost_mnok.sum():,.0f} MNOK")
    except Exception as exc: st.error(f'Cost/FX validation: {exc}'); cfx=pd.DataFrame()

    st.markdown('### Uncertainty register')
    if 'v12_register' not in st.session_state: st.session_state.v12_register=pd.DataFrame([
        {'name':'STOIIP','distribution':'lognormal','median':stoiip,'sigma':.15,'low':np.nan,'mode':np.nan,'high':np.nan},
        {'name':'Recovery factor','distribution':'triangular','median':np.nan,'sigma':np.nan,'low':max(0,rf-.08),'mode':rf,'high':min(1,rf+.08)},
        {'name':'Uptime','distribution':'uniform','median':np.nan,'sigma':np.nan,'low':.88,'mode':np.nan,'high':.98}])
    st.session_state.v12_register=st.data_editor(st.session_state.v12_register,num_rows='dynamic',use_container_width=True,key='v12_register_editor')
    reg=[]
    for r in st.session_state.v12_register.to_dict('records'):
        reg.append({k:v for k,v in r.items() if not (isinstance(v,float) and np.isnan(v))})
    corr=np.eye(len(reg))
    reg_issues=validate_register(reg,corr)
    if reg_issues:
        for issue in reg_issues: st.error(issue)
    elif st.button('Sample uncertainty register',key='v12_sample_register'):
        st.session_state.v12_register_samples=sample_register(reg,2000,corr,42)
    if 'v12_register_samples' in st.session_state: st.dataframe(st.session_state.v12_register_samples.describe().T,use_container_width=True)

    st.markdown('### Project-linked decision states')
    if 'v12_terminal_states' not in st.session_state: st.session_state.v12_terminal_states=pd.DataFrame([
        {'state':'High resource','production_multiplier':1.20,'capex_multiplier':1.05,'opex_multiplier':1.0,'oil_price_multiplier':1.0,'gas_price_multiplier':1.0,'fx_multiplier':1.0,'delay_months':0.0},
        {'state':'Low resource','production_multiplier':0.75,'capex_multiplier':0.95,'opex_multiplier':1.0,'oil_price_multiplier':1.0,'gas_price_multiplier':1.0,'fx_multiplier':1.0,'delay_months':0.0},
        {'state':'Base','production_multiplier':1.0,'capex_multiplier':1.0,'opex_multiplier':1.0,'oil_price_multiplier':1.0,'gas_price_multiplier':1.0,'fx_multiplier':1.0,'delay_months':0.0}])
    st.session_state.v12_terminal_states=st.data_editor(st.session_state.v12_terminal_states,num_rows='dynamic',use_container_width=True,key='v12_terminal_editor')
    if st.button('Evaluate project-linked decision tree',key='v12_eval_tree'):
        states={str(r.pop('state')):r for r in st.session_state.v12_terminal_states.to_dict('records') if r.get('state')}
        if 'decision_tree' not in st.session_state: st.warning('Create or open the Decision tree module first.')
        else:
            try:
                result,vals=evaluate_project_tree(st.session_state.decision_tree,active_profile,a,states,active_deck,cutoff); st.session_state.v12_project_tree_result={'result':result,'terminal_values':vals}
            except Exception as exc: st.error(f'Project-linked tree error: {exc}')
    if 'v12_project_tree_result' in st.session_state: st.json(st.session_state.v12_project_tree_result)

    st.markdown('### Calculation inspector & validation gate')
    idx=st.slider('Cash-flow row to inspect',0,max(len(cf)-1,0),0,key='v12_inspect'); st.json(inspect_period(cf,idx))
    checks=validate_model(st.session_state.profile,physical=phys,schedule=acts,register=reg,corr=corr,fx_deck=st.session_state.v12_fxdeck)
    st.dataframe(pd.DataFrame(checks),hide_index=True,use_container_width=True)
    if has_errors(checks): st.error('Structural model errors detected. Resolve these before relying on uncertainty results.')
    else: st.success('No structural V12 validation errors detected.')

st.divider()
st.markdown('<div style="text-align:center;opacity:.72;font-size:.82rem;padding:6px 0 18px"><b>Made by Merouane Hamdani</b> · Educational purposes only — non-commercial · NCS Economics Workbench</div>', unsafe_allow_html=True)
