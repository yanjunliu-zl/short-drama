"""Startup patch: fix langchain_openai + openai SDK compatibility."""
import os
import pathlib


def apply_patch():
    old = 'not isinstance(http_client, httpx.Client)'
    new = 'not (isinstance(http_client, httpx.Client) or getattr(http_client,"__name__","")=="_SyncHttpxClientWrapper")'

    for pkg_path in [
        '/home/appuser/.local/lib/python3.10/site-packages/openai/_base_client.py',
        '/home/appuser/.local/lib/python3.10/site-packages/langsmith/_openapi_client/_base_client.py',
    ]:
        try:
            with open(pkg_path) as fh:
                c = fh.read()
            if old in c:
                c = c.replace(old, new)
                with open(pkg_path, 'w') as fh:
                    fh.write(c)
                # Delete all .pyc cache files
                pycache_dir = pathlib.Path(pkg_path).parent / '__pycache__'
                if pycache_dir.exists():
                    for pyc in pycache_dir.glob('_base_client*.pyc'):
                        pyc.unlink()
                print(f"[startup-patch] Patched {pkg_path}", flush=True)
        except Exception as e:
            print(f"[startup-patch] Could not patch {pkg_path}: {e}")
