"""The Azure IoT Hub integration."""
from __future__ import annotations

from datetime import timedelta
import json
import logging

from azure.iot.device import IoTHubDeviceClient, Message

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, IOT_HUB_DEVICE_CONNECTION_STRING, MINUTE_TIMER

_LOGGER = logging.getLogger(__name__)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.LIGHT]


# async def send_data_to_iot_hub(hass: HomeAssistant, client: IoTHubDeviceClient):
#     """Function to send data to Azure IoT Hub."""
#     message = Message("Your data here")
#     await hass.async_add_executor_job(client.send_message, message)
#     _LOGGER.info("Sent data to IoT Hub")


async def send_data_to_iot_hub(
    hass: HomeAssistant, client: IoTHubDeviceClient, entry: ConfigEntry
):
    """Collect data from multiple entities and send as a single message to IoT Hub."""
    monitored_entities = entry.options.get("monitored_entities", [])

    data_to_send = {}

    for entity_id in monitored_entities:
        state = hass.states.get(entity_id)
        if state:
            data_to_send[entity_id] = {
                "state": state.state,
                "attributes": dict(state.attributes),
            }

    if data_to_send:
        message_string = json.dumps(data_to_send)
        message = Message(message_string)

        # Send the data to Azure IoT Hub
        await hass.async_add_executor_job(client.send_message, message)
        _LOGGER.info("Sent data to IoT Hub for configured entities")
    else:
        _LOGGER.info("No data to send to IoT Hub")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Azure IoT Hub from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    _LOGGER.warning(f"Using STRING: {entry.data[IOT_HUB_DEVICE_CONNECTION_STRING]}")

    # Create the IoT Hub client instance.
    client = IoTHubDeviceClient.create_from_connection_string(
        entry.data[IOT_HUB_DEVICE_CONNECTION_STRING]
    )

    # Connect to Azure IoT Hub to validate the connection.
    try:
        await hass.async_add_executor_job(client.connect)
    except Exception as ex:
        _LOGGER.error(f"Failed to connect to Azure IoT Hub: {ex}")
        client.shutdown()  # If client has shutdown method to safely cleanup
        return False

    # Store the client instance in `hass.data`.
    hass.data[DOMAIN][entry.entry_id] = client

    # Forward the entry setup to any platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up the scheduled task to send data.
    send_interval = timedelta(minutes=MINUTE_TIMER)

    async def scheduled_send(now):
        # Make sure to pass the `client` from `hass.data` corresponding to the current `entry.entry_id`.
        await send_data_to_iot_hub(hass, hass.data[DOMAIN][entry.entry_id], entry)

    # Schedule the data sending.
    async_track_time_interval(hass, scheduled_send, send_interval)

    # Reload function should be defined before it's added to the entry update listeners.
    async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
        """Handle reload of an entry."""
        await async_unload_entry(hass, entry)
        await async_setup_entry(hass, entry)

    # Only add the reload listener if it does not exist.
    if not entry.update_listeners:
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    client: IoTHubDeviceClient = hass.data[DOMAIN][entry.entry_id]

    # Disconnect your client cleanly
    await hass.async_add_executor_job(client.shutdown)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Remove the client from hass.data after a successful unload
        hass.data[DOMAIN].pop(entry.entry_id)
