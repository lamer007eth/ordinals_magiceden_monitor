import asyncio
import json
import os
from datetime import datetime, timezone
from websockets.legacy.client import connect
from dotenv import load_dotenv
import aiohttp
import aiofiles

load_dotenv(".env")

# =========================
# ENV
# =========================
WS_URL = os.getenv("ME_WS_URL", "wss://wss-mainnet.magiceden.io/").strip()
COLLECTION_SYMBOL = os.getenv("COLLECTION_SYMBOL", "stones").strip()

TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
TELEGRAM_GENERAL_CHAT_ID = (os.getenv("TELEGRAM_GENERAL_CHAT_ID") or "").strip()
TELEGRAM_TRAIT_CHAT_ID = (os.getenv("TELEGRAM_TRAIT_CHAT_ID") or "").strip()  # optional second channel

RECONNECT_DELAY = int(os.getenv("RECONNECT_DELAY", "10"))
SEEN_FILE = os.getenv("SEEN_FILE", "seen_listings.txt")
TRAITS_FILTER_FILE = os.getenv("TRAITS_FILTER_FILE", "traits_filter.json")

COINGECKO_NFT_ID = os.getenv("COINGECKO_NFT_ID", "stones").strip()
PRICE_CACHE_SECONDS = int(os.getenv("PRICE_CACHE_SECONDS", "60"))

# Optional
MIN_PRICE_BTC = float(os.getenv("MIN_PRICE_BTC", "0") or 0)

HEADERS = [
    ("Origin", "https://magiceden.io"),
    ("User-Agent", "Mozilla/5.0"),
]

BTC_SYMBOL = "💰"
DOLLAR_SYMBOL = "💵"
GREEN_CIRCLE = "💹"
DIAMOND = "💎"
CYCLE = "♻️"


def require_env():
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_GENERAL_CHAT_ID:
        missing.append("TELEGRAM_GENERAL_CHAT_ID")
    if missing:
        raise SystemExit(f"Missing .env vars: {', '.join(missing)}")


def subscribe_collection_payload():
    return {
        "type": "subscribeCollection",
        "constraint": {
            "chain": "bitcoin",
            "collectionSymbol": COLLECTION_SYMBOL
        }
    }


SUBSCRIBE_TOPICS = {
    "eventName": "nx.Subscribe",
    "nx.Topics": ["*"]
}


# =========================
# TRAITS FILTER
# =========================
def load_traits_filter(path: str) -> dict:
    """
    traits_filter.json format (example):
    {
      "Stone Type": ["Crystal"],
      "Rarity Tier": ["IV", "V"]
    }
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            print(f"⚠️ {path} must be a JSON object {{trait_type: [values...]}}")
            return {}
        # normalize lists
        normalized = {}
        for k, v in data.items():
            if isinstance(v, list):
                normalized[str(k)] = [str(x) for x in v]
            else:
                normalized[str(k)] = [str(v)]
        return normalized
    except FileNotFoundError:
        print(f"⚠️ {path} not found — trait filtering disabled")
        return {}
    except Exception as e:
        print(f"⚠️ Failed to load {path}: {e}")
        return {}


def traits_match(traits: dict, rule: dict) -> bool:
    """
    rule: {"Trait": ["A","B"], "Trait2": ["X"]}
    match if ANY rule key matches (OR logic), like your old code:
      Stone Type == Crystal OR Rarity Tier in [IV,V]
    """
    if not rule:
        return False

    for trait_type, allowed_values in rule.items():
        v = traits.get(trait_type)
        if v is None:
            continue
        if str(v) in allowed_values:
            return True
    return False


# =========================
# SEEN / DEDUP
# =========================
async def load_seen(path: str) -> set[str]:
    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            lines = await f.readlines()
        return {line.strip() for line in lines if line.strip()}
    except FileNotFoundError:
        return set()


async def append_seen(path: str, item_id: str):
    async with aiofiles.open(path, "a", encoding="utf-8") as f:
        await f.write(item_id + "\n")


# =========================
# COINGECKO PRICE CACHE
# =========================
_price_cache_text = ""
_price_cache_ts = 0.0


async def fetch_price_data(session: aiohttp.ClientSession) -> str:
    """
    Returns formatted floor/vol text. Cached for PRICE_CACHE_SECONDS.
    """
    global _price_cache_text, _price_cache_ts

    now = asyncio.get_event_loop().time()
    if _price_cache_text and (now - _price_cache_ts) < PRICE_CACHE_SECONDS:
        return _price_cache_text

    url = f"https://api.coingecko.com/api/v3/nfts/{COINGECKO_NFT_ID}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            data = await resp.json()
            floor_price = float(data.get("floor_price", {}).get("usd", 0.0) or 0.0)
            volume = float(data.get("volume_24h", {}).get("usd", 0.0) or 0.0)
            text = f"{DIAMOND} Floor Price: ${floor_price:.2f}\n{CYCLE} 24h Vol: ${volume:.2f}"
            _price_cache_text = text
            _price_cache_ts = now
            return text
    except Exception as e:
        print(f"⚠️ CoinGecko error: {e}")
        return ""


# =========================
# PARSE LISTING
# =========================
def parse_listing(data: dict):
    token = data.get("token", {})
    meta = token.get("meta", {}) or {}

    name = meta.get("name", "Unknown")
    listed_price_btc = int(data.get("listedPrice", 0) or 0) / 1e8
    btc_usd_price = float(data.get("btcUsdPrice", 0) or 0.0)
    listed_price_usd = listed_price_btc * btc_usd_price

    img_url = meta.get("collection_page_img_url") or meta.get("image") or ""
    txid = token.get("genesisTransaction", "") or ""
    location = token.get("location", "") or ""

    if ":" in location:
        # e.g. "<txid>:<index>" -> "<txid>i<index>"
        inscription_id = location.split(":")[0] + "i" + location.split(":")[-1]
    else:
        inscription_id = txid + "i0"

    item_url = f"https://magiceden.io/ordinals/item-details/{inscription_id}"

    # traits
    attributes = meta.get("attributes", []) or []
    traits = {attr.get("trait_type"): attr.get("value") for attr in attributes if attr.get("trait_type")}

    return {
        "name": name,
        "price_btc": listed_price_btc,
        "price_usd": listed_price_usd,
        "btc_usd": btc_usd_price,
        "img": img_url,
        "url": item_url,
        "inscription_id": inscription_id,
        "traits": traits,
    }


# =========================
# TELEGRAM
# =========================
async def send_telegram_photo(
    session: aiohttp.ClientSession,
    chat_id: str,
    name: str,
    price_btc: float,
    price_usd: float,
    btc_usd: float,
    image_url: str,
    link: str,
    price_text: str,
):
    caption = (
        f"🆕 <b>{name}</b>\n"
        f"{BTC_SYMBOL} {price_btc:.8f} BTC\n"
        f"{DOLLAR_SYMBOL} ${price_usd:.2f}\n"
        f"===============\n"
        f"{price_text}\n"
        f"{GREEN_CIRCLE} 1 BTC = ${btc_usd:,.0f}"
    )

    keyboard = {"inline_keyboard": [[{"text": "КУПИТЬ", "url": link}]]}

    try:
        async with session.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": chat_id,
                "photo": image_url,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(keyboard),
            },
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                print(f"❌ Telegram error {resp.status}: {body[:200]}")
    except Exception as e:
        print(f"❌ Telegram send error: {e}")


# =========================
# MAIN LOOP
# =========================
async def listen():
    require_env()

    traits_rule = load_traits_filter(TRAITS_FILTER_FILE)
    seen = await load_seen(SEEN_FILE)

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with connect(WS_URL, extra_headers=HEADERS) as ws:
                    print(f"💹 Connected to Magic Eden WS | collection={COLLECTION_SYMBOL}")
                    await ws.send(json.dumps(subscribe_collection_payload()))
                    await ws.send(json.dumps(SUBSCRIBE_TOPICS))

                    while True:
                        msg = await ws.recv()

                        if msg == "ping":
                            await ws.send("pong")
                            continue

                        data = json.loads(msg)

                        if data.get("kind") != "list":
                            continue

                        listing = parse_listing(data)
                        insc_id = listing["inscription_id"]

                        # dedup
                        if insc_id in seen:
                            continue

                        # optional price filter
                        if MIN_PRICE_BTC > 0 and listing["price_btc"] < MIN_PRICE_BTC:
                            seen.add(insc_id)
                            await append_seen(SEEN_FILE, insc_id)
                            continue

                        price_text = await fetch_price_data(session)

                        # Always send to general channel
                        await send_telegram_photo(
                            session=session,
                            chat_id=TELEGRAM_GENERAL_CHAT_ID,
                            name=listing["name"],
                            price_btc=listing["price_btc"],
                            price_usd=listing["price_usd"],
                            btc_usd=listing["btc_usd"],
                            image_url=listing["img"],
                            link=listing["url"],
                            price_text=price_text,
                        )

                        # Trait match -> second channel
                        if TELEGRAM_TRAIT_CHAT_ID and traits_match(listing["traits"], traits_rule):
                            await send_telegram_photo(
                                session=session,
                                chat_id=TELEGRAM_TRAIT_CHAT_ID,
                                name=listing["name"],
                                price_btc=listing["price_btc"],
                                price_usd=listing["price_usd"],
                                btc_usd=listing["btc_usd"],
                                image_url=listing["img"],
                                link=listing["url"],
                                price_text=price_text,
                            )

                        seen.add(insc_id)
                        await append_seen(SEEN_FILE, insc_id)

            except Exception as e:
                print(f"❌ Connection error: {e}")

            print(f"🔁 Reconnect in {RECONNECT_DELAY}s...")
            await asyncio.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    try:
        asyncio.run(listen())
    except KeyboardInterrupt:
        print("⛔ Stopped by user")