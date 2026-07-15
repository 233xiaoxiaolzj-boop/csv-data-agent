import pandas as pd
import pytest

from executor import execute_code, validate_code


def test_executes_safe_dataframe_analysis():
    df = pd.DataFrame({"city": ["A", "A", "B"], "sales": [2, 3, 7]})
    output = execute_code("result = df.groupby('city')['sales'].sum()", df)
    assert output.result.to_dict() == {"A": 5, "B": 7}


@pytest.mark.parametrize("code", [
    "import os\nresult = 1",
    "result = open('secret.txt').read()",
    "result = df.to_csv('x.csv')",
])
def test_rejects_unsafe_code(code):
    with pytest.raises(ValueError):
        validate_code(code)
