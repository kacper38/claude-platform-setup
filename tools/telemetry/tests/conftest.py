import importlib.util
import pathlib

import pytest


@pytest.fixture(scope="session")
def ledger():
    src = pathlib.Path(__file__).resolve().parents[1] / "ledger.py"
    spec = importlib.util.spec_from_file_location("ledger", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def tdir(tmp_path, monkeypatch):
    d = tmp_path / "telemetry"
    monkeypatch.setenv("KZ_TELEMETRY_DIR", str(d))
    return d
