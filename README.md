# AMM Visualiser

An interactive, browser-based view of real Uniswap pools for **COMP1830 Blockchain for Fintech**
(University of Greenwich), Lab 5.

**Live:** https://apogiatzis.github.io/comp1830-amm-visualiser/

Students paste the RPC URL of their SandboxLab mainnet fork. The page plays **real transactions** against
three real pools on that fork, signed by the sandbox's unlocked test accounts, and draws what they do:
the reserves, the x·y=k bonding curve with each trade on it, the price after every trade, a trade tape
(spot price, price paid, difference) and the mempool / block order.

| Pool | Address | Role |
|---|---|---|
| ETH / USDC · Uniswap v2 | `0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc` | textbook x·y=k, ≈ $20m |
| ETH / USDC · Uniswap v3 0.05% | `0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640` | deep pool; curve uses virtual reserves |
| AAVE / ETH · Uniswap v2 | `0xDFC14d2Af169B0D36C4EFF567Ada9b2E0CAE044f` | thin pool, ≈ $130k |

## Sequences

Link straight to one with `?sequence=<name>`:

| Sequence | What it shows |
|---|---|
| `single` | Bob sells 100 ETH on v2: predict, then check |
| `retail` | 24 seeded random trades; price drift and fee growth of k |
| `whale` | Judy spends 10 ETH in each pool: depth and price impact |
| `protect` | Judy's 60 ETH lands before Bob's 50 ETH: 0.5% minimum reverts, 5% fills |
| `sandwich` | Carol front-runs and back-runs Bob's 200 ETH swap in one block (hidden; shown with `?mev=1`) |
| `arbitrage` | Judy dumps 150 ETH on v2; Carol arbitrages v2 against v3 |

*Your trade* lets a student swap as any trader. With `?mev=1` it also offers Carol's front-running bot (the sandwich demo is not used in the 2026-27 worksheet).

Both charts are interactive: mouse wheel zooms around the cursor (Shift: horizontal axis only), drag pans
(mouse or touch), double-click or ⟲ resets, + / − zoom about the centre. Hovering shows a crosshair readout:
on the curve, x, y and the price at that point; on the price chart, the nearest trade point, its price, trader
and block. A zoomed view is kept as new trades arrive (⟲ turns amber); switching pool resets it.

## How it works

- On **Connect** the page funds traders 1–9 with USDC and AAVE and sets router allowances by writing token
  storage (`anvil_setStorageAt`, like SandboxLab's *Fund wallet*), then takes `evm_snapshot`: the start point.
  **Rewind** and each sequence (by default) `evm_revert` to it.
- To put several transactions in one block it calls `evm_setAutomine(false)`, sends them with explicit
  nonces and priority fees, `anvil_mine`s one block and restores auto-mine. Results are read from the
  pools' `Swap`/`Sync` events in block order.
- Quotes: Uniswap v2's integer formula locally; v3 through QuoterV2 (`0x61fF…B21e`). Swaps: v2 Router02,
  v3 SwapRouter02.
- The worksheet's numbers assume a fork at block **26,344,800**; the page warns if the fork block differs.

Single static page: `index.html` plus the University of Greenwich brand fonts (Cooper Hewitt and Public
Sans, SIL Open Font Licence). [viem](https://viem.sh) 2.57.16 is loaded from jsDelivr.
