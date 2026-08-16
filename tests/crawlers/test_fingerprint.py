"""Tests for URL fingerprinting."""

from src.crawlers.fingerprint import normalize_url, url_fingerprint


# ------------------------------------------------------------------
# normalize_url
# ------------------------------------------------------------------


def test_normalize_lowercases_scheme():
    assert normalize_url("HTTP://EXAMPLE.COM/page") == "http://example.com/page"


def test_normalize_lowercases_host():
    assert normalize_url("https://Example.COM/page") == "https://example.com/page"


def test_normalize_strips_trailing_slash():
    assert normalize_url("https://example.com/page/") == "https://example.com/page"


def test_normalize_preserves_root():
    assert normalize_url("https://example.com") == "https://example.com/"


def test_normalize_sorts_query_params():
    url = "https://example.com/search?z=1&a=2"
    assert "a=2" in normalize_url(url)
    assert normalize_url(url).index("a=2") < normalize_url(url).index("z=1")


def test_normalize_drops_fragment():
    assert "#" not in normalize_url("https://example.com/page#section")


# ------------------------------------------------------------------
# url_fingerprint
# ------------------------------------------------------------------


def test_fingerprint_deterministic():
    url = "https://example.com/page?a=1&b=2"
    assert url_fingerprint(url) == url_fingerprint(url)


def test_fingerprint_same_after_normalization():
    """Same logical URL with different casing → same fingerprint."""
    fp1 = url_fingerprint("HTTPS://EXAMPLE.COM/page")
    fp2 = url_fingerprint("https://example.com/page")
    assert fp1 == fp2


def test_fingerprint_same_with_query_reorder():
    fp1 = url_fingerprint("https://example.com?a=1&b=2")
    fp2 = url_fingerprint("https://example.com?b=2&a=1")
    assert fp1 == fp2


def test_fingerprint_different_urls():
    fp1 = url_fingerprint("https://example.com/a")
    fp2 = url_fingerprint("https://example.com/b")
    assert fp1 != fp2


def test_fingerprint_is_sha256_hex():
    fp = url_fingerprint("https://example.com")
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)
