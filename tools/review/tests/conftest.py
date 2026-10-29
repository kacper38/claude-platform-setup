import importlib.util
import pathlib

import pytest


@pytest.fixture(scope="session")
def review():
    src = pathlib.Path(__file__).resolve().parents[1] / "fresh_review.py"
    spec = importlib.util.spec_from_file_location("fresh_review", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
