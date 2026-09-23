"""Cloud entry point: fresh daily artifact, Qmsg delivery, no local config needed."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path

from collect_news import CST, collect
from push_brief import load_config, push_qmsg, QmsgContentRejected


def send_sections(directory, cfg):
    record = json.loads((directory / "brief.json").read_text(encoding="utf-8"))
    results = []
    for section in record["sections"]:
        text = "每日晨报 | " + record["date"] + "\n【" + section["source"] + "】\n"
        text += "\n".join(f"{i}. {item['title']}" for i, item in enumerate(section["articles"], 1))
        try:
            push_qmsg(text, cfg)
            results.append({"source": section["source"], "status": "sent"})
        except QmsgContentRejected:
            print("[Qmsg] 栏目被内容检测拦截：" + section["source"])
            results.append({"source": section["source"], "status": "content_rejected"})
        except RuntimeError as error:
            results.append({"source": section["source"], "status": "unconfirmed", "error": str(error)})
            (directory / "delivery.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            raise
    (directory / "delivery.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    rejected = [x["source"] for x in results if x["status"] != "sent"]
    if rejected:
        raise RuntimeError("部分栏目被Qmsg拦截，其他栏目已处理：" + "、".join(rejected))


def ensure_fresh(directory):
    meta = directory / "brief.json"
    try:
        record = json.loads(meta.read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(record["generated_at"])
        age = (datetime.now(CST) - generated).total_seconds()
        valid = (record["date"] == datetime.now(CST).date().isoformat()
                 and 0 <= age <= 3 * 3600 and (directory / "brief.txt").is_file())
    except (OSError, ValueError, KeyError, TypeError):
        valid = False
    if not valid:
        print("No fresh daily artifact; collecting now")
        collect(directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--channel", choices=['wecom', 'qmsg'], default='wecom')
    parser.add_argument("--style", choices=['paper', 'dark'], default=os.environ.get('BRIEF_STYLE') or 'dark')
    args = parser.parse_args()
    directory = Path(args.output)
    ensure_fresh(directory)
    from render_brief import render_all
    render_all(directory)
    text = (directory / "brief.txt").read_text(encoding="utf-8")
    if args.dry_run:
        print(text)
    elif args.channel == 'qmsg':
        send_sections(directory, load_config().get("qmsg", {}))
    else:
        from push_image import send_image
        cfg = load_config()
        webhook = os.environ.get('WECOM_WEBHOOK') or cfg.get('wecom', {}).get('webhook', '')
        send_image(directory / f'brief-{args.style}.png', webhook)
        (directory / 'delivery.json').write_text(json.dumps({'channel': 'wecom', 'status': 'api_success', 'style': args.style}), encoding='utf-8')
