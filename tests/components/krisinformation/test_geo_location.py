"""The tests for the krisinformation geo_location."""
from unittest.mock import patch

from freezegun import freeze_time

from homeassistant.components import geo_location
from homeassistant.components.krisinformation import generate_mock_event
from homeassistant.components.krisinformation.geo_location import (
    MIN_TIME_BETWEEN_UPDATES,
)
from homeassistant.const import EVENT_HOMEASSISTANT_START, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.krisinformation.const import MOCK_CONFIG


async def test_entity_lifecycle(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the general setup of the integration."""
    config_entry = MockConfigEntry(
        domain="krisinformation",
        data=MOCK_CONFIG,
        title="Krisinformation",
        unique_id=123456789,
    )

    config_entry.add_to_hass(hass)

    # Patching 'utcnow' to gain more control over the timed update.
    utcnow = dt_util.utcnow()
    with freeze_time(utcnow), patch(
        "krisinformation.crisis_alerter.CrisisAlerter.vmas", is_test=True
    ) as mock_feed_update:
        mock_feed_update.return_value = [
            generate_mock_event("Test-VMA-1337-1", "Test VMA 1")
        ]

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # # Artificially trigger update and collect events.
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        # 1 geolocation and 1 sensor entities
        assert (
            len(hass.states.async_entity_ids("geo_location"))
            + len(hass.states.async_entity_ids("sensor"))
            == 2
        )

        entity_registry = er.async_get(hass)
        assert len(entity_registry.entities) == 1

        state = [
            hass.states.get(entity_id)
            for entity_id in hass.states.async_entity_ids(geo_location.DOMAIN)
        ][0]

        assert state is not None

        assert state.attributes == {
            "friendly_name": "Test VMA 1",
            "icon": "mdi:public",
            "latitude": 9.11,
            "longitude": 57.7,
            "source": "krisinformation",
            "unit_of_measurement": UnitOfLength.KILOMETERS,
            "county": "Värmlands län",
            "link": "krisinformation.se",
            "published": "2023-03-29T11:02:11+02:00",
        }

        # Simulate an update - two existing, one new entry, one outdated entry
        mock_feed_update.return_value = [
            generate_mock_event("Test-VMA-1337-1", "Test VMA 1"),
            generate_mock_event("Test-VMA-1337-2", "Test VMA 2"),
        ]
        async_fire_time_changed(hass, utcnow + MIN_TIME_BETWEEN_UPDATES)
        await hass.async_block_till_done()

        state = [
            hass.states.get(entity_id)
            for entity_id in hass.states.async_entity_ids(geo_location.DOMAIN)
        ][0]

        assert (
            len(hass.states.async_entity_ids("geo_location"))
            + len(hass.states.async_entity_ids("sensor"))
            == 3
        )
