"""Event fired for each new post."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EVENT_IMPORTANT_POST, EVENT_NEW_POST
from .coordinator import ActusVilleConfigEntry
from .entity import ActusVilleEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActusVilleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([ActusVilleNewPostEvent(entry.runtime_data)])


class ActusVilleNewPostEvent(ActusVilleEntity, EventEntity):
    """`info_importante` when a post contains a keyword, `nouveau_post` otherwise."""

    _attr_translation_key = "new_post"
    _attr_event_types = [EVENT_NEW_POST, EVENT_IMPORTANT_POST]

    @property
    def available(self) -> bool:
        # Going unavailable then back would replay the last event to state-triggered automations.
        return True

    @callback
    def _handle_coordinator_update(self) -> None:
        for post in self.coordinator.pop_new_posts():
            self._trigger_event(
                EVENT_IMPORTANT_POST if post.important else EVENT_NEW_POST,
                post.as_dict(),
            )
            self.async_write_ha_state()
