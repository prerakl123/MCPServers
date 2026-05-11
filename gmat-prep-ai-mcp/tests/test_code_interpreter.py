"""Smoke tests for the code_interpreter sandbox.

These are end-to-end - they actually spawn the sandbox subprocess. They will
be skipped if numpy/sympy/matplotlib aren't installed in the running venv.
"""
import importlib.util

import pytest

from tools import code_interpreter

_HAVE_NUMPY = importlib.util.find_spec("numpy") is not None
_HAVE_SYMPY = importlib.util.find_spec("sympy") is not None
_HAVE_MPL = importlib.util.find_spec("matplotlib") is not None

pytestmark = pytest.mark.skipif(
    not (_HAVE_NUMPY and _HAVE_SYMPY and _HAVE_MPL),
    reason="sandbox deps not installed in this venv",
)


def test_arithmetic():
    out = code_interpreter.run("print(2 + 2)")
    assert out["status"] == "ok", out
    assert "4" in out["stdout"]


def test_sympy_solve():
    code = (
        "from sympy import symbols, solve\n"
        "x = symbols('x')\n"
        "print(solve(2*x - 10, x))\n"
    )
    out = code_interpreter.run(code)
    assert out["status"] == "ok", out
    assert "5" in out["stdout"]


def test_uncaught_exception():
    out = code_interpreter.run("raise ValueError('bad')")
    assert out["status"] == "error"
    assert out["error"]["type"] == "ValueError"
    assert "bad" in out["error"]["message"]


def test_timeout():
    code = "while True: pass"
    out = code_interpreter.run(code, timeout_s=2)
    assert out["status"] == "error"
    assert out["error"]["type"] == "Timeout"


def test_matplotlib_artifact():
    code = (
        "import matplotlib.pyplot as plt\n"
        "plt.plot([1,2,3], [4,5,6])\n"
        "plt.title('demo')\n"
    )
    out = code_interpreter.run(code)
    assert out["status"] == "ok", out
    assert any(a["kind"] == "image/png" for a in out["artifacts"])
