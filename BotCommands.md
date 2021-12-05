# Available Commands

## /help

Displays PDF document with available commands

## /price _SYMBOL_

Displays CoinGecko/CoinMarketCap statistics for the given cryptocurrency symbol.

```shell
/price btc
```

## /price_address _ADDRESS_ _PLATFORM_

Displays price data for given contract address.

Supported platforms

* eth
* bsc
* matic

```shell
/price 0x0000000000000 eth
```

## /gas

Displays ethereum gas fees

## /trending

Displays trending tokens on CoinGecko and CoinMarketCap

## /alert _SYMBOL_ < OR > _TARGET_PRICE_

Alerts user when specified token reaches overcomes target price

```shell
/alert btc > 60000
```

## /latest_listings

Displays latest token listings on COinGecko and CoinMarketCap <br><br>

## /register _NETWORK_ _PARAMETERS_

Registers user wallet/exchange account to use with other commands for quick trade execution or viewing account balance.

```shell
/register bsc ADDRESS PRIVATE_KEY
/register eth ADDRESS PRIVATE_KEY
/register matic ADDRESS PRIVATE_KEY
/register coinbase API_KEY API_SECRET API_PASSPHRASE
/register kucoin API_KEY API_SECRET API_PASSPHRASE
```

## /buy _NETWORK_ _ADDRESS_ _AMOUNT_

Purchases token from decentralized exchange

Networks

* bsc - AMOUNT in BNB
* eth - AMOUNT in ETH
* matic -AMOUNT in MATIC

```shell
/buy bsc 0x68fbd4d89ba15343e7d2457189459b7ac80a20a3 0.5
```

## /sell _NETWORK_ _ADDRESS_

Sells all tokens for given address in a decentralized exchange

Networks

* bsc
* eth
* matic

```shell
/sell bsc 0x68fbd4d89ba15343e7d2457189459b7ac80a20a3
```

## /chart _SYMBOL_ _NUM_DAYS_

Displays chart of given token symbol for a period of time.

```shell
/chart btc 365
```

<br><br>

## /candle _SYMBOL-BASE_ _NUM_TIME_ _TIME_UNIT_

Displays candle stick chart of given token symbol pair for a period of time.

Time Units

* d - Day
* h - Hour
* m - Minute

```shell
/candle btc-usd 365 d
/candle btc-usd 7 h
/candle btc-usd 30 m
```

## /balance _NETWORK_

Replies privately with the balance of your current holdings for the given network

Networks

* bsc
* eth
* matic
* coinbase

```shell
/balance eth
```

## /spy _NETWORK_ _ADDRESS_

Displays 5 recent holdings for given address

Networks

* bsc
* eth
* matic

```shell
/spy eth 0x000000000000
```

<br><br><br><br><br><br>

## /snipe _ADDRESS_ _BNB_AMOUNT_

Utilizes high gas to purchase token as fast as possible. Will wait until liquidity is present before purchasing token

```shell
/snipe 0x68fbd4d89ba15343e7d2457189459b7ac80a20a3 0.5
```

## /limit _ACTION_ _ADDRESS_ _TARGET_PRICE_ _BNB_AMOUNT_

Creates a limit order to trade on the binance smart chain

**BNB_AMOUNT** only required for limit buy

ACTIONS

* buy
* sell
* stop

```shell
/limit sell 0x68fbd4d89ba15343e7d2457189459b7ac80a20a3 5
```

## /active_orders

Displays active limit orders

## /cancel_order _ORDER_ID_

Cancels limit order

```shell
/cancel_order 30
```

<br><br><br><br><br><br><br><br><br><br><br><br>

## /coinbase _ORDER_TYPE_ _ACTION_ _SYMBOL_ _USD_AMOUNT_ _USD_LIMIT_PRICE_

Creates a coinbase trade order

Order types

* limit
* market

Actions

* buy
* sell
* stop - Only applies for limit orders

**USD_LIMIT_PRICE only used on Limit orders**

```shell
/coinbase limit buy eth 100 3500
/coinbase market buy eth 100
```

## /submit _TOKEN_NAME_ _SYMBOL_

Submits given token name and symbol to monthly crypto drawing (AKA Token of the month)

```shell
/submit Shiba Inu SHIB
```

# Admin Commands

## /restart_kucoin

Restarts kucoin bot. This bot displays futures trades in real time (Currently disabled)

## /monthly_drawing

Replies with a poll containing a maximum of 10 token names and symbols to vote for. 