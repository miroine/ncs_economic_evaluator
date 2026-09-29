import pandas as pd
from economics.engine import Assumptions, calculate_cashflow
from economics.market import default_market_deck, aligned_market_deck
from economics.advanced_analysis import spider, exceedance_curve, excel_workbook

def profile():
    return pd.DataFrame({'year':[2027,2028,2029],'oil_mmbbl':[1.,1.,1.],'gas_msm3':[0.,0.,0.],'capex_mnok':[100.,0.,0.],'opex_mnok':[0.,0.,0.],'decom_mnok':[0.,0.,0.]})

def test_market_deck_drives_price_and_fx():
    d=default_market_deck([2027,2028,2029],75,.35,10.5); d.loc[1,'oil_usd_bbl']=100; d.loc[1,'usd_nok']=11
    cf=calculate_cashflow(profile(),Assumptions(),d)
    assert cf.loc[1,'oil_price_usd_bbl']==100
    assert cf.loc[1,'usd_nok']==11

def test_market_deck_interpolates():
    d=pd.DataFrame({'year':[2027,2029],'oil_usd_bbl':[70.,90.],'gas_usd_sm3':[.3,.5],'usd_nok':[10.,12.]})
    a=aligned_market_deck([2027,2028,2029],d)
    assert a.loc[1,'oil_usd_bbl']==80

def test_spider_has_base_points():
    s=spider(profile(),Assumptions(),None,variables=('Oil price','CAPEX'),changes=(0,10))
    assert len(s)==4 and set(s.variable)=={'Oil price','CAPEX'}

def test_exceedance_sorted():
    e=exceedance_curve([3,1,2]); assert e.npv_mnok.tolist()==[1.,2.,3.]

def test_excel_export_nonempty():
    p=profile(); a=Assumptions(); d=default_market_deck(p.year); cf=calculate_cashflow(p,a,d)
    data=excel_workbook(a,p,cf,d,metadata={'author':'Merouane Hamdani'})
    assert data[:2]==b'PK' and len(data)>1000
