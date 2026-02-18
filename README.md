# Ordinals Magic Eden Monitor 🧿📡

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Bitcoin](https://img.shields.io/badge/Bitcoin-Ordinals-orange)
![MagicEden](https://img.shields.io/badge/Marketplace-MagicEden-black)
![Telegram](https://img.shields.io/badge/Telegram-alerts-2CA5E0)
![Type](https://img.shields.io/badge/Type-Monitoring-purple)
![API](https://img.shields.io/badge/API-WebSocket%20%2B%20REST-grey)

Real-time **Ordinals (Bitcoin NFTs)** listing monitor for **Magic Eden**.

Tracks new listings, detects rare traits, fetches floor price & volume data and sends **Telegram alerts** to multiple channels.

---

## ✨ Features

* 🆕 Detects **new NFT listings** instantly via WebSocket
* 🏷️ Filters listings by **traits / attributes**
* 📩 Sends alerts to **general** and **rare traits** channels
* 💰 Displays price in **BTC + USD**
* 📊 Fetches **Floor Price** & **24h Volume**
* 🖼️ Sends NFT image preview
* 🔘 Inline “Buy” button
* 🧠 Deduplicates listings (no spam on reconnect)

---

## 📦 Project structure

```text
ordinals_magiceden_monitor/
├─ ordinals_magiceden_monitor.py
├─ traits_filter.json
├─ .env.example
├─ requirements.txt
├─ .gitignore
└─ README.md
```

---

## 🚀 Quick start

### 1) Install

```bash
pip install -r requirements.txt
```

---

### 2) Create `.env`

Copy `.env.example` → `.env`

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_GENERAL_CHAT_ID=
TELEGRAM_TRAIT_CHAT_ID=

COLLECTION_SYMBOL=stones
COINGECKO_NFT_ID=stones

RECONNECT_DELAY=10
PRICE_CACHE_SECONDS=60
MIN_PRICE_BTC=0

SEEN_FILE=seen_listings.txt
TRAITS_FILTER_FILE=traits_filter.json
ME_WS_URL=wss://wss-mainnet.magiceden.io/
```

---

### 3) Configure trait filters

`traits_filter.json`

```json
{
  "Stone Type": ["Crystal"],
  "Rarity Tier": ["IV", "V"]
}
```

Listings matching these traits will be sent to the **rare alerts channel**.

---

### 4) Run

```bash
python ordinals_magiceden_monitor.py
```

---

## 📨 Alert preview

```
🆕 Stones #2451

💰 0.08500000 BTC
💵 $5,230.11
===============

💎 Floor Price: $4,980.22
♻️ 24h Vol: $812,441.55

💹 1 BTC = $61,530
```

With image preview + Buy button.

---

## 🧠 How filtering works

Trait alerts trigger if **any** condition matches:

* Stone Type = Crystal
* Rarity Tier = IV / V

Logic = OR (configurable in JSON).

---

## 🌐 Data sources

* Magic Eden WebSocket → listings
* CoinGecko API → floor & volume
* Telegram Bot API → alerts

---

## 🛠️ Notes

* `seen_listings.txt` stores processed listings
* Prevents duplicate alerts on reconnect
* Works 24/7 as a background monitor
* Supports multiple Telegram channels

---

## 📡 Use cases

* Ordinals trading alerts
* Trait sniping
* Floor monitoring
* Collection analytics
* Alpha channels

---

## ⚠️ Disclaimer

For educational & monitoring purposes only.
Not affiliated with Magic Eden.
