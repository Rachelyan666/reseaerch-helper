from research_agent.web import DuckDuckGoSearchTool, WebPageFetcher


class FakeResponse:
    def __init__(self, *, text="", url="https://example.com", status_code=200):
        self.text = text
        self.url = url
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class FakeHTTPClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, params=None, headers=None, follow_redirects=None, timeout=None):
        self.calls.append({
            "url": url,
            "params": params,
            "headers": headers,
            "follow_redirects": follow_redirects,
            "timeout": timeout,
        })
        return self.response


def test_duckduckgo_search_tool_parses_results_from_html():
    html = """
    <html><body>
      <div class='result'>
        <a class='result__a' href='https://example.com/acme'>Acme Official Site</a>
        <a class='result__snippet'>Acme builds design tools.</a>
      </div>
      <div class='result'>
        <a class='result__a' href='https://news.example.com/acme'>Acme in the news</a>
        <a class='result__snippet'>Independent coverage.</a>
      </div>
    </body></html>
    """
    tool = DuckDuckGoSearchTool(http_client=FakeHTTPClient(FakeResponse(text=html)))

    results = tool.search("Acme competitors", max_results=2)

    assert results == [
        {
            "title": "Acme Official Site",
            "url": "https://example.com/acme",
            "snippet": "Acme builds design tools.",
        },
        {
            "title": "Acme in the news",
            "url": "https://news.example.com/acme",
            "snippet": "Independent coverage.",
        },
    ]


def test_webpage_fetcher_extracts_title_and_main_text():
    html = """
    <html>
      <head><title>Acme Overview</title></head>
      <body>
        <main>
          <h1>Acme</h1>
          <p>Acme is a design collaboration company.</p>
          <p>It competes with tools for product design and whiteboarding.</p>
        </main>
      </body>
    </html>
    """
    fetcher = WebPageFetcher(http_client=FakeHTTPClient(FakeResponse(text=html, url="https://example.com/acme")))

    page = fetcher.fetch("https://example.com/acme")

    assert page["title"] == "Acme Overview"
    assert page["url"] == "https://example.com/acme"
    assert "design collaboration company" in page["content"]
    assert "whiteboarding" in page["content"]
