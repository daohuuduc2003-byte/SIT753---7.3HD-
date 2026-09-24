"""Unit tests for helper functions in server.py"""
from server import clean


def test_clean_escapes_html():
    assert clean("<b>hi</b>") == "&lt;b&gt;hi&lt;/b&gt;"


def test_clean_trims_whitespace():
    assert clean("   river   ") == "river"


def test_clean_truncates_to_maxlen():
    assert clean("a" * 50, maxlen=10) == "a" * 10


def test_clean_handles_none_and_numbers():
    assert clean(None) == ""
    assert clean(123) == "123"
