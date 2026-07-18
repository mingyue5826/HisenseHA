import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD
from .pyhisenseapi import HiSenseLogin

SUPPORTED_DEVICE_TYPES = ["空调", "冰箱"]


class HisenseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        self._home_options = None
        self._access_token = None
        self._refresh_token = None
        self._device_info = None

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            hisense_login = HiSenseLogin(session=session)

            try:
                token_pair = await hisense_login.login(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except Exception:
                errors["base"] = "invalid_auth"
            else:
                if not token_pair:
                    errors["base"] = "invalid_auth"
                else:
                    access_token, refresh_token = token_pair
                    try:
                        self._home_options = await hisense_login.get_home_select_options(
                            access_token
                        )
                    except Exception:
                        errors["base"] = "cannot_connect"
                    else:
                        if self._home_options is None:
                            errors["base"] = "cannot_connect"
                        elif not self._home_options:
                            errors["base"] = "no_homes"
                        else:
                            self._access_token = access_token
                            self._refresh_token = refresh_token
                            return await self.async_step_home()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={
                "username_hint": "app login username",
                "password_hint": "app login password",
            },
            errors=errors,
        )

    async def async_step_home(self, user_input=None):
        errors = {}

        if user_input is not None:
            home_id = user_input["home_id"]
            session = async_get_clientsession(self.hass)
            hisense_login = HiSenseLogin(session=session)
            try:
                self._device_info = await hisense_login.get_all_devices(
                    self._access_token, home_id, self._refresh_token
                )
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                if self._device_info is None:
                    errors["base"] = "cannot_connect"
                elif not self._device_info:
                    errors["base"] = "no_devices"
                else:
                    return await self.async_step_device()

        return self.async_show_form(
            step_id="home",
            data_schema=vol.Schema(
                {vol.Required("home_id"): vol.In(self._home_options)}
            ),
            errors=errors,
        )

    async def async_step_device(self, user_input=None):
        errors = {}

        if user_input is not None:
            device_ids = user_input["device_ids"]
            if not device_ids:
                errors["base"] = "no_devices"
            else:
                devices = [
                    self._device_info[device_id]
                    for device_id in device_ids
                ]
                return self.async_create_entry(
                    title="Hisense Smart Control",
                    data={"devices": devices}
                )

        device_id_to_label = {}
        for device_id, info in self._device_info.items():
            label = info.get("label", device_id)
            device_type = info.get("device_type", "")
            device_id_to_label[device_id] = f"{label} ({device_type})"

        data_schema = vol.Schema(
            {
                vol.Required("device_ids"): cv.multi_select(device_id_to_label),
            }
        )
        return self.async_show_form(
            step_id="device",
            data_schema=data_schema,
            errors=errors,
        )
