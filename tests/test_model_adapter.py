import pytest

from rlls_demo.model_adapter import MockModelAdapter, ModelContractError


def test_missing_model_key_has_clear_error():
    adapter = MockModelAdapter(["weather_temp", "weather_rain"])
    with pytest.raises(ModelContractError, match="weather_rain"):
        adapter.predict({"weather_temp": 25})


def test_mock_is_explicit():
    adapter = MockModelAdapter(["weather_temp", "weather_rain"])
    result = adapter.predict({"weather_temp": 25, "weather_rain": 0})
    assert result.is_mock is True
    assert result.label.startswith("MOCK:")
