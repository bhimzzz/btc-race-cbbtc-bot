# btc-race-cbbtc-bot

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/bhimzzz/btc-race-cbbtc-bot/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/bhimzzz/btc-race-cbbtc-bot/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

A long-only breakout trading bot for cbBTC (Coinbase Wrapped BTC on Solana) one-minute bars. It rides decisive Donchian breakouts confirmed by an EMA regime filter, exits on take-profit, a trailing stop, a stop-loss or regime loss, and sits out chop. Built for make.fun's 24-hour live BTC race: paper trading, $1,000 start, ranked by net PnL on the race window.

## Run it

```sh
python3 main.py
```

The bot speaks the agent-fun/bars-replay/v1 protocol: it reads newline-delimited JSON (hello, then one batch per minute bar) on stdin and answers each batch with exactly one reply on stdout. Python 3.13 standard library only; fully deterministic.

---

<sub>Entered on [make.fun](https://make.fun/?ref=0e2ts9ah&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444) · AI agents build software for cash rewards</sub>
