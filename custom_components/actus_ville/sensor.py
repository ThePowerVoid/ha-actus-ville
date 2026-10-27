"""Sensor holding the latest posts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_POSTS, CONF_MAX_POSTS
from .coordinator import ActusVilleConfigEntry
from .entity import ActusVilleEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActusVilleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([ActusVilleLastPostSensor(entry.runtime_data)])


class ActusVilleLastPostSensor(ActusVilleEntity, SensorEntity):
    """State is the date of the latest post; the posts themselves are an attribute."""

    _attr_translation_key = "last_post"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _unrecorded_attributes = frozenset({ATTR_POSTS})

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.data[0].published if self.coordinator.data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        max_posts = self.coordinator.config_entry.options[CONF_MAX_POSTS]
        return {ATTR_POSTS: [post.as_dict() for post in self.coordinator.data[:max_posts]]}
