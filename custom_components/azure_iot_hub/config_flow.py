"""Config flow for Azure IoT Hub integration."""
from __future__ import annotations

import logging
from typing import Any

from azure.iot.device import IoTHubDeviceClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_registry import async_get

from .const import DOMAIN, IOT_HUB_DEVICE_CONNECTION_STRING, MINUTE_TIMER

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        # Include the title in the description dict
        vol.Required(
            IOT_HUB_DEVICE_CONNECTION_STRING, description={"title": "Connection String"}
        ): str,
        vol.Required(
            MINUTE_TIMER,
            description={"title": "Minute Timer"},
            # You could validate that the minute timer is an integer and within a certain range if needed
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
    }
)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        # Get the entity registry
        entity_registry = async_get(self.hass)
        entities = {
            entry.entity_id: entry.original_name or entry.entity_id
            for entry in entity_registry.entities.values()
        }

        # Create a multiselect form
        options_schema = vol.Schema(
            {
                vol.Optional(
                    "monitored_entities",
                    default=self.config_entry.options.get("monitored_entities", []),
                ): cv.multi_select(entities)
            }
        )

        if user_input is not None:
            # Update the config entry
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=options_schema)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    client = IoTHubDeviceClient.create_from_connection_string(
        data[IOT_HUB_DEVICE_CONNECTION_STRING]
    )

    # Use a try-except block to handle potential exceptions
    try:
        client.connect()
    except ValueError:
        raise CannotConnect("ValueError - Failed to connect to IoT Hub")
    finally:
        client.disconnect()
        # Always disconnect in finally to ensure we do not leave the connection open

    # Validate minute timer here if needed (e.g., make a call to a function that uses this timer)
    # If validation fails, you might raise an appropriate exception

    # Return info that you want to store in the config entry, including the timer value
    return {"title": "IoT Hub Device", "minute_timer": data["minute_timer"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Azure IoT Hub."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
