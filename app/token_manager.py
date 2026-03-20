import os
import json
import time
import logging
import requests
import concurrent.futures
from cachetools import TTLCache
from datetime import timedelta
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

AUTH_URL = os.getenv(
    "AUTH_URL",
    "https://alonejwtgeneratorapiv1.vercel.app/token"
)

CACHE_DURATION = timedelta(hours=7).seconds
TOKEN_REFRESH_THRESHOLD = timedelta(hours=6).seconds


class TokenCache:
    def __init__(self):
        self.cache = TTLCache(maxsize=5, ttl=CACHE_DURATION)
        self.last_refresh = 0

        # ✅ BIG connection pool (pool warning fix)
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    # ======================
    # GET TOKENS
    # ======================
    def get_tokens(self):
        now = time.time()

        if (
            "PK" not in self.cache or
            (now - self.last_refresh) > TOKEN_REFRESH_THRESHOLD
        ):
            self._refresh_tokens()
            self.last_refresh = now

        return self.cache.get("PK", [])

    # ======================
    # PARALLEL TOKEN FETCH ⚡
    # ======================
    def _fetch_one(self, cred):
        try:
            r = self.session.get(
                AUTH_URL,
                params=cred,
                timeout=6
            )

            if r.status_code == 200:
                t = r.json().get("token")
                if t:
                    logger.info(f"✅ PK token OK {cred['uid']}")
                    return t
        except Exception as e:
            logger.warning(f"❌ PK token fail {cred['uid']} {e}")

        return None

    def _refresh_tokens(self):
        creds = self._load_pk_credentials()

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
            tokens = list(ex.map(self._fetch_one, creds))

        tokens = [t for t in tokens if t]
        self.cache["PK"] = tokens

        logger.info(f"⚡ PK tokens refreshed = {len(tokens)}")

    # ======================
    # LOAD CREDS
    # ======================
    def _load_pk_credentials(self):
        try:
            env_data = os.getenv("PK_CONFIG")
            if env_data:
                return json.loads(env_data)

            path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config",
                "pk_config.json"
            )

            if os.path.exists(path):
                with open(path) as f:
                    return json.load(f)

            return []

        except Exception as e:
            logger.error(f"PK config load error: {e}")
            return []


# ======================
# HEADERS
# ======================
def get_headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Dalvik/2.1.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }


token_cache = TokenCache()