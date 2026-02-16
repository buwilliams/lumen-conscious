#!/usr/bin/env python3
"""Web search skill with pluggable backends.

Usage:
  echo '{"query": "AI news", "max_results": 5}' | python main.py
  echo '{"query": "climate change", "backend": "tavily"}' | python main.py
  python main.py --help

Input (JSON via stdin):
  query        - Search query string (required)
  backend      - Search backend to use (default: tavily)
  max_results  - Maximum number of results (default: 5)

Plain text input is also accepted as the query string.

Output (JSON to stdout):
  query    - The original query
  results  - Array of {title, url, content}

Environment:
  TAVILY_API_KEY - Required for the tavily backend
"""

import argparse
import json
import os
import sys


def _search_tavily(query: str, max_results: int = 5) -> list[dict]:
    """Search using the Tavily API."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY environment variable not set")

    from tavily import TavilyClient

    client = TavilyClient(api_key=api_key)
    response = client.search(query=query, max_results=max_results)

    results = []
    for r in response.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
        })
    return results


BACKENDS = {
    "tavily": _search_tavily,
}


def main():
    parser = argparse.ArgumentParser(
        description="Web search skill with pluggable backends.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", nargs="?", default=None,
                        help="JSON input or plain text query (also accepts stdin)")
    args = parser.parse_args()

    # Read input from arg or stdin
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

    # Parse input — JSON or plain text
    try:
        params = json.loads(raw)
    except json.JSONDecodeError:
        params = {"query": raw}

    query = params.get("query", "")
    backend = params.get("backend", "tavily")
    max_results = params.get("max_results", 5)

    if not query:
        print(json.dumps({"error": "No query provided"}))
        sys.exit(1)

    search_fn = BACKENDS.get(backend)
    if not search_fn:
        print(json.dumps({"error": f"Unknown backend '{backend}'. Available: {list(BACKENDS.keys())}"}))
        sys.exit(1)

    try:
        results = search_fn(query, max_results=max_results)
        print(json.dumps({"query": query, "results": results}, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
