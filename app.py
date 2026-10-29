import json
import io
import hashlib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from economics.engine import Assumptions, calculate_cashflow, metrics, breakeven_oil_price, minimum_economic_volume
from economics.analysis import tornado, sensitivity_curve, npv_waterfall
from economics.market import default_market_deck, validate_market_deck
from economics.advanced_analysis import (
    spider, breakeven_table, breakeven_factor, exceedance_curve, tax_bridge,
    excel_workbook, breakeven_suite, extended_breakeven_suite
)
from economics.conventions import (
    BBL_PER_SM3, money_factor, oil_factor, gas_factor, consistent_discount_rate, display_frame
)
from economics.decision_tree import evaluate_tree
from economics.scenarios import Scenario, evaluate_scenarios
from components.decision_tree_component import decision_tree
from economics.monte_carlo import (
    Uncertainty, run_monte_carlo, run_tree_monte_carlo, summary as mc_summary, correlation_matrix
)
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
from economics.assurance import model_health

st.set_page_config(page_title="NCS Economics Workbench", page_icon="🌊", layout="wide")

THEMES = {
    "McKinsey-inspired": {"bg":"#ffffff","panel":"#f3f5f7","card":"#ffffff","text":"#051c2c","muted":"#526575","accent":"#005eb8","accent2":"#00a1c9","grid":"#dce3e8","plot":"#ffffff"},
    "North Sea": {"bg":"#071923","panel":"#0d2733","card":"#123746","text":"#edf7fa","muted":"#9fc0cb","accent":"#36b7c9","accent2":"#78d6b3","grid":"#244956","plot":"#0d2733"},
    "Midnight Offshore": {"bg":"#090d18","panel":"#111827","card":"#172033","text":"#f4f7fb","muted":"#9aa7bd","accent":"#60a5fa","accent2":"#a78bfa","grid":"#29344a","plot":"#111827"},
    "Arctic Light": {"bg":"#f4f8fa","panel":"#ffffff","card":"#eaf1f4","text":"#17313b","muted":"#5e7680","accent":"#087f8c","accent2":"#287271","grid":"#d6e2e6","plot":"#ffffff"},
}

def apply_theme(name):
    t = THEMES[name]
    pio.templates["ncs_workbench"] = go.layout.Template(
        layout=go.Layout(
            paper_bgcolor=t["panel"], plot_bgcolor=t["plot"],
            font=dict(family="Segoe UI, -apple-system, BlinkMacSystemFont, sans-serif", color=t["text"], size=12),
            title=dict(font=dict(size=14, color=t["text"])),
            colorway=[t["accent"], t["accent2"], "#f59e0b", "#ec4899", "#8b5cf6", "#10b981"],
            xaxis=dict(gridcolor=t["grid"], zerolinecolor=t["grid"], title_font=dict(color=t["muted"])),
            yaxis=dict(gridcolor=t["grid"], zerolinecolor=t["grid"], title_font=dict(color=t["muted"])),
            legend=dict(bgcolor="rgba(0,0,0,0)"), margin=dict(l=45, r=25, t=60, b=40)
        )
    )
    pio.templates.default = "ncs_workbench"
    st.markdown(f"""<style>
    .stApp {{background:{t['bg']}; color:{t['text']};}}
    [data-testid="stSidebar"] {{background:{t['panel']}; border-right:1px solid {t['grid']};}}
    [data-testid="stHeader"] {{background:rgba(0,0,0,0);}}
    h1,h2,h3 {{letter-spacing:-.02em; color:{t['text']};}}
    h1 {{font-family:Georgia, 'Times New Roman', serif; font-weight:400;}}
    div[data-testid="stMetric"] {{background:{t['card']}; border:1px solid {t['grid']}; border-top:3px solid {t['accent']}; padding:16px 18px; border-radius:2px;}}
    div[data-testid="stMetricLabel"] {{color:{t['muted']};}}
    .stTabs [data-baseweb="tab-list"] {{gap:6px; border-bottom:1px solid {t['grid']};}}
    .stTabs [data-baseweb="tab"] {{border-radius:9px 9px 0 0; padding:8px 14px;}}
    .stTabs [aria-selected="true"] {{background:{t['card']}; color:{t['accent']};}}
    .ncs-hero {{padding:24px 26px; border-bottom:3px solid {t['accent']}; background:{t['panel']}; margin-bottom:24px;}}
    .ncs-kicker {{color:{t['accent']}; font-size:.78rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase;}}
    .ncs-sub {{color:{t['muted']}; margin-top:4px;}}
    [data-testid="stHorizontalBlock"] {{flex-wrap:wrap;}}
    [data-testid="column"] {{min-width:260px;}}
    .stDataFrame, [data-testid="stDataEditor"] {{overflow-x:auto;}}
    [data-testid="stWidgetLabel"], [data-testid="stCaptionContainer"], [data-testid="stMarkdownContainer"] {{color:{t['text']};}}
    [data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="input"] input {{background:{t['card']}; color:{t['text']};}}
    button[kind="primary"] {{background:{t['accent']}; color:#ffffff; border-radius:2px;}}
    button[kind="primary"] [data-testid="stMarkdownContainer"] {{color:#ffffff;}}
    @media (max-width: 900px) {{ .ncs-hero {{padding:14px 16px;}} [data-testid="column"] {{min-width:100% !important;}} }}
    .ncs-notice {{margin-top:22px; padding:12px 14px; border:1px solid {t['grid']}; border-radius:12px; color:{t['muted']}; font-size:.82rem; background:{t['card']};}}
    </style>""", unsafe_allow_html=True)

# Cache canonical results, not unit-specific presentation. All model inputs remain
# part of Streamlit's cache key, so edits invalidate the affected analyses.
calculate_cashflow = st.cache_data(show_spinner=False, max_entries=32)(calculate_cashflow)
metrics = st.cache_data(show_spinner=False, max_entries=32)(metrics)
breakeven_oil_price = st.cache_data(show_spinner=False, max_entries=32)(breakeven_oil_price)
minimum_economic_volume = st.cache_data(show_spinner=False, max_entries=32)(minimum_economic_volume)
breakeven_factor = st.cache_data(show_spinner=False, max_entries=32)(breakeven_factor)
breakeven_table = st.cache_data(show_spinner=False, max_entries=32)(breakeven_table)
extended_breakeven_suite = st.cache_data(show_spinner=False, max_entries=32)(extended_breakeven_suite)
tornado = st.cache_data(show_spinner=False, max_entries=32)(tornado)
sensitivity_curve = st.cache_data(show_spinner=False, max_entries=32)(sensitivity_curve)
spider = st.cache_data(show_spinner=False, max_entries=32)(spider)
evaluate_scenarios = st.cache_data(show_spinner=False, max_entries=32)(evaluate_scenarios)


def render_chart(figure, **kwargs):
    st.plotly_chart(figure, theme=None, **kwargs)


with st.sidebar:
    theme_name = st.selectbox("Interface theme", list(THEMES), index=0, key="theme_name")
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
    loaded = st.session_state.pop('_pending_project_import')
    st.session_state.profile = validate_profile_table(loaded['profile'])
    if loaded.get('market_deck') is not None: st.session_state.market_deck = pd.DataFrame(loaded['market_deck'])
    if loaded.get('scenarios') is not None: st.session_state.scenario_table = pd.DataFrame(loaded['scenarios'])
    if loaded.get('decision_tree') is not None: st.session_state.decision_tree = loaded['decision_tree']
    if loaded.get('concepts') is not None: st.session_state.concept_table = pd.DataFrame(loaded['concepts'])
    st.session_state.snapshots = loaded.get('snapshots', [])
    la = loaded.get('assumptions', {})
    ls = loaded.get('settings', {})
    amap = {'oil_price_usd_bbl':'assump_oil','gas_price_usd_sm3':'assump_gas','usd_nok':'assump_fx','money_basis':'assump_money_basis','base_year':'assump_base_year','discount_rate_basis':'assump_rate_basis','tax_mode':'setting_fiscal_engine'}
    for src, dst in amap.items():
        if src in la: st.session_state[dst] = la[src]
    if 'discount_rate' in la: st.session_state.assump_disc_pct = float(la['discount_rate'])*100
    if 'general_inflation' in la: st.session_state.assump_inflation_pct = float(la['general_inflation'])*100
    if 'oil_escalation' in la: st.session_state.assump_oil_esc_pct = float(la['oil_escalation'])*100
    if 'gas_escalation' in la: st.session_state.assump_gas_esc_pct = float(la['gas_escalation'])*100
    if 'cost_escalation' in la: st.session_state.assump_cost_esc_pct = float(la['cost_escalation'])*100
    if 'time_resolution' in ls: st.session_state.setting_resolution = ls['time_resolution']
    if 'capex_phasing' in ls: st.session_state.setting_capex_phasing = ls['capex_phasing']

PAGES = [
    'Dashboard',
    'Production & Economics',
    'Sensitivity & Breakeven',
    'Scenarios & Uncertainty',
    'Project & Export'
]

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
    money_unit = st.selectbox('Money', ['MNOK','BNOK','kNOK','NOK'], key='sel_money_unit')
    oil_unit = st.selectbox('Oil volume', ['MMbbl','kbbl','MSm3 oil','bbl'], key='sel_oil_unit')
    gas_unit = st.selectbox('Gas volume', ['MSm3','BCM','MMboe','kSm3','Sm3'], key='sel_gas_unit')
    st.caption('Display conversions adapt tables and charts. Internal calculation engine uses canonical units (MNOK, MMbbl, MSm³).')
    use_deck = st.toggle('Use annual market deck', value=True, help='Use editable annual oil, gas and FX curves instead of flat assumptions.', key='setting_use_deck')
    st.divider()
    st.subheader('Economic cutoff')
    st.caption('Cutoff rate inputs use canonical MMbbl and MSm3 per model period.')
    cutoff_mode = st.selectbox('Cutoff rule',['none','hard','negative_ocf','economic_limit'],format_func=lambda x:{'none':'None','hard':'Hard cutoff','negative_ocf':'Negative operating CF','economic_limit':'Economic limit / look-ahead'}[x])
    hard_year = st.number_input('Hard boundary / cutoff year',int(min(years)),int(max(years)+20),int(max(years)),1)
    neg_periods = st.number_input('Consecutive negative periods',1,10,2,1)
    lookahead = st.number_input('Economic-limit look-ahead periods',1,10,3,1)
    min_oil = st.number_input('Minimum oil rate (MMbbl/period)',0.0,100.0,0.0,.1)
    min_gas = st.number_input('Minimum gas rate (MSm³/period)',0.0,10000.0,0.0,10.0)
    decom_lag = st.number_input('Decommissioning lag (periods)',0,10,1,1)
    st.divider()
    st.subheader('Model resolution')
    time_resolution = st.selectbox('Cash-flow resolution',['annual','quarterly','monthly'],format_func=str.title,key='setting_resolution')
    capex_phasing = st.selectbox('Subannual CAPEX phasing',['even','front'],format_func=lambda x:'Even' if x=='even' else 'Front-loaded',key='setting_capex_phasing')
    fiscal_engine = st.selectbox('Fiscal engine',['ncs_v2','ncs_post_2022'],format_func=lambda x:'NCS fiscal V2' if x=='ncs_v2' else 'Legacy post-2022 baseline',key='setting_fiscal_engine')
    st.info('Fiscal calculations remain an analytical project-level model; validate vintage/company-specific tax treatment before investment decisions.')
    st.markdown('<div class="ncs-notice"><b>Made by Merouane Hamdani</b><br>For educational purposes only — non-commercial.<br><br>Not investment, tax, legal, reserves, or engineering advice.</div>', unsafe_allow_html=True)

# Build assumptions and cashflow
a = Assumptions(
    oil, gas, fx, disc, tax_mode=fiscal_engine, money_basis=money_basis,
    base_year=int(base_year), general_inflation=inflation,
    oil_escalation=oil_esc, gas_escalation=gas_esc, cost_escalation=cost_esc,
    discount_rate_basis=rate_basis
)
active_deck = st.session_state.market_deck if use_deck else None
cutoff = CutoffSettings(
    mode=cutoff_mode,
    hard_cutoff_year=int(hard_year) if cutoff_mode in ('hard','negative_ocf','economic_limit') else None,
    consecutive_negative_periods=int(neg_periods),
    lookahead_periods=int(lookahead),
    minimum_oil_mmbbl=float(min_oil),
    minimum_gas_msm3=float(min_gas),
    decom_lag_periods=int(decom_lag)
)
active_profile = expand_profile(st.session_state.profile, time_resolution, capex_phasing)
analysis_view = None
if page == 'Sensitivity & Breakeven':
    analysis_view = st.radio('Analysis view', ['Sensitivity & Tornado', 'Breakeven Analysis', 'Market Decks'], horizontal=True, key='analysis_view')
cf = calculate_cashflow(active_profile, a, active_deck, cutoff)
m = metrics(cf)
model_key = hashlib.sha256(json.dumps({
    'profile': active_profile.to_json(double_precision=15),
    'assumptions': a.__dict__,
    'deck': None if active_deck is None else active_deck.to_json(double_precision=15),
    'cutoff': cutoff.__dict__,
}, sort_keys=True).encode()).hexdigest()
mc_matches_model = st.session_state.get('mc_model_key') == model_key

# Breakeven calculations evaluated consistently on active_profile
show_breakeven = page == 'Dashboard' or analysis_view == 'Breakeven Analysis'
be = breakeven_oil_price(active_profile, a, cutoff=cutoff) if not use_deck and show_breakeven else None
deck_be = breakeven_factor(active_profile, a, 'Oil price', active_deck, cutoff=cutoff) if use_deck and show_breakeven else None
mev = minimum_economic_volume(active_profile, a, active_deck, cutoff) if show_breakeven else None

# Compute equivalent dollar per bbl and dollar per Sm3 when deck is active
equiv_oil_be_usd_bbl = None
equiv_oil_be_usd_sm3 = None
if use_deck and deck_be is not None:
    vol_weights = cf.get('oil_mmbbl', pd.Series(0, index=cf.index))
    if vol_weights.sum() > 0 and 'oil_price_usd_bbl' in cf.columns:
        w_oil_price = float((cf['oil_price_usd_bbl'] * vol_weights).sum() / vol_weights.sum())
    else:
        w_oil_price = float(st.session_state.market_deck['oil_usd_bbl'].mean())
    equiv_oil_be_usd_bbl = w_oil_price * deck_be
    equiv_oil_be_usd_sm3 = equiv_oil_be_usd_bbl * BBL_PER_SM3
elif be is not None:
    equiv_oil_be_usd_bbl = be
    equiv_oil_be_usd_sm3 = be * BBL_PER_SM3

# Shared scenario state
if 'scenario_table' not in st.session_state:
    st.session_state.scenario_table = pd.DataFrame([
        {'name':'Base','oil_factor':1.0,'gas_factor':1.0,'capex_factor':1.0,'opex_factor':1.0,'production_factor':1.0,'start_delay_years':0},
        {'name':'High resource','oil_factor':1.0,'gas_factor':1.0,'capex_factor':1.05,'opex_factor':1.0,'production_factor':1.25,'start_delay_years':0},
        {'name':'Low resource','oil_factor':1.0,'gas_factor':1.0,'capex_factor':0.95,'opex_factor':1.0,'production_factor':0.75,'start_delay_years':0},
        {'name':'1-year delay','oil_factor':1.0,'gas_factor':1.0,'capex_factor':1.0,'opex_factor':1.0,'production_factor':1.0,'start_delay_years':1},
    ])

def current_scenarios():
    out = []
    for row in st.session_state.scenario_table.to_dict('records'):
        try: out.append(Scenario(**row))
        except (TypeError, ValueError): pass
    return out

scenario_results = pd.DataFrame(columns=['scenario', 'npv_mnok', 'irr', 'payback_year'])
scenario_cfs = {}
if page == 'Project & Export':
    scenarios = current_scenarios()
    scenario_results, scenario_cfs = evaluate_scenarios(active_profile, a, scenarios, active_deck, cutoff)
scenario_values = dict(zip(scenario_results['scenario'], scenario_results['npv_mnok'])) if not scenario_results.empty else {}

# Conversion factors
mf = money_factor(money_unit)
of = oil_factor(oil_unit)
gf = gas_factor(gas_unit)

def display_table(frame):
    return display_frame(frame, money_unit, oil_unit, gas_unit)


# ==============================================================================
# 1. DASHBOARD
# ==============================================================================
if page == 'Dashboard':
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric('Pre-tax NPV', f"{m['pre_tax_npv_mnok']*mf:,.2f} {money_unit}")
    c2.metric('After-tax NPV', f"{m['after_tax_npv_mnok']*mf:,.2f} {money_unit}")
    c3.metric('IRR after tax', '—' if m['irr'] is None else f"{m['irr']:.1%}")
    
    # Breakeven metric display with both $/bbl ($/Sm3) and deck factor
    if use_deck:
        if deck_be is not None and equiv_oil_be_usd_bbl is not None:
            be_str = f"${equiv_oil_be_usd_bbl:.1f}/bbl ({deck_be:.3f}× deck)"
            c4.metric('Oil breakeven', be_str, help=f"Weighted deck oil breakeven: ${equiv_oil_be_usd_bbl:,.2f}/bbl (${equiv_oil_be_usd_sm3:,.2f}/Sm³), requiring a {deck_be:.3f}× factor on the market deck.")
        else:
            c4.metric('Oil breakeven', '—', help='No breakeven found in search range')
    else:
        if be is not None:
            c4.metric('Oil breakeven', f"${be:.1f}/bbl", help=f"Flat oil breakeven: ${be:,.2f}/bbl (${be*BBL_PER_SM3:,.2f}/Sm³)")
        else:
            c4.metric('Oil breakeven', '—')
            
    c5.metric('MEV', '—' if mev is None else f"{mev:,.2f} MMboe", help="Minimum economic hydrocarbon volume required for NPV = 0")
    c6.metric('Payback', m['payback_year'] or '—')
    
    if cf.attrs.get('cutoff_year') is not None:
        st.info(f"Economic cessation: {cf.attrs.get('cutoff_year')} — {cf.attrs.get('cutoff_reason')}")
    st.caption(f"{money_basis.title()} money • entered {rate_basis} discount {disc:.2%} • effective {money_basis} discount {consistent_discount_rate(disc,rate_basis,money_basis,inflation):.2%}")
    
    chart_cf = display_table(cf[['year','pre_tax_cf_mnok','after_tax_cf_mnok']])
    render_chart(px.bar(chart_cf, x='year', y=list(chart_cf.columns[1:]), barmode='group', title=f'Period cash flow ({money_unit})', labels={'value':money_unit, 'variable':'Cash flow'}), use_container_width=True)
    
    cum = display_table(cf[['year','cumulative_cf_mnok','cumulative_npv_mnok']])
    render_chart(px.line(cum, x='year', y=list(cum.columns[1:]), markers=True, title=f'Cumulative cash flow and NPV ({money_unit})', labels={'value':money_unit, 'variable':'Cash flow'}), use_container_width=True)
    
    prod = cf[['year','oil_mmbbl','gas_msm3']].copy()
    prod[f'Oil ({oil_unit})'] = prod['oil_mmbbl'] * of
    prod[f'Gas ({gas_unit})'] = prod['gas_msm3'] * gf
    render_chart(px.line(prod, x='year', y=[f'Oil ({oil_unit})', f'Gas ({gas_unit})'], markers=True, title=f'Production profile — Oil ({oil_unit}), Gas ({gas_unit})', labels={'value':'Volume (units shown in legend)'}), use_container_width=True)


# ==============================================================================
# 2. PRODUCTION & ECONOMICS
# ==============================================================================
elif page == 'Production & Economics':
    tab_profile, tab_gen, tab_cashflow, tab_bridges = st.tabs([
        'Production & Cost Profile',
        'Profile Generator & Concepts',
        'Cash Flow Statement',
        'Revenue & Tax Bridges'
    ])
    
    with tab_profile:
        st.subheader('Production and cost profile')
        st.caption(f'Display & input units: Oil ({oil_unit}), Gas ({gas_unit}), Costs ({money_unit}). Seamlessly converted to/from canonical model units (MMbbl, MSm³, MNOK).')
        
        # Prepare display DataFrame with user-selected units
        disp_df = st.session_state.profile.copy()
        oil_col_name = f'oil_{oil_unit}'
        gas_col_name = f'gas_{gas_unit}'
        capex_col_name = f'capex_{money_unit}'
        opex_col_name = f'opex_{money_unit}'
        decom_col_name = f'decom_{money_unit}'
        
        disp_df[oil_col_name] = disp_df['oil_mmbbl'] * of
        disp_df[gas_col_name] = disp_df['gas_msm3'] * gf
        disp_df[capex_col_name] = disp_df['capex_mnok'] * mf
        disp_df[opex_col_name] = disp_df['opex_mnok'] * mf
        disp_df[decom_col_name] = disp_df['decom_mnok'] * mf
        
        view_cols = ['year', oil_col_name, gas_col_name, capex_col_name, opex_col_name, decom_col_name]
        disp_df = disp_df[view_cols]
        
        with st.form('profile_manual_form'):
            edited_profile = st.data_editor(disp_df, use_container_width=True, num_rows='dynamic', key=f'profile_editor_{money_unit}_{oil_unit}_{gas_unit}')
            apply_manual = st.form_submit_button('Apply manual profile', type='primary')
            
        if apply_manual:
            try:
                # Convert back from display units to canonical units
                conv_df = edited_profile.copy()
                conv_df['oil_mmbbl'] = conv_df[oil_col_name] / of
                conv_df['gas_msm3'] = conv_df[gas_col_name] / gf
                conv_df['capex_mnok'] = conv_df[capex_col_name] / mf
                conv_df['opex_mnok'] = conv_df[opex_col_name] / mf
                conv_df['decom_mnok'] = conv_df[decom_col_name] / mf
                canonical = conv_df[['year', 'oil_mmbbl', 'gas_msm3', 'capex_mnok', 'opex_mnok', 'decom_mnok']]
                st.session_state.profile = validate_profile_table(canonical)
                st.success(f'Manual profile applied successfully (converted from {oil_unit}, {gas_unit}, {money_unit} to canonical units).')
                st.rerun()
            except (TypeError, ValueError) as exc:
                st.error(f'Profile validation error: {exc}')
                
        c_up, c_dn = st.columns(2)
        with c_up:
            uploaded_profile = st.file_uploader('Import profile from CSV or Excel', type=['csv','xlsx','xlsm'], key='profile_upload')
            if uploaded_profile is not None:
                try:
                    imported_profile = load_profile_table(uploaded_profile.getvalue(), uploaded_profile.name)
                    st.dataframe(display_table(imported_profile), use_container_width=True, hide_index=True)
                    if st.button('Apply imported profile', type='primary', key='apply_profile_import'):
                        st.session_state.profile = imported_profile
                        st.success('Imported profile applied.')
                        st.rerun()
                except (TypeError, ValueError, ImportError) as exc:
                    st.error(f'Could not import profile: {exc}')
        with c_dn:
            template = st.session_state.profile.iloc[:0].to_csv(index=False)
            st.caption('CSV templates and imports use canonical MMbbl, MSm3 and MNOK units.')
            st.download_button('Download profile CSV template', template, 'profile_template.csv', 'text/csv')

    with tab_gen:
        st.subheader('Production profile generator & reserves')
        g1, g2, g3, g4 = st.columns(4)
        gres = g1.number_input('Recoverable oil (MMbbl)', 1.0, 2000.0, 100.0, 5.0)
        gplat = g2.number_input('Oil plateau (MMbbl/year)', .1, 200.0, 12.0, .5)
        gdecl = g3.number_input('Annual decline (%)', 0.0, 80.0, 15.0, 1.0) / 100
        glife = g4.number_input('Profile periods', 5, 60, 20, 1)
        generated = generated_profile(
            int(st.session_state.profile.year.min()), int(glife), float(gres), float(gplat),
            250.0, 2, 4, float(gdecl), float(st.session_state.profile.capex_mnok.sum()),
            float(st.session_state.profile.opex_mnok[st.session_state.profile.opex_mnok > 0].median() or 0),
            float(st.session_state.profile.decom_mnok.sum())
        )
        generated_display = display_table(generated[['year', 'oil_mmbbl', 'gas_msm3']])
        render_chart(px.line(generated_display, x='year', y=list(generated_display.columns[1:]), title='Generated ramp / plateau / decline profile', labels={'value':'Volume (units shown in legend)'}), use_container_width=True)
        st.caption('Generator inputs above use the explicitly stated canonical units.')
        if st.button('Use generated profile as project profile'):
            st.session_state.profile = generated
            st.success('Project profile updated with generated curve.')
            st.rerun()

        st.divider()
        st.subheader('Development concept comparison')
        if 'concept_table' not in st.session_state:
            st.session_state.concept_table = pd.DataFrame([
                {'name':'Subsea tie-back','capex_factor':.75,'opex_factor':.85,'production_factor':.90,'schedule_shift_years':-1},
                {'name':'FPSO','capex_factor':1.0,'opex_factor':1.0,'production_factor':1.0,'schedule_shift_years':0},
                {'name':'Fixed platform','capex_factor':1.30,'opex_factor':.90,'production_factor':1.12,'schedule_shift_years':1}
            ])
        st.session_state.concept_table = st.data_editor(st.session_state.concept_table, num_rows='dynamic', use_container_width=True, key='concept_editor')
        concepts = []
        for r in st.session_state.concept_table.to_dict('records'):
            try: concepts.append(DevelopmentConcept(**r))
            except (TypeError, ValueError): pass
        concept_results = compare_concepts(active_profile, a, concepts, active_deck, cutoff) if concepts else pd.DataFrame()
        if not concept_results.empty:
            concept_display = display_table(concept_results)
            st.dataframe(concept_display, use_container_width=True, hide_index=True)
            render_chart(px.bar(concept_display, x='concept', y=f'npv ({money_unit})', title=f'Cutoff-aware concept NPV ({money_unit})'), use_container_width=True)

    with tab_cashflow:
        st.subheader('Economic cash-flow statement')
        econ = display_table(cf)
        st.caption(f'Money shown in {money_unit}; oil in {oil_unit}; gas in {gas_unit}. Calculation engine runs on canonical units.')
        st.dataframe(econ.style.format(precision=2), use_container_width=True)
        st.download_button('Download displayed cash flow CSV', econ.to_csv(index=False), 'cashflow_display.csv', 'text/csv')

    with tab_bridges:
        st.subheader('Revenue & value bridges')
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            st.markdown('### Undiscounted cash-flow bridge')
            wf = npv_waterfall(cf)
            labels = list(wf)
            values = [wf[k] * mf for k in labels]
            figw = go.Figure(go.Waterfall(name='Project value', orientation='v', measure=['relative']*len(values)+['total'], x=labels+['Undiscounted after-tax CF'], y=values+[0], connector={'line':{'width':1}}))
            figw.update_layout(title=f'Project cash-flow bridge ({money_unit})', yaxis_title=money_unit)
            render_chart(figw, use_container_width=True)
        with col_w2:
            st.markdown('### Pre-tax to after-tax bridge')
            tb = tax_bridge(cf)
            tb['value'] = tb['value_mnok'] * mf
            measures = ['absolute'] + ['relative'] * (max(len(tb)-2, 0)) + ['total'] if len(tb) > 1 else ['absolute']
            figtb = go.Figure(go.Waterfall(x=tb['component'], y=tb['value'], measure=measures))
            figtb.update_layout(title=f'Pre-tax to after-tax bridge ({money_unit})', yaxis_title=money_unit)
            render_chart(figtb, use_container_width=True)
        
        st.markdown('### Stacked revenue breakdown')
        rev = display_table(cf[['year','oil_revenue_mnok','gas_revenue_mnok']])
        render_chart(px.area(rev, x='year', y=list(rev.columns[1:]), title=f'Stacked period revenue ({money_unit})', labels={'value':money_unit}), use_container_width=True)


# ==============================================================================
# 3. SENSITIVITY & BREAKEVEN
# ==============================================================================
elif page == 'Sensitivity & Breakeven':
    if analysis_view == 'Sensitivity & Tornado':
        st.subheader('Tornado & single-variable sensitivity')
        tdf, base_npv = tornado(active_profile, a, market_deck=active_deck, cutoff=cutoff)
        fig = go.Figure()
        fig.add_bar(y=tdf['variable'], x=tdf['low_delta']*mf, orientation='h', name='Low case (-20%)')
        fig.add_bar(y=tdf['variable'], x=tdf['high_delta']*mf, orientation='h', name='High case (+20%)')
        fig.update_layout(barmode='overlay', title=f'Tornado — change in NPV ({money_unit})', xaxis_title=f'ΔNPV ({money_unit})')
        render_chart(fig, use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            variable = st.selectbox('Sensitivity curve variable', ['Oil price','Gas price','Production','CAPEX','OPEX'])
            curve = sensitivity_curve(active_profile, a, variable, market_deck=active_deck, cutoff=cutoff)
            curve['npv_display'] = curve['npv_mnok'] * mf
            figc = px.line(curve, x='change_pct', y='npv_display', markers=True, title=f'{variable} sensitivity curve')
            figc.add_hline(y=0, line_dash='dash')
            figc.update_xaxes(title='Change from base (%)')
            figc.update_yaxes(title=f'NPV ({money_unit})')
            render_chart(figc, use_container_width=True)
        with c2:
            st.markdown('### NPV spider plot')
            sp = spider(active_profile, a, active_deck, cutoff=cutoff)
            sp = display_table(sp)
            figsp = px.line(sp, x='change_pct', y=f'npv ({money_unit})', color='variable', markers=True, title=f'Spider sensitivity ({money_unit})')
            figsp.add_hline(y=0, line_dash='dash')
            figsp.update_xaxes(title='Input change (%)')
            figsp.update_yaxes(title=f'NPV ({money_unit})')
            render_chart(figsp, use_container_width=True)

    elif analysis_view == 'Breakeven Analysis':
        st.subheader('Multi-variable & extended breakeven')
        b1, b2 = st.columns(2)
        with b1:
            if use_deck:
                deck_table = breakeven_table(active_profile, a, active_deck, cutoff=cutoff)
                oil_row = deck_table[deck_table['variable'] == 'Oil price'].iloc[0]
                if pd.isna(oil_row['breakeven_factor']):
                    st.metric('Oil-deck breakeven', 'Outside search range')
                else:
                    be_deck_f = oil_row['breakeven_factor']
                    st.metric(
                        'Oil-deck breakeven',
                        f"{be_deck_f:.3f}× ({oil_row['breakeven_change_pct']:+.1f}%)",
                        f"${equiv_oil_be_usd_bbl:.2f}/bbl (${equiv_oil_be_usd_sm3:.2f}/Sm³)" if equiv_oil_be_usd_bbl is not None else None
                    )
                st.caption('With annual market deck enabled, breakeven is computed as a uniform curve multiplier.')
            else:
                st.metric(
                    'Oil-price breakeven',
                    'Outside search range' if be is None else f'${be:,.2f}/bbl',
                    f"${be*BBL_PER_SM3:,.2f}/Sm³" if be is not None else None
                )
                if be is not None:
                    prices = np.linspace(max(0, be*.45), max(be*1.65, oil*1.4, 20), 31)
                    rows = []
                    for price in prices:
                        aa = Assumptions(**{**a.__dict__, 'oil_price_usd_bbl': float(price)})
                        rows.append({'oil_price': price, 'npv': metrics(calculate_cashflow(active_profile, aa, cutoff=cutoff))['npv_mnok'] * mf})
                    bedf = pd.DataFrame(rows)
                    figb = px.line(bedf, x='oil_price', y='npv', title='Oil-price breakeven curve')
                    figb.add_hline(y=0, line_dash='dash')
                    figb.add_vline(x=be, line_dash='dash')
                    figb.update_xaxes(title='Oil price (USD/bbl)')
                    figb.update_yaxes(title=f'NPV ({money_unit})')
                    render_chart(figb, use_container_width=True)
            st.metric('Minimum economic volume (MEV)', '—' if mev is None else f'{mev:,.2f} MMboe')

        with b2:
            st.markdown('### Multi-variable breakeven table')
            bet = breakeven_table(active_profile, a, active_deck, cutoff=cutoff)
            st.dataframe(bet.style.format({'breakeven_factor':'{:.3f}','breakeven_change_pct':'{:.1f}%'}), use_container_width=True, hide_index=True)
            available = bet.dropna(subset=['breakeven_change_pct'])
            if not available.empty:
                render_chart(px.bar(available, x='variable', y='breakeven_change_pct', title='Input change required to reach NPV = 0', labels={'breakeven_change_pct':'Change from base (%)'}), use_container_width=True)

        st.markdown('### Extended breakeven suite')
        st.dataframe(extended_breakeven_suite(active_profile, a, active_deck, cutoff), use_container_width=True, hide_index=True)

    elif analysis_view == 'Market Decks':
        st.subheader('Market decks')
        st.caption('Edit annual oil, gas and FX assumptions. When “Use annual market deck” is enabled, these curves drive the core cash-flow calculation.')
        deck_issues = validate_market_deck(st.session_state.market_deck)
        st.session_state.market_deck = st.data_editor(st.session_state.market_deck, use_container_width=True, num_rows='dynamic', key='market_deck_editor')
        if deck_issues:
            for issue in deck_issues: st.warning(issue)
        else:
            md = st.session_state.market_deck.copy()
            figm = go.Figure()
            figm.add_trace(go.Scatter(x=md.year, y=md.oil_usd_bbl, name='Oil USD/bbl'))
            figm.add_trace(go.Scatter(x=md.year, y=md.usd_nok, name='USD/NOK', yaxis='y2'))
            figm.update_layout(title='Oil price and FX deck', yaxis_title='USD/bbl', yaxis2=dict(title='USD/NOK', overlaying='y', side='right'))
            render_chart(figm, use_container_width=True)
            render_chart(px.line(md, x='year', y='gas_usd_sm3', markers=True, title='Gas price deck (USD/Sm³)'), use_container_width=True)

        st.markdown('### Named reference decks')
        decks = named_decks(sorted(st.session_state.profile.year.astype(int).unique()), oil, gas, fx)
        deck_name = st.radio('Preset deck', ['Low', 'Base', 'High'], horizontal=True, key='v10_deck')
        selected_deck = select_deck(decks, deck_name)
        render_chart(px.line(selected_deck, x='year', y=['oil_usd_bbl','usd_nok'], markers=True, title=f'{deck_name} reference deck'), use_container_width=True)


# ==============================================================================
# 4. SCENARIOS & UNCERTAINTY
# ==============================================================================
elif page == 'Scenarios & Uncertainty':
    tab_scen, tab_mc, tab_tree = st.tabs([
        'Scenario Manager',
        'Monte Carlo Uncertainty',
        'Decision Tree'
    ])
    
    with tab_scen:
        st.subheader('Scenario manager')
        st.caption('Define deterministic scenario multipliers modifying production, CAPEX, OPEX, and schedule.')
        st.session_state.scenario_table = st.data_editor(st.session_state.scenario_table, num_rows='dynamic', use_container_width=True, key='scenario_editor')
        scenarios = current_scenarios()
        scenario_results, scenario_cfs = evaluate_scenarios(active_profile, a, scenarios, active_deck, cutoff)
        scenario_values = dict(zip(scenario_results['scenario'], scenario_results['npv_mnok'])) if not scenario_results.empty else {}
        scenario_display = display_table(scenario_results)
        st.dataframe(scenario_display, use_container_width=True, hide_index=True)
        if not scenario_results.empty:
            render_chart(px.bar(scenario_display, x='scenario', y=f'npv ({money_unit})', title=f'Scenario NPV ({money_unit})'), use_container_width=True)

    with tab_mc:
        st.subheader('Monte Carlo simulation')
        st.caption('Gaussian copula sampling over correlated price, cost, and reservoir distributions.')
        dists = ['lognormal','normal','triangular']
        c1, c2, c3, c4, c5 = st.columns(5)
        oil_sig = c1.number_input('Oil σ (%)', 0., 100., 20.) / 100
        oil_dist = c1.selectbox('Oil distribution', dists, key='oil_dist')
        gas_sig = c2.number_input('Gas σ (%)', 0., 100., 20.) / 100
        gas_dist = c2.selectbox('Gas distribution', dists, key='gas_dist')
        cap_sig = c3.number_input('CAPEX σ (%)', 0., 100., 20.) / 100
        cap_dist = c3.selectbox('CAPEX distribution', dists, key='cap_dist')
        op_sig = c4.number_input('OPEX σ (%)', 0., 100., 15.) / 100
        op_dist = c4.selectbox('OPEX distribution', dists, key='op_dist')
        prod_sig = c5.number_input('Production σ (%)', 0., 100., 15.) / 100
        prod_dist = c5.selectbox('Production distribution', dists, key='prod_dist')
        
        r1, r2, r3 = st.columns(3)
        price_corr = r1.slider('Oil ↔ gas correlation', -.9, .9, .35, .05)
        cost_corr = r2.slider('CAPEX ↔ OPEX correlation', -.9, .9, .40, .05)
        resource_cost_corr = r3.slider('Production ↔ CAPEX correlation', -.9, .9, .15, .05)
        
        u = Uncertainty(oil_sig, gas_sig, cap_sig, op_sig, prod_sig, oil_dist, gas_dist, cap_dist, op_dist, prod_dist, price_corr, cost_corr, resource_cost_corr)
        iterations = st.slider('Iterations', 500, 10000, 2000, 500)
        seed = st.number_input('Random seed', 0, 999999, 42)
        mc_inputs_key = (repr(u), iterations, int(seed))
        
        if st.button('Run Monte Carlo', type='primary', key='run_mc'):
            with st.spinner('Evaluating correlated economic cases...'):
                samples, factors = run_monte_carlo(active_profile, a, u, iterations, int(seed), return_factors=True, market_deck=active_deck, cutoff=cutoff)
            st.session_state.mc_samples = samples
            st.session_state.mc_factors = factors
            st.session_state.mc_model_key = model_key
            st.session_state.mc_inputs_key = mc_inputs_key
            mc_matches_model = True
            
        mc_is_current = mc_matches_model and st.session_state.get('mc_inputs_key') == mc_inputs_key
        if 'mc_samples' in st.session_state and not mc_is_current:
            st.warning('Model or uncertainty inputs have changed. Run Monte Carlo again to update the results.')
        if 'mc_samples' in st.session_state and mc_is_current:
            samples = st.session_state.mc_samples
            factors = st.session_state.get('mc_factors')
            ms = mc_summary(samples)
            x1, x2, x3, x4, x5 = st.columns(5)
            x1.metric('P10 (10th percentile / downside)', f"{ms['P10']*mf:,.2f} {money_unit}")
            x2.metric('P50 (Median)', f"{ms['P50']*mf:,.2f} {money_unit}")
            x3.metric('P90 (90th percentile / upside)', f"{ms['P90']*mf:,.2f} {money_unit}")
            x4.metric('Mean', f"{ms['mean']*mf:,.2f} {money_unit}")
            x5.metric('P(NPV > 0)', f"{ms['prob_npv_positive']:.1%}")
            
            c_hist, c_scurve = st.columns(2)
            with c_hist:
                render_chart(px.histogram(x=samples*mf, nbins=60, labels={'x':f'NPV ({money_unit})'}, title='NPV distribution'), use_container_width=True)
            with c_scurve:
                exc = display_table(exceedance_curve(samples))
                render_chart(px.line(exc, x=f'npv ({money_unit})', y='exceedance_pct', title='NPV exceedance curve (S-curve)', labels={f'npv ({money_unit})':f'NPV ({money_unit})','exceedance_pct':'Probability of exceedance (%)'}), use_container_width=True)
            st.caption('P10/P90 are non-exceedance percentiles (low/high NPV), not petroleum reserves exceedance notation.')

            with st.expander('Correlation / sample diagnostics'):
                st.write('Target factor correlation matrix')
                st.dataframe(pd.DataFrame(correlation_matrix(u), index=['Oil','Gas','CAPEX','OPEX','Production'], columns=['Oil','Gas','CAPEX','OPEX','Production']))
                if factors is not None:
                    st.write('Realized sampled-factor correlation')
                    st.dataframe(factors.corr())
        else:
            st.info('Configure uncertainty inputs and click “Run Monte Carlo”.')

    with tab_tree:
        st.subheader('Decision tree + scenario economics')
        default_tree = {
            'nodes': [
                {'id':'n1','type':'decision','label':'Development concept','x':50,'y':220},
                {'id':'n2','type':'chance','label':'Resource outcome','x':300,'y':100},
                {'id':'n3','type':'outcome','label':'High','scenario_key':'High resource','value':0,'x':560,'y':40},
                {'id':'n4','type':'outcome','label':'Low','scenario_key':'Low resource','value':0,'x':560,'y':220},
                {'id':'n5','type':'outcome','label':'Base','scenario_key':'Base','value':0,'x':300,'y':390}
            ],
            'edges': [
                {'id':'e1','source':'n1','target':'n2','label':'Develop'},
                {'id':'e2','source':'n2','target':'n3','probability':0.35},
                {'id':'e3','source':'n2','target':'n4','probability':0.65},
                {'id':'e4','source':'n1','target':'n5','label':'Base'}
            ]
        }
        if 'decision_tree' not in st.session_state:
            st.session_state.decision_tree = default_tree
        edited = decision_tree(st.session_state.decision_tree, {k:v*mf for k,v in scenario_values.items()}, key='economic_decision_tree', money_unit=money_unit, money_factor=mf, theme=THEMES[theme_name])
        if edited:
            st.session_state.decision_tree = edited
        try:
            tr = evaluate_tree(st.session_state.decision_tree, scenario_values)
            c1, c2 = st.columns(2)
            c1.metric('Current decision-tree value', f"{tr['value']*mf:,.2f} {money_unit}")
            c2.write('Selected decision edges: ' + (', '.join(tr['selected_edges']) or '—'))
            for w in tr['warnings']: st.warning(w)
        except Exception as exc:
            st.error(f'Tree evaluation error: {exc}')
            
        with st.expander('Scenario values feeding outcome nodes'):
            st.dataframe(display_table(pd.DataFrame([{'scenario_key':k,'current_npv_mnok':v} for k,v in scenario_values.items()])), use_container_width=True, hide_index=True)
            st.json(st.session_state.decision_tree)


# ==============================================================================
# 5. PROJECT & EXPORT
# ==============================================================================
elif page == 'Project & Export':
    tab_exp, tab_audit, tab_advanced = st.tabs([
        'Project Snapshots & Export',
        'Data & Audit Trail',
        'Exploration & Assurance'
    ])
    
    with tab_exp:
        st.subheader('Project snapshots & workbook export')
        project_name = st.text_input('Project name', 'NCS Development Case')
        version_name = st.text_input('Snapshot label', 'Baseline')
        if 'snapshots' not in st.session_state:
            st.session_state.snapshots = []
        if st.button('Create economics snapshot'):
            st.session_state.snapshots.append(snapshot(project_name, version_name, m).__dict__)
            st.success(f'Snapshot "{version_name}" captured.')
        if st.session_state.snapshots:
            st.dataframe(display_table(pd.json_normalize(st.session_state.snapshots)), use_container_width=True)
            
        c_dl1, c_dl2, c_dl3 = st.columns(3)
        with c_dl1:
            project_bytes = dumps_project(
                st.session_state.profile, a, st.session_state.scenario_table,
                st.session_state.get('decision_tree', {}),
                {'author':'Merouane Hamdani','purpose':'Educational purposes only — non-commercial','app_version':'V12.3'},
                st.session_state.market_deck, st.session_state.get('concept_table'),
                {'time_resolution':time_resolution, 'capex_phasing':capex_phasing, 'cutoff':cutoff.__dict__},
                st.session_state.snapshots
            )
            st.download_button('Save complete project (.json)', project_bytes, 'ncs_project.json', 'application/json')
        with c_dl2:
            wb = excel_workbook(a, active_profile, cf, st.session_state.market_deck, scenario_results, st.session_state.get('mc_samples') if mc_matches_model else None, {'author':'Merouane Hamdani','purpose':'Educational purposes only — non-commercial','money_basis':money_basis,'display_money_unit':money_unit,'export_units':'Canonical MNOK / MMbbl / MSm3'})
            st.download_button('Download analysis workbook (.xlsx)', wb, 'ncs_economics_analysis.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            st.caption('Workbook, audit CSVs and project JSON retain canonical MNOK / MMbbl / MSm3 units for reproducibility.')
            if 'mc_samples' in st.session_state and not mc_matches_model:
                st.warning('Outdated Monte Carlo samples are excluded from this workbook. Re-run the simulation for this model.')
        with c_dl3:
            report = decision_report_text(project_name, m, cf.attrs.get('cutoff_year'), cf.attrs.get('cutoff_reason'), st.session_state.get('concept_table'))
            st.download_button('Download decision summary (.md)', report, 'investment_decision_summary.md', 'text/markdown')

        st.divider()
        st.subheader('Load existing project')
        uploaded = st.file_uploader('Load project JSON', type=['json'], key='project_json_loader')
        if uploaded is not None:
            try:
                loaded = loads_project(uploaded)
                st.success(f"Project schema {loaded['schema_version']} validated.")
                st.json({'metadata':loaded.get('metadata',{}),'settings':loaded.get('settings',{}),'snapshots':loaded.get('snapshots',[])})
                if st.button('Apply loaded project', type='primary', key='apply_loaded_project'):
                    loaded['profile'] = validate_profile_table(loaded['profile']).to_dict('records')
                    st.session_state._pending_project_import = loaded
                    st.rerun()
            except Exception as e:
                st.error(f'Could not load project: {e}')

    with tab_audit:
        st.subheader('Data & calculation audit')
        c_csv1, c_csv2 = st.columns(2)
        with c_csv1:
            st.download_button('Download full cash-flow CSV', cf.to_csv(index=False), 'cashflow.csv', 'text/csv')
        with c_csv2:
            st.download_button('Download scenarios CSV', scenario_results.to_csv(index=False), 'scenarios.csv', 'text/csv')
            
        st.json({
            'assumptions': a.__dict__,
            'display_units': {'money': money_unit, 'oil': oil_unit, 'gas': gas_unit},
            'effective_discount_rate': consistent_discount_rate(disc, rate_basis, money_basis, inflation),
            'metrics': m,
            'oil_breakeven_usd_bbl': equiv_oil_be_usd_bbl,
            'oil_breakeven_usd_sm3': equiv_oil_be_usd_sm3,
            'deck_multiplier': deck_be if use_deck else None,
            'market_deck_enabled': use_deck,
            'cutoff_settings': cutoff.__dict__,
            'attribution': {'author':'Merouane Hamdani','purpose':'Educational purposes only — non-commercial'}
        })

    with tab_advanced:
        st.subheader('Exploration risking & model assurance')
        e1, e2 = st.columns(2)
        with e1:
            st.markdown('### Exploration risking')
            cos = st.slider('Geological chance of success (GCoS)', 0.01, 0.99, 0.30, 0.01)
            st.caption('Exploration inputs use canonical MNOK; results below use the selected display unit.')
            dry = st.number_input('Dry-hole cost (MNOK)', 0.0, 20000.0, 900.0, 50.0)
            small = st.number_input('Small discovery development NPV (MNOK)', -50000.0, 100000.0, 1500.0, 100.0)
            large = st.number_input('Large discovery development NPV (MNOK)', -50000.0, 200000.0, 12000.0, 250.0)
            pe = prospect_emv(cos, dry, [DiscoveryCase('Small', .55, small), DiscoveryCase('Large', .45, large)])
            st.metric('Risked exploration EMV', f"{pe['risked_emv_mnok']*mf:,.2f} {money_unit}")
            st.dataframe(display_table(pd.DataFrame(discovery_distribution(cos, dry, [DiscoveryCase('Small', .55, small), DiscoveryCase('Large', .45, large)]))), hide_index=True, use_container_width=True)
        with e2:
            st.markdown('### Model health & assurance')
            health = model_health(st.session_state.profile, active_deck, [.55,.45], {'cessation_year':cf.attrs.get('cutoff_year'),'decom_year':None}, recoverable_oil_mmbbl=float(st.session_state.profile.oil_mmbbl.sum())*1.05, money_basis=money_basis, discount_basis=rate_basis)
            st.dataframe(pd.DataFrame(health), hide_index=True, use_container_width=True)

st.divider()
st.markdown('<div style="text-align:center;opacity:.72;font-size:.82rem;padding:6px 0 18px"><b>Made by Merouane Hamdani</b> · Educational purposes only — non-commercial · NCS Economics Workbench</div>', unsafe_allow_html=True)
