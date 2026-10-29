import importlib.util
import pathlib

import pytest


@pytest.fixture(scope="session")
def egress():
    src = pathlib.Path(__file__).resolve().parents[1] / "egress_screen.py"
    spec = importlib.util.spec_from_file_location("egress_screen", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
