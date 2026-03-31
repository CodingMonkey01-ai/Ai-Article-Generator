import feedparser


def fetch_news_from_rss(keyword: str, max_results: int = 10):
    """
    Fetch news using Google News RSS.
    """
    query = keyword.replace(" ", "+")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    feed = feedparser.parse(url)

    news_list = []
    seen_titles = set()

    for entry in feed.entries:
        title = entry.title.strip()

        if title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())

        news_list.append({
            "title": title,
            "url": entry.link,
            "published": entry.get("published", ""),
        })

        if len(news_list) >= max_results:
            break

    print(f"RSS returned {len(news_list)} results for '{keyword}'")
    return news_list


def filter_news(news_list, keyword, top_n=5):
    """Return the most relevant RSS items for a keyword."""

    keyword = keyword.lower()

    filtered = [
        item for item in news_list
        if keyword in item["title"].lower()
    ]

    if not filtered:
        filtered = news_list

    return filtered[:top_n]


def get_news_for_keyword(keyword, num_results=10):
    """Fetch and filter RSS news items for a keyword."""

    news_list = fetch_news_from_rss(keyword, max_results=num_results)

    if not news_list:
        print(f"No news found for '{keyword}'")
        return []

    return filter_news(news_list, keyword)
