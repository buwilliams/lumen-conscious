#!/usr/bin/env python3
"""Research a topic and produce a structured digest.

Usage:
  echo '{"topic": "quantum computing breakthroughs 2025"}' | python main.py
  python main.py --help

Input (JSON via stdin):
  topic        - Research topic or question (required)
  max_sources  - Max pages to fetch and summarize (default: 3)
  max_results  - Max search results to consider (default: 5)

Output (JSON to stdout):
  topic, summary, sources, search_meta
"""

import argparse
import json
import os
import sys
import traceback


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def search_tavily(query, max_results=5):
    """Search using Tavily API via direct HTTP."""
    import requests
    
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not set")
    
    resp = requests.post(
        "https://api.tavily.com/search",
        json={"query": query, "max_results": max_results, "api_key": api_key},
        timeout=15
    )
    resp.raise_for_status()
    data = resp.json()
    
    results = []
    for r in data.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0),
        })
    return results


def search_duckduckgo(query, max_results=5):
    """Fallback search using DuckDuckGo HTML."""
    import requests
    from bs4 import BeautifulSoup
    
    resp = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0 (compatible; NovaBot/1.0)"},
        timeout=10
    )
    resp.raise_for_status()
    
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    
    for r in soup.select(".result")[:max_results]:
        title_el = r.select_one(".result__title a")
        snippet_el = r.select_one(".result__snippet")
        if title_el:
            url = title_el.get("href", "")
            results.append({
                "title": title_el.get_text(strip=True),
                "url": url,
                "content": snippet_el.get_text(strip=True) if snippet_el else "",
                "score": 0,
            })
    
    return results


def do_search(query, max_results=5):
    """Try Tavily first, fall back to DuckDuckGo."""
    try:
        results = search_tavily(query, max_results)
        if results:
            log(f"[research_digest] Search via Tavily: {len(results)} results")
            return results
    except Exception as e:
        log(f"[research_digest] Tavily failed ({e}), trying DuckDuckGo...")
    
    try:
        results = search_duckduckgo(query, max_results)
        log(f"[research_digest] Search via DuckDuckGo: {len(results)} results")
        return results
    except Exception as e:
        log(f"[research_digest] DuckDuckGo also failed: {e}")
        raise RuntimeError(f"All search backends failed")


def fetch_page(url, timeout=8):
    """Fetch a webpage."""
    import requests
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; NovaBot/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp.text, resp.status_code, None
    except Exception as e:
        return None, None, str(e)


def extract_content(html, max_content_length=1200):
    """Extract title, main content, and key points from HTML."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)

    key_points = []
    for h in soup.find_all(["h1", "h2", "h3"], limit=8):
        text = h.get_text(strip=True)
        if text and 3 < len(text) < 200:
            key_points.append(text)

    seen = set()
    unique_points = []
    for p in key_points:
        norm = p.lower().strip()
        if norm not in seen:
            seen.add(norm)
            unique_points.append(p)
    key_points = unique_points[:10]

    main_area = (
        soup.find("main") or soup.find("article") or
        soup.find("div", {"role": "main"}) or
        soup.body or soup
    )

    paragraphs = []
    if main_area:
        for p in main_area.find_all(["p"], recursive=True):
            text = p.get_text(separator=" ", strip=True)
            if text and len(text) > 40:
                paragraphs.append(text)
                if len("\n\n".join(paragraphs)) > max_content_length:
                    break

    main_content = "\n\n".join(paragraphs)
    if len(main_content) < 80 and main_area:
        main_content = main_area.get_text(separator=" ", strip=True)[:max_content_length]

    word_count = len(main_content.split())

    if len(main_content) > max_content_length:
        main_content = main_content[:max_content_length]
        last_period = main_content.rfind('. ')
        if last_period > max_content_length * 0.6:
            main_content = main_content[:last_period + 1]
        else:
            main_content = main_content.rsplit(' ', 1)[0] + "..."

    return title, main_content, key_points, word_count


def main():
    parser = argparse.ArgumentParser(description="Research a topic and produce a structured digest.")
    parser.add_argument("input", nargs="?", default=None, help="JSON input (also accepts stdin)")
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
        params = {"topic": raw}

    topic = params.get("topic", "").strip()
    if not topic:
        print(json.dumps({"error": "No topic provided"}))
        sys.exit(1)

    max_sources = min(params.get("max_sources", 3), 5)
    max_results = min(params.get("max_results", 5), 8)

    log(f"[research_digest] Searching for: {topic}")

    # Step 1: Search
    try:
        search_results = do_search(topic, max_results=max_results)
    except Exception as e:
        print(json.dumps({"error": f"Search failed: {e}"}))
        sys.exit(1)

    if not search_results:
        print(json.dumps({
            "topic": topic,
            "summary": "No search results found.",
            "sources": [],
            "search_meta": {"results_found": 0, "pages_fetched": 0, "total_words_analyzed": 0}
        }, indent=2))
        sys.exit(0)

    # Step 2: Fetch top N pages
    sources = []
    all_key_points = []
    total_words = 0
    successful_fetches = 0
    urls_to_fetch = [r["url"] for r in search_results[:max_sources]]

    for i, sr in enumerate(search_results):
        url = sr["url"]
        source = {
            "title": sr.get("title", ""),
            "url": url,
            "search_snippet": sr.get("content", ""),
            "content_excerpt": "",
            "key_points": [],
        }

        if url in urls_to_fetch:
            log(f"[research_digest] Fetching: {url[:80]}")
            html, status, error = fetch_page(url, timeout=8)

            if html and not error:
                try:
                    title, content, key_points, word_count = extract_content(html)
                    source["title"] = title or source["title"]
                    source["content_excerpt"] = content
                    source["key_points"] = key_points
                    all_key_points.extend(key_points[:4])
                    total_words += word_count
                    successful_fetches += 1
                    log(f"[research_digest]   -> OK ({word_count} words)")
                except Exception as e:
                    source["fetch_error"] = f"Extraction failed: {e}"
            else:
                source["fetch_error"] = error or "Empty response"

        sources.append(source)

    # Step 3: Build summary
    snippet_texts = [s.get("search_snippet", "") for s in sources if s.get("search_snippet")]
    summary_parts = []

    if snippet_texts:
        summary_parts.append("Key findings from search:")
        for i, snippet in enumerate(snippet_texts[:6], 1):
            summary_parts.append(f"  {i}. {snippet[:300]}")

    if all_key_points:
        seen = set()
        unique = []
        for p in all_key_points:
            norm = p.lower().strip()
            if norm not in seen:
                seen.add(norm)
                unique.append(p)
        if unique:
            summary_parts.append("\nKey headings from sources:")
            for p in unique[:8]:
                summary_parts.append(f"  - {p}")

    summary = "\n".join(summary_parts) if summary_parts else "No content could be extracted."

    digest = {
        "topic": topic,
        "summary": summary,
        "sources": sources,
        "search_meta": {
            "results_found": len(search_results),
            "pages_fetched": successful_fetches,
            "total_words_analyzed": total_words,
        }
    }

    print(json.dumps(digest, indent=2, ensure_ascii=False))
    sys.stdout.flush()
    log(f"[research_digest] Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"error": f"Unexpected: {e}", "tb": traceback.format_exc()}))
        sys.exit(1)
