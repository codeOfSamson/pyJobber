# tests/test_base_scraper.py
import pytest
from scrapers.base import ApplyResult, BaseScraper


def test_apply_result_defaults():
    result = ApplyResult(status="applied")
    assert result.error is None
    assert result.job_updated_at is None
    assert result.employer_active_at is None
    assert result.screening_links == []


def test_apply_result_with_error():
    result = ApplyResult(status="failed", error="Timeout")
    assert result.status == "failed"
    assert result.error == "Timeout"


def test_apply_result_with_screening_links():
    result = ApplyResult(status="skipped", screening_links=["https://example.com/job/1"])
    assert len(result.screening_links) == 1
    assert result.screening_links[0] == "https://example.com/job/1"


def test_base_scraper_is_abstract():
    with pytest.raises(TypeError):
        BaseScraper()
