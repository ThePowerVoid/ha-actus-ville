"""Base entity for Actus Ville."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ActusVilleCoordinator


class ActusVilleEntity(CoordinatorEntity[ActusVilleCoordinator]):
    """An entity attached to the town's service device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ActusVilleCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{self._attr_translation_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )
