"""Constants for the Actus Ville integration."""

from datetime import timedelta

DOMAIN = "actus_ville"

CONF_KEYWORDS = "keywords"
CONF_MAX_POSTS = "max_posts"

DEFAULT_SCAN_INTERVAL = 30
DEFAULT_MAX_POSTS = 10
DEFAULT_KEYWORDS = (
    "coupure",
    "interruption",
    "panne",
    "enedis",
    "électricité",
    "eau potable",
    "fuite",
    "gaz",
    "alerte",
    "vigilance",
    "inondation",
    "crue",
    "canicule",
    "restriction",
)

ATTR_POSTS = "posts"

EVENT_NEW_POST = "nouveau_post"
EVENT_IMPORTANT_POST = "info_importante"

NOTIFY_MAX_AGE = timedelta(days=3)
FETCH_TIMEOUT = 30
STORAGE_VERSION = 1
SEEN_IDS_LIMIT = 500
