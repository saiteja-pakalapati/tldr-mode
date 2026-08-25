"""A deliberately small, HTTP-only personal reading policy for mitmproxy."""

from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path

from mitmproxy import http


PUBLIC_HOST = "blog.example.com"
UPSTREAM_HOST = "blog"
UPSTREAM_PORT = 8000
POLICY_PATH = Path(__file__).with_name("policy.json")
NEXT_ARTICLE = {
    "/examples/keyword-heavy.html": "/examples/next.html",
}


def load_policy():
    """Read a fresh policy so saved preferences apply to the next request."""
    return json.loads(POLICY_PATH.read_text())


class PageStats(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)


def is_demo(flow):
    return flow.request.pretty_host == PUBLIC_HOST


def notice(title, explanation, next_url="/"):
    return f"""<!doctype html><html><head><meta charset='utf-8'>
    <link rel='stylesheet' href='/style.css'><title>{escape(title)}</title></head>
    <body><main class='card policy-result'><p class='eyebrow'>YOUR KEYWORDS SETTING</p>
    <h1>{escape(title)}</h1><p>{escape(explanation)}</p>
    <section class='decision'><h2>How this decision was made</h2>
    <p>The proxy read <code>keywords.enabled</code> and <code>keywords.maximum_occurrences</code> from <code>proxy/policy.json</code>. The saved limit was exceeded, so the original article was replaced by this message.</p>
    <p>Set <code>keywords.enabled</code> to <code>false</code> and reload this URL to see the original article.</p></section>
    <a class='button' href='{escape(next_url)}'>Go to the next article →</a>
    <a class='button secondary' href='/'>Return to demo guide</a>
    </main></body></html>"""


def request(flow: http.HTTPFlow):
    if not is_demo(flow):
        return

    # Always fetch the article body. A 304 response has no body for the policy
    # engine to evaluate after the reader changes the JSON file.
    flow.request.headers.pop("If-Modified-Since", None)
    flow.request.headers.pop("If-None-Match", None)
    flow.request.headers["Cache-Control"] = "no-cache"

    flow.metadata["original_path"] = flow.request.path
    flow.metadata["reading_policy"] = load_policy()

    # An author supplies both versions; the reader's switch chooses one.
    policy = flow.metadata["reading_policy"]
    full_page = policy["tldr_mode"]["full_page_name"]
    concise_page = policy["tldr_mode"]["concise_page_name"]
    if policy["tldr_mode"]["enabled"] and flow.request.path.endswith("/" + full_page):
        flow.request.path = flow.request.path[: -len(full_page)] + concise_page

    # Docker resolves this internal name. No machine-wide hosts-file edit is needed.
    flow.metadata["tldr_demo"] = True
    flow.request.host = UPSTREAM_HOST
    flow.request.port = UPSTREAM_PORT
    flow.request.scheme = "http"


def response(flow: http.HTTPFlow):
    if not flow.metadata.get("tldr_demo") or not flow.response:
        return
    # Settings can change between reloads, so demo pages must not be reused from
    # the browser cache.
    flow.response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    flow.response.headers["Pragma"] = "no-cache"
    flow.response.headers["Expires"] = "0"
    flow.response.headers.pop("ETag", None)
    flow.response.headers.pop("Last-Modified", None)
    if "text/html" not in flow.response.headers.get("content-type", ""):
        return
    # Navigation is part of the demo controls, not an article being evaluated.
    if flow.metadata.get("original_path") == "/":
        return

    parser = PageStats()
    parser.feed(flow.response.get_text(strict=False))
    reasons = []
    policy = flow.metadata["reading_policy"]
    page_text = " ".join(parser.text).lower()
    if policy["keywords"]["enabled"]:
        for phrase, limit in policy["keywords"]["maximum_occurrences"].items():
            count = page_text.count(phrase.lower())
            if count > limit:
                reasons.append(f"the phrase “{phrase}” appears {count} times and your limit is {limit}")

    if reasons:
        flow.response = http.Response.make(
            200,
            notice(
                "This article was skipped",
                "It does not match your preferences because " + "; ".join(reasons) + ".",
                NEXT_ARTICLE.get(flow.metadata.get("original_path"), "/examples/next.html"),
            ),
            {
                "Content-Type": "text/html; charset=utf-8",
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
