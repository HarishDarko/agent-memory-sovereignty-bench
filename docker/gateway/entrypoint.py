"""Container entrypoint: run the policy-gated gateway proxy.

Environment: DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, GATEWAY_POLICY_PATH,
GATEWAY_LEDGER_PATH, GATEWAY_PORT.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.gateway.ledger import Ledger  # noqa: E402
from benchmark.gateway.policy import GatewayPolicy  # noqa: E402
from benchmark.gateway.server import create_server  # noqa: E402


def main() -> int:
    policy_path = Path(os.environ.get("GATEWAY_POLICY_PATH", "/app/config/gateway-policy.toml"))
    ledger_path = Path(os.environ.get("GATEWAY_LEDGER_PATH", "/tmp/gateway-ledger.jsonl"))
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    port = int(os.environ.get("GATEWAY_PORT", "8000"))
    policy = GatewayPolicy.load(policy_path) if policy_path.exists() else GatewayPolicy()
    server = create_server(
        policy=policy,
        ledger=Ledger(ledger_path),
        upstream_url=base_url + "/chat/completions",
        api_key=api_key,
        port=port,
    )
    print(f"gateway listening on 127.0.0.1:{server.server_port} -> {server.upstream_url}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
