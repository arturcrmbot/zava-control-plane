"""Minimal ACP server test double.

Speaks just enough of the Agent Client Protocol over stdio (newline-delimited
JSON-RPC 2.0) to satisfy ComposeBridge: responds to `initialize` and
`session/new`, and on `session/prompt` replays the `update` objects from the
JSONL file named by the FAKE_ACP_TRACE env var, then returns a stop reason.

Extra argv (e.g. --acp -C <dir> --allow-all) is ignored on purpose so the
bridge can build its normal command line with this script as the binary.
"""
import json
import os
import sys


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main() -> None:
    trace_path = os.environ.get("FAKE_ACP_TRACE", "")
    updates: list[dict] = []
    if trace_path and os.path.exists(trace_path):
        with open(trace_path, encoding="utf-8") as fh:
            updates = [json.loads(ln) for ln in fh if ln.strip()]

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        mid = msg.get("id")
        method = msg.get("method")
        if method == "initialize":
            _send({"jsonrpc": "2.0", "id": mid,
                   "result": {"protocolVersion": 1, "agentCapabilities": {}}})
        elif method == "session/new":
            _send({"jsonrpc": "2.0", "id": mid,
                   "result": {"sessionId": "fake-session",
                              "models": {"availableModels": []}}})
        elif method == "session/prompt":
            if os.environ.get("FAKE_ACP_EXIT_MIDPROMPT") == "1":
                # emit one update, then exit WITHOUT sending the prompt result
                if updates:
                    _send({"jsonrpc": "2.0", "method": "session/update",
                           "params": {"sessionId": "fake-session", "update": updates[0]}})
                return
            for upd in updates:
                _send({"jsonrpc": "2.0", "method": "session/update",
                       "params": {"sessionId": "fake-session", "update": upd}})
            _send({"jsonrpc": "2.0", "id": mid, "result": {"stopReason": "end_turn"}})
        # any other method: ignore


if __name__ == "__main__":
    main()
