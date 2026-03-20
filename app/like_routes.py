from flask import Blueprint, request, jsonify
import asyncio
import logging
import aiohttp
import requests
from datetime import datetime, timezone

from .utils.protobuf_utils import encode_uid, decode_info, create_protobuf
from .utils.crypto_utils import encrypt_aes
from .token_manager import get_headers

logger = logging.getLogger(__name__)

like_bp = Blueprint("like_bp", __name__)

_SERVERS = {}
_token_cache = None


# ---------------- ASYNC POST ---------------- #

async def async_post(url, data, token):
    try:
        headers = get_headers(token)
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=data, headers=headers) as r:
                if r.status == 200:
                    return await r.read()
                logger.warning(f"POST {url} → {r.status}")
                return None

    except Exception as e:
        logger.error(f"Async post fail {url}: {e}")
        return None


# ---------------- REGION DETECT ---------------- #

async def detect_player(uid):

    uid_bytes = bytes.fromhex(encode_uid(uid))

    for region, server_list in _SERVERS.items():

        tokens = _token_cache.get_tokens(region)
        if not tokens:
            continue

        for server in server_list:

            info_url = f"{server}/GetPlayerPersonalShow"

            resp = await async_post(info_url, uid_bytes, tokens[0])

            if resp:
                info = decode_info(resp)
                if info and info.AccountInfo.PlayerNickname:
                    return region, server, info

    return None, None, None


# ---------------- SEND LIKES ---------------- #

async def send_likes(uid, region, server):

    tokens = _token_cache.get_tokens(region)
    like_url = f"{server}/LikeProfile"

    encrypted = encrypt_aes(create_protobuf(uid, region))
    payload = bytes.fromhex(encrypted)

    tasks = [async_post(like_url, payload, t) for t in tokens]
    results = await asyncio.gather(*tasks)

    return sum(1 for r in results if r)


# ---------------- ROUTE ---------------- #

@like_bp.route("/like")
async def like_player():

    uid = request.args.get("uid")

    if not uid or not uid.isdigit():
        return jsonify({"error": "bad uid"}), 400

    region, server, info = await detect_player(uid)

    if not info:
        return jsonify({"error": "Player not found"}), 404

    before = info.AccountInfo.Likes
    name = info.AccountInfo.PlayerNickname

    added = await send_likes(uid, region, server)

    # verify
    tokens = _token_cache.get_tokens(region)
    verify = requests.post(
        f"{server}/GetPlayerPersonalShow",
        data=bytes.fromhex(encode_uid(uid)),
        headers=get_headers(tokens[0]),
        timeout=10
    )

    after = before
    if verify.status_code == 200:
        new = decode_info(verify.content)
        if new:
            after = new.AccountInfo.Likes

    return jsonify({
        "player": name,
        "uid": uid,
        "likes_before": before,
        "likes_after": after,
        "likes_added": after - before,
        "region": region,
        "server": server
    })


# ---------------- HEALTH ---------------- #

@like_bp.route("/health")
def health():
    return jsonify({
        "servers": {k: len(v) for k, v in _SERVERS.items()},
        "time": datetime.now(timezone.utc).isoformat()
    })


# ---------------- INIT ---------------- #

def initialize_routes(app, servers_config, token_cache_instance):
    global _SERVERS, _token_cache
    _SERVERS = servers_config
    _token_cache = token_cache_instance
    app.register_blueprint(like_bp)