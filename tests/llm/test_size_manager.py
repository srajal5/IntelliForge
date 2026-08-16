"""Unit tests for RequestSizeManager size estimation, detection, and chunking."""

from src.llm.size_manager import RequestSizeManager


def test_estimate_size_and_is_oversized():
    mgr = RequestSizeManager(max_input_chars=100)
    assert mgr.estimate_size("hello") == 5
    assert mgr.is_oversized("a" * 150) is True
    assert mgr.is_oversized("a" * 50) is False


def test_reduce_prompt_truncates_at_boundary():
    mgr = RequestSizeManager(max_input_chars=100)
    prompt = "Paragraph 1\n\nParagraph 2 is very long text that goes on and on and on and on\n\nParagraph 3"

    reduced = mgr.reduce_prompt(prompt, limit=50)
    assert len(reduced) <= 50
    assert "[... Truncated due to size limit ...]" in reduced
    assert "Paragraph 1" in reduced


def test_chunk_prompt_splits_correctly():
    mgr = RequestSizeManager(max_input_chars=50)
    p1 = "First block of text."
    p2 = "Second block of text."
    p3 = "Third block of text."
    full_prompt = f"{p1}\n\n{p2}\n\n{p3}"

    chunks = mgr.chunk_prompt(full_prompt, chunk_size=30)
    assert len(chunks) >= 2
    assert all(len(c) <= 30 for c in chunks)
