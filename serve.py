import subprocess
import sys
import os
import asyncio
from pathlib import Path

from hypercorn.config import Config
from hypercorn.asyncio import serve
from app.main import app

CERT_PATH = Path("/tmp/patchwatch-cert.pem")
KEY_PATH  = Path("/tmp/patchwatch-key.pem")


def generate_self_signed_cert():
    if CERT_PATH.exists() and KEY_PATH.exists():
        print("[patchwatch] SSL certs already exist, reusing.")
        return

    print("[patchwatch] Generating self-signed SSL certificate in /tmp ...")
    result = subprocess.run(
        [
            "openssl", "req", "-x509",
            "-newkey", "rsa:2048",
            "-keyout", str(KEY_PATH),
            "-out",    str(CERT_PATH),
            "-days",   "825",
            "-nodes",
            "-subj",   "/CN=patchwatch/O=PatchWatch/C=US",
            "-addext", "subjectAltName=IP:0.0.0.0,IP:127.0.0.1,DNS:localhost"
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("[patchwatch] openssl failed:", result.stderr, file=sys.stderr)
        sys.exit(1)

    KEY_PATH.chmod(0o600)
    print(f"[patchwatch] Cert → {CERT_PATH}")
    print(f"[patchwatch] Key  → {KEY_PATH}")


def build_hypercorn_config() -> Config:
    config = Config()
    config.bind     = ["0.0.0.0:443"]
    config.certfile = str(CERT_PATH)
    config.keyfile  = str(KEY_PATH)
    config.workers  = int(os.environ.get("WORKERS", "1"))
    config.accesslog = "-"
    config.errorlog  = "-"
    config.loglevel  = "info"
    return config


if __name__ == "__main__":
    generate_self_signed_cert()
    config = build_hypercorn_config()
    print("[patchwatch] Starting Hypercorn on https://0.0.0.0:443")
    asyncio.run(serve(app, config))