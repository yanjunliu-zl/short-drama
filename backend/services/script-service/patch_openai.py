"""Patch openai and langsmith SDKs to accept langchain's httpx wrapper class"""
import inspect, os, pathlib

# Patch 1: openai
import openai._base_client as obc
f1 = inspect.getfile(obc)
with open(f1) as fh:
    c1 = fh.read()
old = 'not isinstance(http_client, httpx.Client)'
new = 'not (isinstance(http_client, httpx.Client) or getattr(http_client,"__name__","")=="_SyncHttpxClientWrapper")'
if old in c1 and '_SyncHttpxClientWrapper' not in c1:
    c1 = c1.replace(old, new)
    with open(f1, 'w') as fh:
        fh.write(c1)
    # Delete .pyc cache to force recompilation
    pyc = pathlib.Path(f1).parent / '__pycache__' / (pathlib.Path(f1).stem + '.cpython-310.pyc')
    if pyc.exists():
        pyc.unlink()
    print(f'Patched {f1}')

# Patch 2: langsmith (if installed)
try:
    import langsmith._openapi_client._base_client as lbc
    f2 = inspect.getfile(lbc)
    with open(f2) as fh:
        c2 = fh.read()
    if old in c2 and '_SyncHttpxClientWrapper' not in c2:
        c2 = c2.replace(old, new)
        with open(f2, 'w') as fh:
            fh.write(c2)
        pyc2 = pathlib.Path(f2).parent / '__pycache__' / (pathlib.Path(f2).stem + '.cpython-310.pyc')
        if pyc2.exists():
            pyc2.unlink()
        print(f'Patched {f2}')
except ImportError:
    pass
