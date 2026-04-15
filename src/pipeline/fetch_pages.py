"""
fetch_pages.py — fetch a single page and return raw snapshot fields.
"""

import hashlib
import logging
import re

import requests
from bs4 import BeautifulSoup

from src.config import FETCH_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)


def _extract_visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "head"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch_page(source: dict) -> dict:
    """
    Fetch one page and return a dict ready to insert into raw_snapshots.

    On network error, http_status is None and raw_text starts with "ERROR:".
    response_headers_json is always a JSON-serialisable dict (empty on failure).
    """
    url = source["url"]

    result = {
        "source_id":             source["source_id"],
        "http_status":           None,
        "final_url":             url,
        "content_type":          None,
        "content_hash":          None,
        "page_title":            None,
        "raw_text":              None,
        "response_headers_json": {},
    }

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=FETCH_TIMEOUT,
            allow_redirects=True,
        )

        result["http_status"]           = resp.status_code
        result["final_url"]             = resp.url
        result["content_type"]          = resp.headers.get("Content-Type", "")
        result["response_headers_json"] = dict(resp.headers)

        soup = BeautifulSoup(resp.text, "lxml")

        title_tag = soup.find("title")
        result["page_title"] = title_tag.get_text().strip() if title_tag else None

        visible_text           = _extract_visible_text(soup)
        result["raw_text"]     = visible_text
        result["content_hash"] = _content_hash(visible_text)

        logger.info("Fetched %s — HTTP %s", url, resp.status_code)

    except requests.exceptions.Timeout:
        logger.warning("Timeout fetching %s", url)
        result["raw_text"] = "ERROR: request timed out"

    except requests.exceptions.RequestException as exc:
        logger.warning("Request error fetching %s: %s", url, exc)
        result["raw_text"] = f"ERROR: {exc}"

    return result
