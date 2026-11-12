#!/usr/bin/env python3
"""Records a mainnet transaction once, for the Real transactions page (traces.html).

Usage: python3 tools/capture_trace.py <tx hash> <out.json> [rpc url]

Saves the transaction, its receipt, the block's fee recipient, the call tree with each
call's events (callTracer, withLog), the balance and storage changes (prestateTracer,
diffMode) and the symbol/decimals of every token that emitted an event. Needs an RPC
endpoint that serves debug_traceTransaction for the block (dRPC's free one does).
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


def main():
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
        "source": RPC,
        "captured": time.strftime("%Y-%m-%d"),
    }, open(out, "w"), separators=(",", ":"))
    print(out, "bytes", len(open(out).read()))


main()
