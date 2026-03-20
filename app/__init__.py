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
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def get_tokens(self):
        now = time.time()
        # যদি ক্যাশে টোকেন না থাকে অথবা রিফ্রেশ টাইম হয়ে যায়
        if "PK" not in self.cache or (now - self.last_refresh) > TOKEN_REFRESH_THRESHOLD:
            self._refresh_tokens()
            self.last_refresh = now
        return self.cache.get("PK", [])

    def _fetch_one(self, cred):
        try:
            r = self.session.get(AUTH_URL, params=cred, timeout=10) # টাইমআউট একটু বাড়িয়ে দিলাম
            if r.status_code == 200:
                t = r.json().get("token")
                if t:
                    return t
        except Exception as e:
            print(f"Token fetch fail for {cred.get('uid')}: {e}")
        return None

    def _refresh_tokens(self):
        creds = self._load_pk_credentials()
        if not creds:
            print("CRITICAL: No credentials found to refresh tokens!")
            self.cache["PK"] = []
            return

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            tokens = list(ex.map(self._fetch_one, creds))

        tokens = [t for t in tokens if t]
        self.cache["PK"] = tokens
        print(f"Successfully refreshed {len(tokens)} tokens.")

    def _load_pk_credentials(self):
        try:
            # ১. প্রথমে এনভায়রনমেন্ট ভেরিয়েবল চেক করো
            env_data = os.getenv("PK_CONFIG")
            if env_data:
                return json.loads(env_data)

            # ২. ফাইল পাথ ঠিকভাবে খোঁজা (Vercel Friendly)
            # প্রজেক্টের রুট ডিরেক্টরি থেকে পাথ নেওয়া
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(base_dir, "config", "pk_config.json")

            print(f"DEBUG: Looking for config at {path}")

            if os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                    return data
            
            print("ERROR: pk_config.json not found in config folder")
            return []

        except Exception as e:
            print(f"PK config load error: {e}")
            return []

token_cache = TokenCache()
