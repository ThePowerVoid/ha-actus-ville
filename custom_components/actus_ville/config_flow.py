"""Config and options flows for Actus Ville."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL, CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_KEYWORDS,
    CONF_MAX_POSTS,
    DEFAULT_KEYWORDS,
    DEFAULT_MAX_POSTS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import CannotConnect, async_fetch_feed
from .parser import FeedError, parse_feed

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(),
        vol.Required(CONF_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCAN_INTERVAL): NumberSelector(
            NumberSelectorConfig(
                min=5,
                max=1440,
                step=5,
                unit_of_measurement="min",
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(CONF_MAX_POSTS): NumberSelector(
            NumberSelectorConfig(min=1, max=50, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_KEYWORDS): TextSelector(TextSelectorConfig(multiple=True)),
    }
)


def _clean_options(user_input: Mapping[str, Any]) -> dict[str, Any]:
    keywords = dict.fromkeys(
        keyword.strip() for keyword in user_input.get(CONF_KEYWORDS, []) if keyword.strip()
    )
    return {
        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
        CONF_MAX_POSTS: int(user_input[CONF_MAX_POSTS]),
        CONF_KEYWORDS: list(keywords),
    }


class ActusVilleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a town feed."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip()
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()
            try:
                parse_feed(await async_fetch_feed(async_get_clientsession(self.hass), url))
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except FeedError:
                errors["base"] = "invalid_feed"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME].strip(),
                    data={CONF_URL: url},
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_MAX_POSTS: DEFAULT_MAX_POSTS,
                        CONF_KEYWORDS: list(DEFAULT_KEYWORDS),
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ActusVilleOptionsFlow:
        return ActusVilleOptionsFlow()


class ActusVilleOptionsFlow(OptionsFlow):
    """Change polling, list length and keywords."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=_clean_options(user_input))
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
