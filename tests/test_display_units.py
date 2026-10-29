import itertools

import numpy as np
import pandas as pd
import pytest

from economics.conventions import BBL_PER_SM3, compact_money, display_frame, gas_factor, money_factor, oil_factor
from economics.project_io import validate_profile_table


@pytest.mark.parametrize('money,oil,gas', list(itertools.product(
    ['NOK', 'kNOK', 'MNOK', 'BNOK'],
    ['bbl', 'kbbl', 'MMbbl', 'MSm3 oil'],
    ['Sm3', 'kSm3', 'MSm3', 'BCM', 'MMboe'],
)))
def test_display_values_labels_and_profile_roundtrip(money, oil, gas):
    source = pd.DataFrame({
        'year': [2027, 2028], 'oil_mmbbl': [1.25, 2.5], 'gas_msm3': [169.9, 339.8],
        'capex_mnok': [1200., 0.], 'opex_mnok': [20., 40.], 'decom_mnok': [0., 200.],
        'npv_mnok': [-1200., 500.], 'irr': [.08, .1],
    })
    original = source.copy(deep=True)
    display = display_frame(source, money, oil, gas)
    assert not any(c.endswith(('_mnok', '_mmbbl', '_msm3')) for c in display)
    for column, factor, label in [
        ('oil_mmbbl', oil_factor(oil), f'oil ({oil})'),
        ('gas_msm3', gas_factor(gas), f'gas ({gas})'),
        ('npv_mnok', money_factor(money), f'npv ({money})'),
    ]:
        np.testing.assert_allclose(display[label], source[column]*factor)
    roundtrip = pd.DataFrame({'year': display.year})
    for column in ['oil_mmbbl', 'gas_msm3', 'capex_mnok', 'opex_mnok', 'decom_mnok']:
        suffix = column.rsplit('_', 1)[1]
        unit, factor = {'mmbbl': (oil, oil_factor(oil)), 'msm3': (gas, gas_factor(gas)),
                        'mnok': (money, money_factor(money))}[suffix]
        roundtrip[column] = display[f'{column.rsplit("_", 1)[0]} ({unit})'] / factor
    canonical = validate_profile_table(roundtrip)
    np.testing.assert_allclose(canonical.drop(columns='year'), source[canonical.columns].drop(columns='year'), rtol=1e-12)
    pd.testing.assert_frame_equal(source, original)
    pd.testing.assert_series_equal(display.irr, source.irr)


def test_physical_conversion_reference_values():
    assert 1 * oil_factor('bbl') == 1_000_000
    assert BBL_PER_SM3 * oil_factor('MSm3 oil') == pytest.approx(1)
    assert 1000 * gas_factor('BCM') == 1
    assert 169.9 * gas_factor('MMboe') == pytest.approx(1)
    assert 1 * money_factor('NOK') == 1_000_000


@pytest.mark.parametrize('value,expected', [
    (4925.91, '4.93 billion NOK'),
    (23.5, '23.50 million NOK'),
    (-4925.91, '-4.93 billion NOK'),
    (.25, '250.00 thousand NOK'),
    (.000025, '25.00 NOK'),
    (0, '0.00 NOK'),
    (999.999, '1.00 billion NOK'),
    (1_500_000, '1.50 trillion NOK'),
])
def test_compact_card_amounts_are_explicit_and_readable(value, expected):
    assert compact_money(value) == expected


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_compact_card_rejects_nonfinite_amounts(value):
    with pytest.raises(ValueError, match='finite'):
        compact_money(value)
