"""Cloud entry point: fresh daily artifact, Qmsg delivery, no local config needed."""
import argparse
from datetime import datetime
import json
from pathlib import Path

from collect_news import CST, collect
from push_brief import load_config, push_qmsg


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
    args = parser.parse_args()
    directory = Path(args.output)
    ensure_fresh(directory)
    text = (directory / "brief.txt").read_text(encoding="utf-8")
    if args.dry_run:
        print(text)
    else:
        push_qmsg(text, load_config().get("qmsg", {}))
