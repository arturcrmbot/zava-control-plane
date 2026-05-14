"""One-shot single-render check. No async, no concurrency."""
from __future__ import annotations
import os, sys, time
from pathlib import Path

# Load .env (same loader as smoke_image_gen.py)
for line in Path(".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    v = v.strip()
    if (v.startswith('"') and v.endswith('"')) or (
        v.startswith("'") and v.endswith("'")
    ):
        v = v[1:-1]
    os.environ[k] = v

os.environ.setdefault("CREATIVE_REAL_FOUNDRY", "1")
os.environ.setdefault("AZURE_OPENAI_IMAGE_TIMEOUT_S", "30")

from api.server.mcp_tools import image_gen

print(f"is_configured: {image_gen.is_configured()}", flush=True)
print(f"cs first 120: {os.environ['AZURE_STORAGE_CONNECTION_STRING'][:120]}", flush=True)
print(f"timeout: {os.environ.get('AZURE_OPENAI_IMAGE_TIMEOUT_S')}", flush=True)
print("--- single render ---", flush=True)
t0 = time.time()
result = image_gen.image_gen(
    prompt="a single glass bottle on a marble plinth, soft natural light, no text, no people",
    size="1024x1024",
    quality="low",
)
dt = time.time() - t0
print(f"wall: {dt:.1f}s", flush=True)
print(f"result_type: {result.result_type}", flush=True)
print(f"image_url: {(result.image_url or '')[:100]}", flush=True)
print(f"cached: {result.cached}, cost: {result.cost_usd}", flush=True)
print(f"error: {result.error}", flush=True)
print(f"error_code: {result.error_code}", flush=True)
