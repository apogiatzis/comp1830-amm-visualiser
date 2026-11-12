#!/usr/bin/env python3
"""Records a mainnet transaction once, for the Real transactions page (traces.html).

Usage: python3 tools/capture_trace.py <tx hash> <out.json> [rpc url]
       python3 tools/capture_trace.py --update <file.json>   (recompute tokenBalances only)

Saves the transaction, its receipt, the block's fee recipient, the call tree with each
call's events (callTracer, withLog), the balance and storage changes (prestateTracer,
diffMode), the symbol/decimals of every token that emitted an event, and each token's
balance before and after for every account whose balance changed (tokenBalances, read
from the storage changes). Needs an RPC endpoint that serves debug_traceTransaction for
the block (dRPC's free one does), and pycryptodome for keccak (pip install pycryptodome).
"""
import json
import sys
import time
import urllib.request

RPC = sys.argv[3] if len(sys.argv) > 3 else "https://eth.drpc.org"


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for attempt in range(6):
        try:
            req = urllib.request.Request(RPC, body, {"content-type": "application/json", "user-agent": "comp1830-capture"})
            reply = json.load(urllib.request.urlopen(req, timeout=120))
            if "error" in reply:
                raise RuntimeError(f"{method}: {reply['error']}")
            return reply["result"]
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 5:
                raise
            time.sleep(2 ** attempt)


def text(raw):
    """An ABI-encoded string, or a bytes32 one (old tokens such as MKR)."""
    data = bytes.fromhex(raw[2:])
    if len(data) >= 64:
        length = int.from_bytes(data[32:64], "big")
        return data[64:64 + length].decode("utf-8", "replace")
    return data.rstrip(b"\0").decode("utf-8", "replace")


def token(address, block):
    try:
        symbol = text(rpc("eth_call", [{"to": address, "data": "0x95d89b41"}, block]))
        decimals = int(rpc("eth_call", [{"to": address, "data": "0x313ce567"}, block]), 16)
        return {"symbol": symbol, "decimals": decimals}
    except Exception:
        return None


def logs_of(frame, out):
    out.extend(frame.get("logs", []))
    for child in frame.get("calls", []):
        logs_of(child, out)
    return out


def keccak(data):
    from Crypto.Hash import keccak as k
    return k.new(digest_bits=256, data=data).hexdigest()


TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
LOW_255 = (1 << 255) - 1  # USDC keeps a blacklist flag in the top bit of the balance slot


def token_balances(calls, diff, tokens):
    """Before/after token balances, read from the storage slots the transaction changed.

    For each token, the accounts in its Transfer events are matched to changed slots of
    a balance mapping: keccak(account . slot) for Solidity, keccak(slot . account) for
    Vyper, trying mapping slots 0-50. Only exact storage values are used; accounts whose
    slot can't be found are left out.
    """
    pre, post = diff.get("pre", {}), diff.get("post", {})
    accounts = {}
    for log in logs_of(calls, []):
        topics = log.get("topics", [])
        if len(topics) == 3 and topics[0] == TRANSFER and log["address"].lower() in tokens:
            seen = accounts.setdefault(log["address"].lower(), [])
            for t in topics[1:]:
                a = "0x" + t[-40:].lower()
                if a not in seen:
                    seen.append(a)
    rows = []
    for tok, accts in accounts.items():
        before = {k.lower(): v for k, v in pre.get(tok, {}).get("storage", {}).items()}
        after = {k.lower(): v for k, v in post.get(tok, {}).get("storage", {}).items()}
        changed = set(before) | set(after)
        for a in accts:
            key = bytes.fromhex(a[2:]).rjust(32, b"\0")
            for slot in range(51):
                s = slot.to_bytes(32, "big")
                hit = next((h for h in ("0x" + keccak(key + s), "0x" + keccak(s + key)) if h in changed), None)
                if hit:
                    b = int(before.get(hit, "0x0"), 16) & LOW_255
                    c = int(after.get(hit, "0x0"), 16) & LOW_255
                    if b != c:
                        rows.append({"token": tok, "account": a, "before": hex(b), "after": hex(c)})
                    break
    return rows


def main():
    if sys.argv[1] == "--update":
        path = sys.argv[2]
        d = json.load(open(path))
        d["tokenBalances"] = token_balances(d["calls"], d["stateDiff"], d["tokens"])
        json.dump(d, open(path, "w"), separators=(",", ":"))
        print(path, len(d["tokenBalances"]), "token balance changes")
        return
    tx_hash, out = sys.argv[1], sys.argv[2]
    tx = rpc("eth_getTransactionByHash", [tx_hash])
    receipt = rpc("eth_getTransactionReceipt", [tx_hash])
    block = rpc("eth_getBlockByNumber", [tx["blockNumber"], False])
    calls = rpc("debug_traceTransaction", [tx_hash, {"tracer": "callTracer", "tracerConfig": {"withLog": True}}])
    diff = rpc("debug_traceTransaction", [tx_hash, {"tracer": "prestateTracer", "tracerConfig": {"diffMode": True}}])
    tokens = {}
    for log in logs_of(calls, []):
        address = log["address"].lower()
        if address not in tokens:
            tokens[address] = token(address, tx["blockNumber"])
    json.dump({
        "hash": tx_hash,
        "tx": {k: tx.get(k) for k in ("from", "to", "value", "input", "gas", "gasPrice", "maxFeePerGas", "maxPriorityFeePerGas", "nonce", "transactionIndex", "blockNumber")},
        "receipt": {k: receipt.get(k) for k in ("status", "gasUsed", "effectiveGasPrice", "logs")},
        "block": {k: block.get(k) for k in ("number", "timestamp", "miner", "baseFeePerGas", "hash")},
        "calls": calls,
        "stateDiff": diff,
        "tokens": {a: t for a, t in tokens.items() if t},
        "tokenBalances": token_balances(calls, diff, {a for a, t in tokens.items() if t}),
        "source": RPC,
        "captured": time.strftime("%Y-%m-%d"),
    }, open(out, "w"), separators=(",", ":"))
    print(out, "bytes", len(open(out).read()))


main()
