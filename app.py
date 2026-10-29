import json
import io
import hashlib
from dataclasses import asdict
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import streamlit as st

from economics.engine import Assumptions, calculate_cashflow, metrics, breakeven_oil_price, minimum_economic_volume
from economics.analysis import tornado, sensitivity_curve, npv_waterfall
from economics.market import default_market_deck, validate_market_deck
from economics.advanced_analysis import (
    spider, breakeven_table, breakeven_factor, exceedance_curve, tax_bridge,
    excel_workbook, breakeven_suite, extended_breakeven_suite
)
from economics.conventions import (
    BBL_PER_SM3, money_factor, oil_factor, gas_factor, consistent_discount_rate, display_frame, compact_money
)
from economics.decision_tree import evaluate_tree
from economics.scenarios import Scenario, evaluate_scenarios
from components.decision_tree_component import decision_tree
from economics.monte_carlo import (
    Uncertainty, run_monte_carlo, run_tree_monte_carlo, summary as mc_summary, correlation_matrix
)
from economics.cutoff import CutoffSettings
from economics.production import FIELD_TYPES, FieldProfileSettings, field_profile
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
    [data-testid="stMetricLabel"] p {{white-space:normal; overflow:visible; text-overflow:clip;}}
    [data-testid="stMetricValue"], [data-testid="stMetricValue"] > div, [data-testid="stMetricValue"] p {{
        font-size:1.6rem; line-height:1.25; font-weight:500;
        white-space:normal; overflow:visible; text-overflow:clip; overflow-wrap:anywhere;
        font-variant-numeric:tabular-nums;
    }}
    .stTabs [data-baseweb="tab-list"] {{gap:6px; border-bottom:1px solid {t['grid']};}}
    .stTabs [data-baseweb="tab"] {{border-radius:9px 9px 0 0; padding:8px 14px;}}
    .stTabs [aria-selected="true"] {{background:{t['card']}; color:{t['accent']};}}
    .ncs-hero {{padding:24px 26px; border-bottom:3px solid {t['accent']}; background:{t['panel']}; margin-bottom:24px;}}
    .ncs-kicker {{color:{t['accent']}; font-size:.78rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase;}}
    .ncs-sub {{color:{t['muted']}; margin-top:4px;}}
    [data-testid="stHorizontalBlock"] {{flex-wrap:wrap;}}
    [data-testid="column"] {{min-width:260px;}}
    .st-key-module_navigation [data-testid="column"], .st-key-module_navigation [data-testid="stColumn"] {{min-width:130px;}}
    .stDataFrame, [data-testid="stDataEditor"] {{overflow-x:auto;}}
    [data-testid="stWidgetLabel"], [data-testid="stCaptionContainer"], [data-testid="stMarkdownContainer"] {{color:{t['text']};}}
    [data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="input"] input {{background:{t['card']}; color:{t['text']};}}
    button[kind="primary"] {{background:{t['accent']}; color:#ffffff; border-radius:2px;}}
    button[kind="primary"] [data-testid="stMarkdownContainer"] {{color:#ffffff;}}
    @media (max-width: 900px) {{ .ncs-hero {{padding:14px 16px;}} [data-testid="column"], [data-testid="stColumn"] {{min-width:100% !important;}} }}
    .ncs-notice {{margin-top:22px; padding:12px 14px; border:1px solid {t['grid']}; border-radius:12px; color:{t['muted']}; font-size:.82rem; background:{t['card']};}}
    </style>""", unsafe_allow_html=True)
    if name == 'McKinsey-inspired':
        st.markdown("""<style>
        [data-testid="stHeading"] h1, [data-testid="stHeading"] h2,
        [data-testid="stHeading"] h3, .ncs-hero h1 {
            font-family:Georgia, 'Times New Roman', serif !important;
            font-weight:400 !important; letter-spacing:-.025em;
        }
        [data-testid="stMetricLabel"] p {font-size:.8rem; font-weight:600; letter-spacing:.02em;}
        .ncs-sub {font-size:.95rem; line-height:1.5;}
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


def production_chart(profile, oil_unit, gas_unit, title):
    x = profile['period'] if 'period' in profile else profile['year'].astype(str)
    figure = make_subplots(rows=1, cols=2, subplot_titles=[
        f'Oil ({oil_unit})', f'Gas ({gas_unit})',
    ], horizontal_spacing=.12)
    for column, values, label, color in [
        (1, profile['oil_mmbbl'] * oil_factor(oil_unit), f'Oil ({oil_unit})', THEMES[theme_name]['accent']),
        (2, profile['gas_msm3'] * gas_factor(gas_unit), f'Gas ({gas_unit})', THEMES[theme_name]['accent2']),
    ]:
        figure.add_trace(go.Bar(x=x, y=values, name=label, marker_color=color,
                               hovertemplate=f'%{{x}}<br>%{{y:,.2f}} {label}<extra></extra>'),
                         row=1, col=column)
        figure.update_yaxes(title_text=oil_unit if column == 1 else gas_unit,
                            rangemode='tozero', row=1, col=column)
    figure.update_xaxes(type='category', nticks=8, title_text='Period' if 'period' in profile else 'Year')
    figure.update_layout(title=title, height=280, showlegend=False,
                         margin=dict(l=45, r=20, t=80, b=40), bargap=.2)
    return figure


with st.sidebar:
    theme_name = st.selectbox("Interface theme", list(THEMES), index=0, key="theme_name")
apply_theme(theme_name)

st.markdown("""<div class="ncs-hero"><div class="ncs-kicker">Energy &amp; capital projects | Norwegian continental shelf</div><h1 style="margin:.15rem 0 .2rem 0">NCS Economics Workbench</h1><div class="ncs-sub">Assess project value. Understand downside exposure. Compare investment choices.</div></div>""", unsafe_allow_html=True)

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
    if ls.get('generator') is not None:
        st.session_state.generator = ls['generator']
    else:
        st.session_state.pop('generator', None)
    for key in list(st.session_state):
        if key.startswith('gen_input_'):
            del st.session_state[key]

years = sorted(st.session_state.profile.year.astype(int).unique().tolist())

PAGES = [
    'Dashboard',
    'Production & Economics',
    'Sensitivity & Breakeven',
    'Scenarios & Uncertainty',
    'Project & Export'
]

if 'active_page' not in st.session_state:
    st.session_state.active_page = PAGES[0]


def select_module(module):
    st.session_state.active_page = module


with st.container(key='module_navigation'):
    for column, module in zip(st.columns(len(PAGES)), PAGES):
        column.button(module, key=f'module_{module}', use_container_width=True,
                      type='primary' if st.session_state.active_page == module else 'secondary',
                      on_click=select_module, args=(module,))
page = st.session_state.active_page

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


def money_card(container, label, value, description):
    container.metric(label, compact_money(value),
                     help=f'{description}\n\nFull amount: {value * mf:,.2f} {money_unit} '
                          f'({value * 1e6:,.2f} NOK).')


def store_generator_input(name, key, factor):
    st.session_state.generator[name] = st.session_state[key] / factor


def generator_number(container, name, label, factor=1., step=1., minimum=0., maximum=None):
    """Keep canonical inputs separate from disposable, unit-specific widgets."""
    key = f'gen_input_{name}_{factor}'
    value = st.session_state.generator[name] * factor
    return container.number_input(
        label, min_value=float(minimum), max_value=None if maximum is None else float(maximum),
        value=float(value), step=float(step), format='%.10g', key=key,
        on_change=store_generator_input, args=(name, key, factor),
    ) / factor


def store_generator_choice(name, key):
    st.session_state.generator[name] = st.session_state[key]


def generator_choice(label, name, options):
    key = f'gen_input_{name}'
    return st.selectbox(label, options, index=options.index(st.session_state.generator[name]),
                        key=key, on_change=store_generator_choice, args=(name, key))


# ==============================================================================
# 1. DASHBOARD
# ==============================================================================
if page == 'Dashboard':
    st.subheader('Investment case at a glance')
    c1, c2, c3 = st.columns(3)
    c4, c5, c6 = st.columns(3)
    money_card(c1, 'Pre-tax project value', m['pre_tax_npv_mnok'], 'Net present value before tax.')
    money_card(c2, 'After-tax project value', m['after_tax_npv_mnok'], 'Net present value after tax.')
    c3.metric('After-tax return (IRR)', '—' if m['irr'] is None else f"{m['irr']:.1%}",
              help='Annualized internal rate of return on after-tax cash flows.')
    
    # Breakeven metric display with both $/bbl ($/Sm3) and deck factor
    if use_deck:
        if deck_be is not None and equiv_oil_be_usd_bbl is not None:
            be_str = f"${equiv_oil_be_usd_bbl:.1f}/bbl"
            c4.metric('Oil breakeven', be_str, help=f"Weighted deck oil breakeven: ${equiv_oil_be_usd_bbl:,.2f}/bbl (${equiv_oil_be_usd_sm3:,.2f}/Sm³), requiring a {deck_be:.3f}× factor on the market deck.")
        else:
            c4.metric('Oil breakeven', '—', help='No breakeven found in search range')
    else:
        if be is not None:
            c4.metric('Oil breakeven', f"${be:.1f}/bbl", help=f"Flat oil breakeven: ${be:,.2f}/bbl (${be*BBL_PER_SM3:,.2f}/Sm³)")
        else:
            c4.metric('Oil breakeven', '—')
            
    c5.metric('Minimum viable volume', '—' if mev is None else f"{mev:,.2f} million boe", help="Minimum economic hydrocarbon volume required for NPV = 0. boe = barrels of oil equivalent.")
    c6.metric('Payback period', m['payback_year'] or '—', help='First model period with non-negative cumulative after-tax cash flow.')
    st.caption('Value cards automatically use thousands, millions or billions of NOK. Hover over the help icons for full amounts; tables and plots retain the selected display units.')
    
    if cf.attrs.get('cutoff_year') is not None:
        st.info(f"Economic cessation: {cf.attrs.get('cutoff_year')} — {cf.attrs.get('cutoff_reason')}")
    st.caption(f"{money_basis.title()} money • entered {rate_basis} discount {disc:.2%} • effective {money_basis} discount {consistent_discount_rate(disc,rate_basis,money_basis,inflation):.2%}")
    
    cashflow_column, cumulative_column = st.columns(2)
    with cashflow_column:
        chart_cf = display_table(cf[['period','pre_tax_cf_mnok','after_tax_cf_mnok']])
        chart_cf = chart_cf.rename(columns={
            f'pre_tax_cf ({money_unit})': f'Pre-tax ({money_unit})',
            f'after_tax_cf ({money_unit})': f'After-tax ({money_unit})',
        })
        figure = px.bar(chart_cf, x='period', y=list(chart_cf.columns[1:]), barmode='group',
                        title='Period cash flow', labels={'value':money_unit, 'variable':'', 'period':'Period'})
        figure.add_hline(y=0, line_width=1)
        figure.update_xaxes(type='category', nticks=8)
        figure.update_layout(height=300, margin=dict(l=45, r=15, t=45, b=35),
                             legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0),
                             title=dict(y=.98), hovermode='x unified')
        render_chart(figure, use_container_width=True)
    with cumulative_column:
        cum = display_table(cf[['period','cumulative_cf_mnok','cumulative_npv_mnok']])
        cum = cum.rename(columns={
            f'cumulative_cf ({money_unit})': f'Cash flow ({money_unit})',
            f'cumulative_npv ({money_unit})': f'Discounted NPV ({money_unit})',
        })
        figure = px.line(cum, x='period', y=list(cum.columns[1:]), title='Cumulative value',
                         labels={'value':money_unit, 'variable':'', 'period':'Period'})
        figure.add_hline(y=0, line_width=1)
        figure.update_xaxes(type='category', nticks=8)
        figure.update_layout(height=300, margin=dict(l=45, r=15, t=45, b=35),
                             legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0),
                             title=dict(y=.98), hovermode='x unified')
        render_chart(figure, use_container_width=True)
    render_chart(production_chart(cf, oil_unit, gas_unit, 'Production profile'), use_container_width=True)


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
        if 'generator' not in st.session_state:
            positive_opex = st.session_state.profile.loc[st.session_state.profile.opex_mnok > 0, 'opex_mnok']
            defaults = FieldProfileSettings(
                start_year=int(st.session_state.profile.year.min()),
                capex_mnok=float(st.session_state.profile.capex_mnok.sum()),
                annual_opex_mnok=float(positive_opex.median()) if len(positive_opex) else 0.,
                decom_mnok=float(st.session_state.profile.decom_mnok.sum()),
            )
            st.session_state.generator = {**asdict(defaults), 'resource_basis':'Recoverable volumes'}
        field_type = generator_choice('Field / fluid case', 'field_type', list(FIELD_TYPES))
        resource_basis = generator_choice('Resource basis', 'resource_basis', [
            'Recoverable volumes', 'In-place volumes × recovery factor',
        ])
        st.caption(f'Volumes follow sidebar units: liquids in {oil_unit}, gas in {gas_unit}, costs in {money_unit}. '
                   'Plateau inputs are annual volumes at 100% uptime; uptime is applied once. '
                   'Use sales/export gas volumes, excluding reinjection and fuel.')
        st.caption('Changing resource basis reinterprets the resource numbers; review volumes and recovery factors after switching.')
        t1, t2, t3, t4 = st.columns(4)
        generator_number(t1, 'start_year', 'Development start year', minimum=1900, maximum=2200)
        generator_number(t2, 'development_years', 'Development lead time (years)', maximum=30)
        generator_number(t3, 'production_years', 'Production forecast (years)', minimum=1, maximum=100)
        generator_number(t4, 'uptime', 'Production uptime (%)', factor=100., step=1., minimum=1., maximum=100.)
        in_place = resource_basis == 'In-place volumes × recovery factor'
        resource_label = 'In-place' if in_place else 'Recoverable'
        liquids = field_type != 'Dry gas'
        primary_oil = field_type in ('Oil with associated gas', 'Independent oil and gas')
        primary_gas = field_type != 'Oil with associated gas'
        for fluid, enabled, primary, unit, factor in [
            ('oil', liquids, primary_oil, oil_unit, of),
            ('gas', True, primary_gas, gas_unit, gf),
        ]:
            if not enabled:
                continue
            fluid_label = 'Condensate' if fluid == 'oil' and field_type == 'Gas with condensate' else fluid.title()
            st.markdown(f'#### {fluid_label} resources' + (' & deliverability' if primary else ' / linked-fluid cap'))
            r1, r2 = st.columns(2)
            generator_number(r1, f'{fluid}_resources_' + ('mmbbl' if fluid == 'oil' else 'msm3'),
                             f'{resource_label} {fluid_label.lower()} ({unit})', factor, step=max(factor, .000001))
            if in_place:
                generator_number(r2, f'{fluid}_recovery_factor', f'{fluid_label} recovery factor (%)',
                                 factor=100., step=1., maximum=100.)
            if primary:
                p1, p2, p3, p4 = st.columns(4)
                generator_number(p1, f'{fluid}_plateau_' + ('mmbbl' if fluid == 'oil' else 'msm3'),
                                 f'{fluid_label} plateau ({unit}/year)', factor, step=max(factor, .000001))
                generator_number(p2, f'{fluid}_ramp_years', f'{fluid_label} ramp-up (years)', maximum=100.)
                generator_number(p3, f'{fluid}_plateau_years', f'{fluid_label} plateau duration (years)', maximum=100.)
                generator_number(p4, f'{fluid}_decline_rate', f'{fluid_label} annual decline (%)',
                                 factor=100., step=1., maximum=100.)
        if field_type == 'Oil with associated gas':
            generator_number(st, 'associated_gas_msm3_per_mmbbl',
                             f'Sales gas / oil ratio ({gas_unit} / {oil_unit})', gf / of,
                             step=max(gf / of, 1e-12))
        elif field_type == 'Gas with condensate':
            generator_number(st, 'condensate_mmbbl_per_msm3',
                             f'Condensate / sales gas ratio ({oil_unit} / {gas_unit})', of / gf,
                             step=max(.001 * of / gf, 1e-12))
            st.info('Condensate is stored in the oil/liquids column and valued using the oil price deck; '
                    'a separate condensate price, shrinkage and processing model is not included.')
        if field_type in ('Oil with associated gas', 'Gas with condensate'):
            st.caption('The linked-fluid ratio stays constant. Production stops when either recoverable resource cap is reached.')
        st.markdown('#### Development & operating costs')
        k1, k2, k3, k4 = st.columns(4)
        generator_number(k1, 'capex_mnok', f'Total development CAPEX ({money_unit})', mf, step=100. * mf)
        generator_number(k2, 'annual_opex_mnok', f'Fixed producing OPEX ({money_unit}/year)', mf, step=10. * mf)
        generator_number(k3, 'variable_opex_nok_boe', 'Variable OPEX (NOK/boe)', step=1.)
        generator_number(k4, 'decom_mnok', f'Decommissioning cost ({money_unit})', mf, step=100. * mf)
        generator_number(st, 'decom_lag_years', 'Decommissioning lag after last production (years)', maximum=30.)
        st.caption('CAPEX is phased evenly over development years (or booked in the first year for immediate start-up). '
                   'Fixed OPEX applies only in producing years. Decommissioning is booked after last production plus the lag; '
                   'the output horizon extends if needed. Costs are entered before engine escalation and tax.')
        fields = asdict(FieldProfileSettings())
        settings = {key: st.session_state.generator[key] for key in fields}
        for key in ('start_year', 'development_years', 'production_years', 'oil_ramp_years',
                    'gas_ramp_years', 'oil_plateau_years', 'gas_plateau_years', 'decom_lag_years'):
            settings[key] = int(settings[key])
        if not in_place:
            settings['oil_recovery_factor'] = settings['gas_recovery_factor'] = 1.
        generated = None
        try:
            generated = field_profile(FieldProfileSettings(**settings))
        except ValueError as exc:
            st.error(f'Cannot generate profile: {exc}')
        if generated is not None:
            render_chart(production_chart(generated, oil_unit, gas_unit, 'Generated production profile'), use_container_width=True)
            s1, s2, s3 = st.columns(3)
            s1.metric(f'Forecast liquids ({oil_unit})', f'{generated.oil_mmbbl.sum() * of:,.3f}')
            s2.metric(f'Forecast sales gas ({gas_unit})', f'{generated.gas_msm3.sum() * gf:,.3f}')
            s3.metric('First production', generated.attrs['first_production_year'])
            for fluid, column, factor, unit in [('oil', 'oil_mmbbl', of, oil_unit), ('gas', 'gas_msm3', gf, gas_unit)]:
                if fluid == 'oil' and not liquids:
                    continue
                cap = settings[f'{fluid}_resources_' + ('mmbbl' if fluid == 'oil' else 'msm3')] * settings[f'{fluid}_recovery_factor']
                remaining = max(0., cap - float(generated[column].sum()))
                st.caption(f'{fluid.title()} remaining outside forecast: {remaining * factor:,.3f} {unit}.')
            st.caption(f"Last production: {generated.attrs['last_production_year']} | "
                       f"Decommissioning: {generated.attrs['decommissioning_year']}. "
                       'Annual screening model; not a reservoir simulation or reserves certification.')
            with st.expander('Preview annual production & cost table'):
                st.dataframe(display_table(generated), use_container_width=True, hide_index=True)
                st.download_button('Download generated canonical profile CSV', generated.to_csv(index=False),
                                   'generated_profile.csv', 'text/csv')
            if st.button('Use generated profile as project profile', key='apply_generated_profile'):
                st.session_state.profile = validate_profile_table(generated)
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
            money_card(x1, 'P10 (10th percentile / downside)', ms['P10'], '10th-percentile after-tax NPV.')
            money_card(x2, 'P50 (Median)', ms['P50'], 'Median after-tax NPV.')
            money_card(x3, 'P90 (90th percentile / upside)', ms['P90'], '90th-percentile after-tax NPV.')
            money_card(x4, 'Mean', ms['mean'], 'Mean after-tax NPV.')
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
            money_card(c1, 'Current decision-tree value', tr['value'], 'Rolled-back value of the current decision tree.')
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
                {'time_resolution':time_resolution, 'capex_phasing':capex_phasing, 'cutoff':cutoff.__dict__,
                 'generator':st.session_state.get('generator')},
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
            money_card(st, 'Risked exploration EMV', pe['risked_emv_mnok'], 'Expected monetary value weighted by geological chance of success.')
            st.dataframe(display_table(pd.DataFrame(discovery_distribution(cos, dry, [DiscoveryCase('Small', .55, small), DiscoveryCase('Large', .45, large)]))), hide_index=True, use_container_width=True)
        with e2:
            st.markdown('### Model health & assurance')
            health = model_health(st.session_state.profile, active_deck, [.55,.45], {'cessation_year':cf.attrs.get('cutoff_year'),'decom_year':None}, recoverable_oil_mmbbl=float(st.session_state.profile.oil_mmbbl.sum())*1.05, money_basis=money_basis, discount_basis=rate_basis)
            st.dataframe(pd.DataFrame(health), hide_index=True, use_container_width=True)

st.divider()
st.markdown('<div style="text-align:center;opacity:.72;font-size:.82rem;padding:6px 0 18px"><b>Made by Merouane Hamdani</b> · Educational purposes only — non-commercial · NCS Economics Workbench</div>', unsafe_allow_html=True)
