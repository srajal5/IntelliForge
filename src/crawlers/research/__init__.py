"""Research paper crawling and adapter module."""

from src.crawlers.research.adapter import ResearchAdapter
from src.crawlers.research.github import GitHubDiscoverer, GitHubMetadataFetcher
from src.crawlers.research.models import RawPaper
from src.crawlers.research.parser import ArxivParser

__all__ = [
    "ResearchAdapter",
    "ArxivParser",
    "RawPaper",
    "GitHubDiscoverer",
    "GitHubMetadataFetcher",
]
