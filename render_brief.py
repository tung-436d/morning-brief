"""Deterministic Chinese news layouts, generated from the daily RSS record."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1080
COLORS = ['#4bbdca', '#e5af51', '#5fbaa0', '#a893e4']
LABELS = ['DOMESTIC', 'GLOBAL', 'BUSINESS', 'TECHNOLOGY']


def font(size, bold=False):
    candidates = [os.environ.get('BRIEF_FONT', ''),
                  'C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc',
                  '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc' if bold else '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    for path in candidates:
        if path and Path(path).is_file():
            return ImageFont.truetype(path, size)
    raise RuntimeError('Chinese font missing: install fonts-noto-cjk or set BRIEF_FONT')


def wrap(draw, text, typeface, width):
    lines, current = [], ''
    for character in text:
        if character == '\n':
            lines.append(current)
            current = ''
        elif current and draw.textlength(current + character, font=typeface) > width:
            lines.append(current)
            current = character
        else:
            current += character
    if current:
        lines.append(current)
    return lines


def paragraph(draw, text, x, y, width, size, color, bold=False, max_lines=None):
    typeface = font(size, bold)
    lines = wrap(draw, text, typeface, width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][:-1] + '…'
    for line in lines:
        draw.text((x, y), line, font=typeface, fill=color)
        y += round(size * 1.5)
    return y


def stamp(article):
    from collect_news import CST
    return datetime.fromisoformat(article['published']).astimezone(CST).strftime('%m-%d %H:%M')


def render(record, destination, style='dark'):
    dark = style == 'dark'
    bg, ink, muted = ('#081722', '#e1ebf3', '#859bad') if dark else ('#faf9f5', '#20272d', '#717c83')
    # Oversized drawing surface is cropped to content, never scales text to fit.
    canvas = Image.new('RGB', (WIDTH, 14000), bg)
    d = ImageDraw.Draw(canvas)
    if dark:
        for x in range(0, WIDTH, 40):
            d.line((x, 0, x, 14000), fill='#10232f')
        for y in range(0, 14000, 40):
            d.line((0, y, WIDTH, y), fill='#10232f')
    accent = COLORS[0] if dark else '#293d49'
    d.rectangle((48, 52, 62, 108), fill=accent)
    d.text((82, 44), '每日新闻速递', font=font(54, True), fill=ink)
    d.text((84, 120), 'MORNING BRIEF  /  DAILY EDITION', font=font(19), fill=muted)
    d.text((766, 65), record['date'].replace('-', '.'), font=font(25, True), fill=ink)
    d.line((48, 165, 1032, 165), fill=accent, width=2)
    count = sum(len(s['articles']) for s in record['sections'])
    y = paragraph(d, f'近24小时  ·  {count} 条新闻  ·  {len(record["sections"])} 个栏目', 48, 185, 980, 24, muted)
    y += 30
    for index, section in enumerate(record['sections']):
        color = COLORS[index % len(COLORS)] if dark else ['#397baa', '#a56483', '#438879', '#8b73b1'][index % 4]
        name = section['source'].split('·')[-1]
        start = y
        d.rectangle((48, y, 55, y + 46), fill=color)
        d.text((72, y - 3), name, font=font(33, True), fill=color)
        d.text((158, y + 9), LABELS[index % 4], font=font(17), fill=muted)
        d.text((908, y + 4), f'{len(section["articles"]):02d} 条', font=font(24), fill=color)
        y += 72
        if dark:
            for i, article in enumerate(section['articles'], 1):
                d.rectangle((72, y + 9, 121, y + 47), fill=color)
                d.text((77, y + 6), f'{i:02d}', font=font(26, True), fill=bg)
                end = paragraph(d, article['title'], 146, y, 820, 35, ink, True)
                summary = article.get('summary', '')
                if summary:
                    end = paragraph(d, summary, 146, end + 13, 820, 24, muted, max_lines=3)
                end += 18
                d.text((146, end), section['source'], font=font(21), fill=color)
                d.text((786, end), stamp(article), font=font(21), fill=muted)
                y = end + 65
                if i != len(section['articles']):
                    d.line((146, y - 20, 988, y - 20), fill='#203541', width=1)
            d.line((48, start, 48, y - 12), fill=color, width=2)
            d.line((48, y - 12, 1032, y - 12), fill='#29404d')
        else:
            articles = section['articles']
            for pair in range(0, len(articles), 2):
                ends = []
                row = y
                for col, article in enumerate(articles[pair:pair + 2]):
                    x = 64 + col * 510
                    d.text((x, row), f'{pair + col + 1:02d}', font=font(21, True), fill=color)
                    end = paragraph(d, article['title'], x, row + 39, 435, 29, ink, True)
                    summary = article.get('summary', '')
                    if summary:
                        end = paragraph(d, summary, x, end + 14, 435, 23, muted, max_lines=5)
                    end += 24
                    d.text((x, end), stamp(article) + '  /  ' + section['source'].split('·')[0], font=font(18), fill=muted)
                    ends.append(end + 62)
                y = max(ends)
                d.line((540, row, 540, y - 24), fill='#d8dde0')
                d.line((64, y - 15, 1009, y - 15), fill='#d8dde0')
        y += 42
    d.line((48, y, 1032, y), fill=accent, width=2)
    y = paragraph(d, '来源：中新网 / IT之家  ·  按 RSS 发布时间整理', 48, y + 22, 980, 23, muted)
    y = paragraph(d, '仅展示来源标题与订阅摘要；不生成未经核实的热度评分。', 48, y + 7, 980, 21, muted)
    if record.get('warnings'):
        y = paragraph(d, '部分来源暂缺：' + '；'.join(record['warnings']), 48, y + 12, 980, 21, muted)
    y = paragraph(d, '生成于 ' + datetime.fromisoformat(record['generated_at']).strftime('%Y-%m-%d %H:%M') + ' CST', 48, y + 16, 980, 19, muted)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.crop((0, 0, WIDTH, y + 45)).save(destination, optimize=True)
    print(f'Generated {destination.name}: {WIDTH} x {y + 45}')


def render_all(directory):
    directory = Path(directory)
    record = json.loads((directory / 'brief.json').read_text(encoding='utf-8'))
    for style in ('dark', 'paper'):
        render(record, directory / f'brief-{style}.png', style)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='output')
    args = parser.parse_args()
    render_all(args.output)
