import pandas as pd
import pytest

from executor import execute_code, validate_code


def test_executes_safe_dataframe_analysis():
    df = pd.DataFrame({"city": ["A", "A", "B"], "sales": [2, 3, 7]})
    output = execute_code("result = df.groupby('city')['sales'].sum()", df)
    assert output.result.to_dict() == {"A": 5, "B": 7}


def test_safe_builtins_are_available():
    df = pd.DataFrame({"sales": [2, 3, 7]})
    output = execute_code("result = round(df['sales'].mean(), 2)", df)
    assert output.result == 4.0


@pytest.mark.parametrize(
    "code",
    [
        "import os\nresult = 1",
        "result = open('secret.txt').read()",
        "result = df.to_csv('x.csv')",
        "result = df.__class__",
        "result = pd.read_pickle('x.pkl')",
        "plt.show()\nresult = 1",
        "plt.pause(1)\nresult = 1",
        "for value in range(10):\n    result = value",
    ],
)
def test_rejects_unsafe_code(code):
    with pytest.raises(ValueError):
        validate_code(code)


def test_requires_result_assignment():
    df = pd.DataFrame({"sales": [1, 2]})
    with pytest.raises(ValueError, match="result"):
        execute_code("total = df['sales'].sum()", df)
