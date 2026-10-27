import pytest
from unittest.mock import patch
from collections import namedtuple
from fastapi.testclient import TestClient

from app.main import app
from app.services.device_battery_service import device_battery_service
from app.schemas.device_battery import DeviceBatteryResponse

client = TestClient(app)

# Lightweight mock for psutil sbattery namedtuple
MockBattery = namedtuple("MockBattery", ["percent", "secsleft", "power_plugged"])


def test_successful_battery_reading():
    """Validates that a normal battery reading parses percentage, plugged status, and time left."""
    mock_batt = MockBattery(percent=50.0, secsleft=3600, power_plugged=True)
    with patch("psutil.sensors_battery", return_value=mock_batt):
        result = device_battery_service.get_battery_status()

    assert result["available"] is True
    assert result["battery_percent"] == 50.0
    assert result["is_plugged_in"] is True
    assert result["seconds_left"] == 3600
    assert "SYSTEM" in result["source"]
    assert "timestamp" in result


def test_system_with_no_battery():
    """Validates that a desktop PC or environment returning None produces available=False."""
    with patch("psutil.sensors_battery", return_value=None):
        result = device_battery_service.get_battery_status()

    assert result["available"] is False
    assert result["battery_percent"] is None
    assert result["is_plugged_in"] is None
    assert result["seconds_left"] == None
    assert result["source"] == "UNAVAILABLE"
    assert "timestamp" in result


def test_psutil_failure_exception_handling():
    """Validates that unexpected OS or sensor exceptions are swallowed safely without tracebacks."""
    with patch("psutil.sensors_battery", side_effect=RuntimeError("ACPI hardware bus failure")):
        result = device_battery_service.get_battery_status()

    assert result["available"] is False
    assert result["battery_percent"] is None
    assert result["source"] == "UNAVAILABLE"


def test_secsleft_negative_handling():
    """
    psutil returns -1 (POWER_TIME_UNKNOWN) or -2 (POWER_TIME_UNLIMITED) when AC is connected.
    The service must map negative seconds to None.
    """
    mock_batt = MockBattery(percent=85.5, secsleft=-2, power_plugged=True)
    with patch("psutil.sensors_battery", return_value=mock_batt):
        result = device_battery_service.get_battery_status()

    assert result["available"] is True
    assert result["battery_percent"] == 85.5
    assert result["is_plugged_in"] is True
    assert result["seconds_left"] is None


def test_api_response_schema_available():
    """Validates GET /api/device-battery and GET /api/v1/device-battery against DeviceBatteryResponse schema."""
    mock_batt = MockBattery(percent=50.0, secsleft=7200, power_plugged=False)
    with patch("psutil.sensors_battery", return_value=mock_batt):
        for path in ["/api/device-battery", "/api/v1/device-battery"]:
            response = client.get(path)
            assert response.status_code == 200
            data = response.json()
            # Validate schema parsing
            parsed = DeviceBatteryResponse(**data)
            assert parsed.available is True
            assert parsed.battery_percent == 50.0
            assert parsed.is_plugged_in is False
            assert parsed.seconds_left == 7200


def test_api_response_schema_unavailable():
    """Validates API schema when hardware battery is unavailable."""
    with patch("psutil.sensors_battery", return_value=None):
        response = client.get("/api/device-battery")
        assert response.status_code == 200
        data = response.json()
        parsed = DeviceBatteryResponse(**data)
        assert parsed.available is False
        assert parsed.battery_percent is None
        assert parsed.source == "UNAVAILABLE"


def test_real_host_device_battery_smoke():
    """Smoke test against the actual host running the tests to verify no unhandled crash."""
    status = device_battery_service.get_battery_status()
    assert isinstance(status, dict)
    assert "available" in status
    assert "source" in status
    assert "timestamp" in status
    if status["available"]:
        assert 0.0 <= status["battery_percent"] <= 100.0
        assert isinstance(status["is_plugged_in"], bool)
