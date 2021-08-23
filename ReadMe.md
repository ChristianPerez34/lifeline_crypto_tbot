[![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai) ![GitHub issues](https://img.shields.io/github/issues-raw/ChristianPerez34/lifeline_crypto_tbot) ![GitHub pull requests](https://img.shields.io/github/issues-pr-raw/ChristianPerez34/lifeline_crypto_tbot) ![Code Style](https://img.shields.io/badge/Code%20Style-Black-black)

The all-in-one stop for your crypto needs.

Telegram bot that displays cryptocurrency prices, charts, and much more.

## Features

* Check token prices on CoinMarketCap & CoinGecko
* Execute swaps on PancakeSwap, UniSwap & QuickSwap (Note: Mostly tested with PancakeSwap)
* Generate line & candle charts
* Alert users when tokens move above/below target price
* View ETH gas fees (Soon to add BSC & Polygon Gas fees)
* Limit orders (Still testing!)
* View trending tokens on CoinGecko & CoinMarketCap
* View the latest token listings on CoinGecko & CoinMarketCap
* View balance of your wallet address
* View recent transactions of other wallet addresses

## Getting Started

The intention of this telegram bot is to facilitate token lookups, swaps, & charts without having to go through multiple
websites.

### Installation

This projecft utilizes [Poetry](https://python-poetry.org/) as its dependency manager

```shell
# Install required python dependencies
poetry install
```

### Environment Variables

Telegram bot expects various environment variables to be set to run.

```shell
# Database config for storing user info, crypto alerts, limit orders, etc...
DB_NAME
DB_HOST
DB_USER
DB_PASSWORD

# Fernet key for Symmetric Encryption
FERNET_KEY

# Telegram bot key from @TheBotFather
TELEGRAM_BOT_API_KEY

# ID of telegram chat|channel|group
TELEGRAM_CHAT_ID

# CoinMarketCap API KEY
COIN_MARKET_CAP_API_KEY

# Crypto Explorer Keys
BSCSCAN_API_KEY
ETHERSCAN_API_KEY
POLYGONSCAN_API_KEY

# Connect to Ethereum MainNet
ETHEREUM_MAIN_NET_URL

# Kucoin API keys for kucoin bot (Optional)
KUCOIN_API_KEY
KUCOIN_API_SECRET
KUCOIN_API_PASSPHRASE

```

### Running The Bot

```shell
# Ensure current working directory is project root
poetry run python app/lifeline_crypto_tbot.py
```


