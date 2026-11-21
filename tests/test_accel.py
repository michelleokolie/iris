import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hw"))

from accel import COUNTS_PER_G, parse_line, to_g
from ir_read import parse


def test_zero_and_positive():
    assert to_g(0) == 0
    assert to_g(21) == pytest.approx(21 / COUNTS_PER_G)   # ~0.98 g
    assert to_g(31) == pytest.approx(31 / COUNTS_PER_G)   # +full scale ~1.45 g


def test_sign_extension():
    assert to_g(0x3F) == pytest.approx(-1 / COUNTS_PER_G)
    assert to_g(0x20) == pytest.approx(-32 / COUNTS_PER_G)   # -full scale ~-1.5 g
    assert to_g(43) == pytest.approx(-21 / COUNTS_PER_G)


def test_invalid_bit_rejected():
    with pytest.raises(ValueError, match="invalid sample"):
        to_g(0x40 | 5)


def test_parse_line_flat_on_back():
    x, y, z = parse_line("0 1 21\n")
    assert (x, y) == (0, pytest.approx(1 / COUNTS_PER_G))
    assert z == pytest.approx(0.985, abs=0.01)


def test_parse_line_requires_three_axes():
    with pytest.raises(ValueError, match="three-axis"):
        parse_line("")


def test_ir_parse():
    assert parse(b"1\n") is True
    assert parse(b"0") is False
    with pytest.raises(KeyError):
        parse(b"high")
