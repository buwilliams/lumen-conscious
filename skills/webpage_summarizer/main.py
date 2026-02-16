#!/usr/bin/env python3
"""Fetch a webpage and extract a structured summary.

Usage:
  echo '{"url": "https://example.com"}' | python main.py
  python main.py --help

Input (JSON via stdin):
  url - The URL to fetch and summarize (required)
  max_content_length - Max chars for main content excerpt (default: 2000)

Output (JSON to stdout):
  url - The fetched URL
  title - Page title
  main_content - Extracted readable text (truncated)
  key_points - List of extracted key points (headings, bold text, list items)
  word_count - Total word count of extracted text
  fetch_status - HTTP status code
  errors - List of any non-fatal issues encountered
"""

import argparse
import json
import re
import sys


def fetch_page(url, timeout=15):
    """Fetch page content, return (response, errors)."""
    import requests
    errors = []
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; NovaBot/1.0; +https://example.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp, errors
    except requests.exceptions.SSLError as e:
        errors.append(f"SSL error: {e}")
        # Retry without SSL verification as fallback
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, verify=False)
            errors.append("Fetched with SSL verification disabled")
            return resp, errors
        except Exception as e2:
            errors.append(f"Retry also failed: {e2}")
            return None, errors
    except requests.exceptions.Timeout:
        errors.append(f"Request timed out after {timeout}s")
        return None, errors
    except requests.exceptions.ConnectionError as e:
        errors.append(f"Connection error: {e}")
        return None, errors
    except requests.exceptions.HTTPError as e:
        errors.append(f"HTTP error: {e}")
        # Still return the response for status code info
        return e.response, errors
    except Exception as e:
        errors.append(f"Unexpected error: {type(e).__name__}: {e}")
        return None, errors


def extract_content(html, max_content_length=2000):
    """Extract title, main content, and key points from HTML."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Remove script, style, nav, footer, header elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
        tag.decompose()

    # Extract title
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)

    # Extract key points from headings, bold text, and list items
    key_points = []

    # Headings (h1-h3)
    for h in soup.find_all(["h1", "h2", "h3"], limit=15):
        text = h.get_text(strip=True)
        if text and len(text) > 3 and len(text) < 200:
            key_points.append(text)

    # List items from main content (first 10 meaningful ones)
    li_count = 0
    for li in soup.find_all("li", limit=30):
        text = li.get_text(strip=True)
        if text and 10 < len(text) < 300:
            key_points.append(f"• {text}")
            li_count += 1
            if li_count >= 10:
                break

    # Deduplicate while preserving order
    seen = set()
    unique_points = []
    for p in key_points:
        normalized = p.lower().strip()
        if normalized not in seen:
            seen.add(normalized)
            unique_points.append(p)
    key_points = unique_points[:15]  # Cap at 15

    # Extract main body text
    # Try to find main content area first
    main_area = (
        soup.find("main") or
        soup.find("article") or
        soup.find("div", {"role": "main"}) or
        soup.find("div", class_=re.compile(r"content|article|post|entry", re.I)) or
        soup.body or
        soup
    )

    # Get all paragraph text
    paragraphs = []
    for p in main_area.find_all(["p", "div"], recursive=True):
        text = p.get_text(separator=" ", strip=True)
        # Filter out very short or likely-navigation text
        if text and len(text) > 40:
            # Avoid duplicates from nested divs
            if not any(text in existing or existing in text for existing in paragraphs[-3:] if paragraphs):
                paragraphs.append(text)

    main_content = "\n\n".join(paragraphs)

    # If paragraphs didn't yield much, fall back to all text
    if len(main_content) < 100:
        main_content = main_area.get_text(separator="\n", strip=True)
        # Clean up excessive whitespace
        main_content = re.sub(r'\n{3,}', '\n\n', main_content)
        main_content = re.sub(r' {2,}', ' ', main_content)

    word_count = len(main_content.split())

    # Truncate main content
    if len(main_content) > max_content_length:
        # Try to break at a sentence boundary
        truncated = main_content[:max_content_length]
        last_period = truncated.rfind('. ')
        if last_period > max_content_length * 0.7:
            truncated = truncated[:last_period + 1]
        else:
            truncated = truncated.rsplit(' ', 1)[0] + "..."
        main_content = truncated

    return title, main_content, key_points, word_count


def main():
    parser = argparse.ArgumentParser(
        description="Fetch a webpage and return a structured summary."
    )
    parser.add_argument("input", nargs="?", default=None,
                        help="JSON input (also accepts stdin)")
    args = parser.parse_args()

    raw = args.input
    if raw is None:
        if not sys.stdin.isatty():
            raw = sys.stdin.read().strip()
        else:
            parser.print_help()
            sys.exit(1)

    if not raw:
        print(json.dumps({"error": "No input provided"}))
        sys.exit(1)

    try:
        params = json.loads(raw)
    except json.JSONDecodeError:
        # Treat plain text as a URL
        params = {"url": raw.strip()}

    url = params.get("url", "").strip()
    if not url:
        print(json.dumps({"error": "No URL provided. Pass {\"url\": \"https://...\"}"}))
        sys.exit(1)

    # Ensure URL has a scheme
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    max_content_length = params.get("max_content_length", 2000)

    # Fetch
    resp, errors = fetch_page(url)

    if resp is None:
        result = {
            "url": url,
            "title": None,
            "main_content": None,
            "key_points": [],
            "word_count": 0,
            "fetch_status": None,
            "errors": errors
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

    # Detect encoding
    if resp.encoding and resp.encoding.lower() != "utf-8":
        errors.append(f"Encoding detected: {resp.encoding}")

    html = resp.text

    # Check if we got meaningful HTML
    if len(html.strip()) < 50:
        errors.append("Page returned very little content (possible JS-rendered page)")

    # Extract
    try:
        title, main_content, key_points, word_count = extract_content(html, max_content_length)
    except Exception as e:
        errors.append(f"Extraction error: {type(e).__name__}: {e}")
        title, main_content, key_points, word_count = "", "", [], 0

    if word_count < 20:
        errors.append("Very low word count - page may be JS-rendered or require authentication")

    result = {
        "url": url,
        "title": title,
        "main_content": main_content,
        "key_points": key_points,
        "word_count": word_count,
        "fetch_status": resp.status_code,
        "errors": errors
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
