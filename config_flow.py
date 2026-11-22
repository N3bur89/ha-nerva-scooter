"""Config flow: indirizzo BLE, VIN, codice modello."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS

from .const import CONF_MODEL, CONF_PASSWORD, CONF_VIN, DEFAULT_MODEL, DOMAIN, MODELS
from .protocol import VIN_RE


class NervaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            vin = user_input[CONF_VIN].strip().upper()
            if not VIN_RE.match(vin):
                errors[CONF_VIN] = "invalid_vin"
            elif user_input.get(CONF_PASSWORD) and len(user_input[CONF_PASSWORD]) != 8:
                errors[CONF_PASSWORD] = "invalid_password"
            else:
                address = user_input[CONF_ADDRESS].split(" ")[0].upper()
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Nerva {vin[-6:]}",
                    data={CONF_ADDRESS: address, CONF_VIN: vin, CONF_MODEL: user_input[CONF_MODEL], CONF_PASSWORD: user_input.get(CONF_PASSWORD, "")},
                )
        found = {
            f"{d.address} ({d.name})": f"{d.address} ({d.name})"
            for d in bluetooth.async_discovered_service_info(self.hass, connectable=True)
        }
        addr_field = vol.In(found) if found else str
        schema = vol.Schema({
            vol.Required(CONF_ADDRESS): addr_field,
            vol.Required(CONF_VIN): str,
            vol.Required(CONF_MODEL, default=DEFAULT_MODEL): vol.In(MODELS),
            vol.Optional(CONF_PASSWORD, default=""): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
