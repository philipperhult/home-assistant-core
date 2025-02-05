"""Support for Krisinformation sensor."""
from datetime import timedelta
import logging
from typing import Any

from krisinformation import crisis_alerter as krisinformation

# Importing necessary modules and classes.
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

# Import custom costants
from .const import CONF_COUNTY, DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

# Minimum time between updates for geolocation events.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

# String literals for the sensor.
NO_ALARM_SV = "Inga larm"
NO_ALARM_EN = "No alarms"


class Error(Exception):
    """Base class for exceptions in this module."""


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor associated with the Krisinformation integration when a configuration entry is added to Home Assistant."""
    name = config.data.get(CONF_NAME, DEFAULT_NAME + " - Sweden")
    county = config.data[CONF_COUNTY]
    language = hass.config.language

    crisis_alerter = krisinformation.CrisisAlerter(county, language)

    sensor = CrisisAlerterSensorCounty(hass, config.entry_id, name, crisis_alerter)

    async_add_entities([sensor], False)


class CrisisAlerterSensorCounty(SensorEntity):
    """Implementation of Krisinformations crisis alerter sensor."""

    _attr_attribution = "Alerts provided by Krisinformation"
    _attr_icon = "mdi:alert"

    def __init__(
        self,
        hass: HomeAssistant,
        unique_id: str,
        name: str,
        crisis_alerter: krisinformation.CrisisAlerter,
    ) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._hass = hass
        self._crisis_alerter = crisis_alerter
        self._state: str | None = None
        self._web: str | None = None
        self._published: str | None = None
        self._area: str | None = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes. Provides additional attributes for the sensor's state."""
        return {
            "link": self._web,
            "published": self._published,
            "county": self._area,
        }

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added. Listens for the Home Assistant startup event and triggers the first_update method accordingly."""
        await self._init_updates()

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def state(self):
        """Return the current state of the sensor."""
        return self._state

    async def _init_updates(self):
        """Run first update and write state. Initiates the first update and writes the state to Home Assistant."""
        await self._update()
        async_track_time_interval(
            self.hass, self._update, MIN_TIME_BETWEEN_UPDATES, cancel_on_shutdown=True
        )

    async def _update(self, _=None) -> None:
        """Get the latest alerts. Fetches the latest crisis alerts from Krisinformation for the specified county and extracts relevant information."""
        try:

            def getvmas():
                return self._crisis_alerter.vmas()

            response = await self.hass.async_add_executor_job(getvmas)
            location = self._crisis_alerter.county
            if len(response) > 0:
                for news in response:
                    county = news["Area"][0]["Description"]
                    if county == location:
                        self._state = news["PushMessage"][:255]  # Crashes if not capped
                        self._web = news["Web"]
                        self._published = news["Published"]
                        self._area = county
                        break
                    self._state = (
                        NO_ALARM_SV
                        if self._crisis_alerter.language == "sv"
                        else NO_ALARM_EN
                    )

            else:
                self._state = (
                    NO_ALARM_SV
                    if self._crisis_alerter.language == "sv"
                    else NO_ALARM_EN
                )
        except Error as error:
            _LOGGER.error("Error fetching data: %s", error)
            self._state = "Unavailable"
