"""Fetch the feed and track which posts are new."""

from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_KEYWORDS,
    DOMAIN,
    FETCH_TIMEOUT,
    NOTIFY_MAX_AGE,
    SEEN_IDS_LIMIT,
    STORAGE_VERSION,
)
from .parser import FeedError, Post, parse_feed

_LOGGER = logging.getLogger(__name__)

type ActusVilleConfigEntry = ConfigEntry[ActusVilleCoordinator]


class CannotConnect(Exception):
    """The feed could not be downloaded."""


async def async_fetch_feed(session: aiohttp.ClientSession, url: str) -> bytes:
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=FETCH_TIMEOUT)
        ) as response:
            response.raise_for_status()
            return await response.read()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise CannotConnect(f"Cannot fetch {url}: {err}") from err


def storage_key(entry_id: str) -> str:
    return f"{DOMAIN}.{entry_id}"


class ActusVilleCoordinator(DataUpdateCoordinator[list[Post]]):
    """Poll the feed. Data is every post in the feed, newest first."""

    config_entry: ActusVilleConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ActusVilleConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(minutes=entry.options[CONF_SCAN_INTERVAL]),
        )
        self._session = async_get_clientsession(hass)
        self._store: Store[list[str]] = Store(
            hass, STORAGE_VERSION, storage_key(entry.entry_id)
        )
        self._seen_ids: list[str] | None = None
        self._pending: list[Post] = []

    async def _async_setup(self) -> None:
        self._seen_ids = await self._store.async_load()

    async def _async_update_data(self) -> list[Post]:
        try:
            raw = await async_fetch_feed(self._session, self.config_entry.data[CONF_URL])
            posts = parse_feed(raw, self.config_entry.options[CONF_KEYWORDS])
        except (CannotConnect, FeedError) as err:
            raise UpdateFailed(str(err)) from err
        await self._async_track_new_posts(posts)
        return posts

    async def _async_track_new_posts(self, posts: list[Post]) -> None:
        seen = set(self._seen_ids or ())
        unseen = [post for post in posts if post.id not in seen]
        if not unseen:
            return
        if self._seen_ids is not None:
            cutoff = dt_util.utcnow() - NOTIFY_MAX_AGE
            self._pending.extend(
                post
                for post in reversed(unseen)
                if post.published is None or post.published >= cutoff
            )
        self._seen_ids = [post.id for post in unseen] + (self._seen_ids or [])
        del self._seen_ids[SEEN_IDS_LIMIT:]
        await self._store.async_save(self._seen_ids)

    def pop_new_posts(self) -> list[Post]:
        """Return the posts not announced yet, oldest first."""
        posts, self._pending = self._pending, []
        return posts
