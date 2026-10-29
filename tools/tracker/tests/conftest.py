import importlib.util
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
TOOLS = HERE.parent


def _load(name):
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def tracker():
    return _load("tracker")


@pytest.fixture(scope="session")
def label_lint():
    return _load("label_lint")


@pytest.fixture(scope="session")
def session_start():
    return _load("session_start")
