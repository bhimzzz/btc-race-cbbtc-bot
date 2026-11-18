#!/usr/bin/env python3
"""cbBTC breakout rider for agent-fun/bars-replay/v1 (make.fun btc-race-24h).

Single-file Python 3.13 bot, standard library only. It speaks the NDJSON
protocol on stdin/stdout: one hello, one batch per minute bar, exactly one
reply per batch, then done. It never reads the clock, the environment or any
file, and keeps no randomness: two runs on the same bars answer identically.

Strategy (long only, all-in/all-out, at most one order per bar):
  A full round trip costs roughly 30-40 bps in fees, slippage and price
  impact, so the bot trades rarely and only on strength:
  - Entry: the close clears the highest close of the prior 180 bars by at
    least 22 bps while sitting above the 240-bar EMA (+10 bps buffer) --
    a decisive breakout in an uptrend, not a marginal poke at resistance.
  - Exit: take profit at +120 bps over the effective entry price (the
    position cost per unit, fees included), with three backstops: a
    trailing stop 80 bps under the peak close since entry, a stop loss
    140 bps under the entry, and a regime exit when the close falls back
    below the 240-bar EMA.
  - Risk controls: a 120-bar cooldown after an exit (30 bars after a take
    profit, so a running trend can be re-joined on a fresh breakout), and
    after 2 consecutive losing trades the bot sits out 720 bars.
  Position state is reconciled from the account carried by every batch, so
  a rejected order (slippage cap, warm-up, a missing bar) never corrupts it.
"""

import json
import sys

SYMBOL = "CBBTC"

# Strategy parameters (see the module docstring for the reasoning).
ENTRY_BARS = 180        # Donchian lookback for the breakout high
EMA_SPAN = 240          # trend filter / regime exit EMA
EMA_BUFFER_BPS = 10     # close must clear the EMA by this much to enter
MIN_BREAK_BPS = 22      # close must clear the breakout high by this much
TRAIL_BPS = 80          # trailing stop under the peak close since entry
STOP_BPS = 140          # stop loss under the effective entry price
TP_BPS = 120            # take profit over the effective entry price
COOLDOWN = 120          # bars to sit out after an exit
TP_COOLDOWN = 30        # shorter sit-out after a take-profit exit
LOCK_LOSSES = 2         # consecutive losers that trigger a lockout
LOCK_BARS = 720         # lockout length in bars
BUY_SLIP_BPS = 150      # max_slippage_bps sent with buys
SELL_SLIP_BPS = 300     # max_slippage_bps sent with sells
MIN_NOTIONAL = 1_000_000  # 1 USDC in quote units: the replay's buy minimum


class Strategy:
    """The breakout rider's state machine, driven by closes and the account."""

    def __init__(self):
        self._ema = None
        self._seen = 0
        self.long = False
        self.peak = 0
        self.entry_ref = 0
        self.cash_at_entry = 0
        self.last_exit_bar = -10 ** 9
        self.last_exit_reason = None
        self.exit_reason = None
        self.lock_until = -1
        self.consec_losses = 0

    def _update_ema(self, closes):
        k = 2.0 / (EMA_SPAN + 1)
        while self._seen < len(closes):
            c = closes[self._seen]
            self._ema = c if self._ema is None else self._ema + k * (c - self._ema)
            self._seen += 1

    def decide(self, closes, cash, qty, cost):
        """Orders for this bar: [] or a single order dict."""
        n = len(closes)
        c = closes[-1]
        self._update_ema(closes)
        # Reconcile the position state with the account as reported.
        if qty > 0 and not self.long:
            self.long = True
            self.peak = c
            self.entry_ref = cost * 10 ** 7 // qty if qty else c
        elif qty == 0 and self.long:
            self.long = False
            if cash - self.cash_at_entry < 0:
                self.consec_losses += 1
                if LOCK_LOSSES and self.consec_losses >= LOCK_LOSSES:
                    self.lock_until = n + LOCK_BARS
                    self.consec_losses = 0
            else:
                self.consec_losses = 0
            self.last_exit_bar = n
            self.last_exit_reason = self.exit_reason
            self.exit_reason = None
            self.peak = 0
        if self.long:
            if c > self.peak:
                self.peak = c
            if self.peak and c * 10000 < self.peak * (10000 - TRAIL_BPS):
                self.exit_reason = "trail"
                return [{"side": "sell", "qty": qty, "slip": SELL_SLIP_BPS}]
            if self.entry_ref and c * 10000 < self.entry_ref * (10000 - STOP_BPS):
                self.exit_reason = "stop"
                return [{"side": "sell", "qty": qty, "slip": SELL_SLIP_BPS}]
            if self.entry_ref and c * 10000 >= self.entry_ref * (10000 + TP_BPS):
                self.exit_reason = "tp"
                return [{"side": "sell", "qty": qty, "slip": SELL_SLIP_BPS}]
            if self._ema is not None and n > EMA_SPAN and c < self._ema:
                self.exit_reason = "ema"
                return [{"side": "sell", "qty": qty, "slip": SELL_SLIP_BPS}]
            return []
        # Flat: look for a decisive breakout in an uptrend.
        if n <= max(ENTRY_BARS, EMA_SPAN):
            return []
        cooldown = TP_COOLDOWN if self.last_exit_reason == "tp" else COOLDOWN
        if n < self.lock_until or n - self.last_exit_bar < cooldown:
            return []
        if self._ema is None or c * 10000 <= self._ema * (10000 + EMA_BUFFER_BPS):
            return []
        hi = max(closes[-ENTRY_BARS - 1:-1])
        if c * 10000 >= hi * (10000 + MIN_BREAK_BPS):
            if cash >= MIN_NOTIONAL:
                self.cash_at_entry = cash
                return [{"side": "buy", "notional": cash, "slip": BUY_SLIP_BPS}]
        return []


def main():
    strat = Strategy()
    closes = []
    next_id = 1
    out = sys.stdout
    for raw in sys.stdin.buffer:
        line = raw.strip()
        if not line:
            continue
        msg = json.loads(line)
        kind = msg.get("type")
        if kind == "batch":
            account = msg["account"]
            cash = int(account["cash_quote_units"])
            qty = 0
            cost = 0
            for p in account["positions"]:
                if p["symbol"] == SYMBOL:
                    qty = int(p["qty"])
                    cost = int(p["cost_quote_units"])
            new_bar = False
            for bar in msg["bars"]:
                if bar["symbol"] == SYMBOL:
                    closes.append(int(bar["c"]))
                    new_bar = True
            orders = strat.decide(closes, cash, qty, cost) if new_bar and closes else []
            wire = []
            for o in orders:
                cid = "o%d" % next_id
                next_id += 1
                if o["side"] == "buy":
                    wire.append({
                        "side": "buy", "client_id": cid, "symbol": SYMBOL,
                        "notional_quote_units": str(o["notional"]),
                        "max_slippage_bps": o["slip"],
                    })
                else:
                    wire.append({
                        "side": "sell", "client_id": cid, "symbol": SYMBOL,
                        "qty": str(o["qty"]),
                        "max_slippage_bps": o["slip"],
                    })
            out.write(json.dumps(
                {"type": "reply", "seq": msg["seq"], "orders": wire},
                separators=(",", ":"), ensure_ascii=False) + "\n")
            out.flush()
        elif kind == "done":
            return
        # hello needs no answer; anything else is ignored.


if __name__ == "__main__":
    main()
