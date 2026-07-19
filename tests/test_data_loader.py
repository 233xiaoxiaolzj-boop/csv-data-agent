import pytest

from data_loader import load_csv


def test_loads_utf8_comma_csv():
    loaded = load_csv("城市,销量\n深圳,10\n广州,8\n".encode("utf-8"))

    assert loaded.dataframe.shape == (2, 2)
    assert loaded.delimiter == ","
    assert loaded.dataframe.iloc[0]["城市"] == "深圳"


def test_detects_semicolon_and_gb18030():
    loaded = load_csv("城市;销量\n深圳;10\n".encode("gb18030"))

    assert loaded.delimiter == ";"
    assert loaded.encoding == "gb18030"


def test_rejects_empty_file():
    with pytest.raises(ValueError, match="为空"):
        load_csv(b"")


def test_rejects_duplicate_column_names():
    with pytest.raises(ValueError, match="重复字段名"):
        load_csv(b"region,units,units\nSouth,1,2\n")
