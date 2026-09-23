"""Collect dated RSS/Atom headlines; Python standard library only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import json
from pathlib import Path
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

CST = timezone(timedelta(hours=8))
BASE = Path(__file__).resolve().parent


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", value or ""))).strip()


def parse_date(value):
    try:
        result = parsedate_to_datetime(value)
    except (ValueError, TypeError, IndexError):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
    return result if result.tzinfo else result.replace(tzinfo=timezone.utc)


def parse_feed(data, now):
    root = ET.fromstring(data)
    # Normalize RSS/Atom namespaces without depending on a particular prefix.
    for element in root.iter():
        element.tag = element.tag.rsplit("}", 1)[-1]
    entries = root.findall(".//item") or root.findall(".//entry")
    articles = []
    for item in entries:
        title = clean(item.findtext("title"))
        published = parse_date(item.findtext("pubDate") or item.findtext("published")
                               or item.findtext("updated") or item.findtext("date"))
        if not title or not published or not now - timedelta(hours=24) <= published <= now + timedelta(minutes=5):
            continue
        link = item.findtext("link") or ""
        if not link.strip():
            link = next((x.get("href", "") for x in item.findall("link")
                         if x.get("rel", "alternate") == "alternate"), "")
        if not link.startswith(("https://", "http://")):
            link = ""
        articles.append({"title": title, "url": link, "published": published.isoformat()})
    return sorted(articles, key=lambda x: x["published"], reverse=True)


def fetch_feed(feed, now):
    for attempt in range(3):
        try:
            req = urllib.request.Request(feed["url"], headers={"User-Agent": "MorningBrief/1.0 RSS reader"})
            with urllib.request.urlopen(req, timeout=25) as response:
                data = response.read(5_000_001)
            if len(data) > 5_000_000:
                raise ValueError("Feed too large")
            return feed, parse_feed(data, now), None
        except Exception as error:
            if attempt == 2:
                return feed, [], type(error).__name__
            time.sleep(2 ** attempt)


def collect(output, now=None):
    now = now or datetime.now(CST)
    feeds = json.loads((BASE / "feeds.json").read_text(encoding="utf-8"))
    sections, seen, warnings = [], set(), []
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda f: fetch_feed(f, now), feeds))
    for feed, articles, error in results:
        selected = []
        for article in articles:
            identity = re.sub(r"\W+", "", article["title"]).casefold()
            if identity in seen:
                continue
            seen.add(identity)
            selected.append(article)
            if len(selected) >= feed.get("limit", 4):
                break
        if selected:
            sections.append({"source": feed["name"], "articles": selected})
        else:
            warnings.append(feed["name"] + (": " + error if error else ": 近24小时无可用新闻"))
    if not sections:
        raise RuntimeError("所有订阅源均无有效新闻，停止生成，避免推送过期内容")
    record = {"date": now.astimezone(CST).date().isoformat(), "generated_at": now.isoformat(),
              "sections": sections, "warnings": warnings}
    lines = ["每日晨报 | " + record["date"], "近24小时新闻标题速览（北京时间）", ""]
    linked = list(lines)
    for section in sections:
        lines.append("【" + section["source"] + "】")
        linked.append("## " + section["source"])
        for index, item in enumerate(section["articles"], 1):
            lines.append(f"{index}. {item['title']}")
            linked.append(f"{index}. {item['title']}\n   {item['url']}")
        lines.append("")
        linked.append("")
    if warnings:
        lines.append("部分栏目暂缺：" + "；".join(warnings))
    lines.append("以上为订阅源原标题，未经AI改写。")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "brief.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "brief.txt").write_text("\n".join(lines), encoding="utf-8")
    (output / "brief.md").write_text("\n".join(linked), encoding="utf-8")
    print(f"Collected {sum(len(s['articles']) for s in sections)} headlines, {len(warnings)} unavailable feeds")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output")
    args = parser.parse_args()
    collect(args.output)
