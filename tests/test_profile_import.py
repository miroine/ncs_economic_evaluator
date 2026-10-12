import io

import pandas as pd
import pytest

from economics.project_io import load_profile_table, validate_profile_table


def test_profile_csv_import_normalizes_columns_and_sorts_years():
    raw=b'year,oil_mmbl,gas_msm3,capex_mnok,opex_mnok\n2028,2,3,4,5\n2027,1,2,3,4\n'
    profile=load_profile_table(raw,'profile.csv')
    assert profile.year.tolist()==[2027,2028]
    assert profile.oil_mmbbl.tolist()==[1,2]
    assert profile.decom_mnok.tolist()==[0,0]


def test_profile_excel_import():
    source=io.BytesIO()
    pd.DataFrame([{'year':2027,'oil_mmbbl':1,'gas_msm3':2,'capex_mnok':3,'opex_mnok':4,'decom_mnok':5}]).to_excel(source,index=False)
    profile=load_profile_table(source.getvalue(),'profile.xlsx')
    assert profile.loc[0,'decom_mnok']==5


def test_profile_validation_rejects_duplicate_years_and_missing_columns():
    row={'year':2027,'oil_mmbbl':1,'gas_msm3':2,'capex_mnok':3,'opex_mnok':4}
    with pytest.raises(ValueError,match='unique whole numbers'):
        validate_profile_table([row,row])
    with pytest.raises(ValueError,match='Missing profile columns'):
        validate_profile_table([{'year':2027}])
