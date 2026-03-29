"""Constants for HiSense Integration."""
DOMAIN = "hisense"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"


def climate_limits_signal(device_id: str) -> str:
    """Dispatcher signal when per-device climate min/max limits change."""
    return f"{DOMAIN}_climate_limits_{device_id}"
