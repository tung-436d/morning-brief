#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日早报推送脚本（纯标准库，无第三方依赖，Python 3.6+ 即可运行）

用法：
    python push_brief.py --file path/to/brief.md [--channel qmsg] [--dry-run]

支持渠道（channel）：
    qmsg        Qmsg酱 —— 推送到 QQ（私聊/群聊），需注册获取 key
    wecom       企业微信群机器人，需 webhook
    dingtalk    钉钉群机器人，需 webhook
    feishu      飞书群机器人，需 webhook
    serverchan  Server酱(方糖)，推送到微信服务号，需 sendkey
    pushplus    PushPlus，需 token

凭证统一在 config.json 中配置。
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_config():
    cfg = {"channel": "qmsg", "qmsg": {}}
    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    for field in ("key", "qq", "group"):
        value = os.environ.get("QMSG_" + field.upper())
        if value:
            cfg.setdefault("qmsg", {})[field] = value
    return cfg


def http_post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def http_post_form(url, fields):
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def split_text(text, limit=3500):
    """按行切分长文本，尽量保持 Markdown 块完整，避免超出单条消息长度限制。"""
    text = text.strip()
    if len(text) <= limit:
        return [text]
    chunks, buf = [], ""
    for line in text.split("\n"):
        if len(buf) + len(line) + 1 > limit and buf:
            chunks.append(buf.rstrip("\n"))
            buf = ""
        buf += line + "\n"
        while len(buf) > limit:  # 极端超长单行硬切
            chunks.append(buf[:limit])
            buf = buf[limit:]
    if buf.strip():
        chunks.append(buf.rstrip("\n"))
    return chunks


# ---------------- 渠道实现 ----------------

def push_qmsg(text, cfg):
    key = cfg.get("key", "")
    if not key:
        raise ValueError("qmsg.key 未配置：请到 https://qmsg.zendee.cn 注册并填写 KEY")
    qq = cfg.get("qq", "")
    group = cfg.get("group", "")
    # 官方限制：单条消息最长 1000 字符；同一 Key 每 5 秒最多推送一次
    chunks = split_text(text, 950)
    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(5)  # 遵守 5 秒限流
        url = "https://qmsg.zendee.cn/v3/send/%s" % key
        fields = {"msg": chunk}
        if group:
            fields["group"] = group
        elif qq:
            fields["qq"] = qq
        # Qmsg 失败时返回 HTTP 4xx + JSON body，需读出真实错误原因
        try:
            resp = http_post_form(url, fields)
        except urllib.error.HTTPError as e:
            raise RuntimeError("Qmsg HTTP 请求失败，状态码 %s" % e.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise RuntimeError("Qmsg 网络异常；未自动重试，以免重复推送") from None
        try:
            data = json.loads(resp)
        except json.JSONDecodeError:
            raise RuntimeError("Qmsg 返回非 JSON 响应，未确认发送成功") from None
        if not isinstance(data, dict) or data.get("success") is not True:
            raise RuntimeError("Qmsg 未确认发送成功，请检查服务后台及配额")
        print("[Qmsg] 已确认发送第 %d/%d 条" % (i + 1, len(chunks)))


def push_wecom(text, cfg):
    webhook = cfg.get("webhook", "")
    if not webhook:
        raise ValueError("wecom.webhook 未配置")
    for chunk in split_text(text, 3800):
        payload = {"msgtype": "markdown", "markdown": {"content": chunk}}
        print("[企业微信] " + http_post_json(webhook, payload))


def push_dingtalk(text, cfg):
    webhook = cfg.get("webhook", "")
    if not webhook:
        raise ValueError("dingtalk.webhook 未配置")
    payload = {"msgtype": "markdown",
               "markdown": {"title": "每日新闻速递", "text": text}}
    print("[钉钉] " + http_post_json(webhook, payload))


def push_feishu(text, cfg):
    webhook = cfg.get("webhook", "")
    if not webhook:
        raise ValueError("feishu.webhook 未配置")
    payload = {"msg_type": "text", "content": {"text": text}}
    print("[飞书] " + http_post_json(webhook, payload))


def push_serverchan(text, cfg):
    sendkey = cfg.get("sendkey", "")
    if not sendkey:
        raise ValueError("serverchan.sendkey 未配置")
    url = "https://sctapi.ftqq.com/%s.send" % sendkey
    print("[Server酱] " + http_post_form(url, {"title": "每日新闻速递", "desp": text}))


def push_pushplus(text, cfg):
    token = cfg.get("token", "")
    if not token:
        raise ValueError("pushplus.token 未配置")
    payload = {"token": token, "title": "每日新闻速递",
               "content": text, "template": "markdown"}
    print("[PushPlus] " + http_post_json("https://www.pushplus.plus/send", payload))


DISPATCH = {
    "qmsg": push_qmsg,
    "wecom": push_wecom,
    "dingtalk": push_dingtalk,
    "feishu": push_feishu,
    "serverchan": push_serverchan,
    "pushplus": push_pushplus,
}


def main():
    parser = argparse.ArgumentParser(description="每日早报推送脚本")
    parser.add_argument("--file", required=True, help="早报 Markdown 文件路径")
    parser.add_argument("--channel", default=None, help="覆盖 config.json 中的渠道")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不真正发送")
    args = parser.parse_args()

    cfg = load_config()
    channel = args.channel or cfg.get("channel", "qmsg")
    if channel not in DISPATCH:
        print("未知渠道: %s（可选: %s）" % (channel, "/".join(DISPATCH.keys())))
        sys.exit(2)

    with open(args.file, "r", encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        print("内容为空，跳过推送")
        return

    if args.dry_run:
        print("【DRY-RUN】渠道=%s  字符数=%d" % (channel, len(text)))
        print("-" * 40)
        print(text)
        return

    try:
        DISPATCH[channel](text, cfg.get(channel, {}))
        print("✅ 推送完成（渠道=%s）" % channel)
    except Exception as e:
        print("❌ 推送失败：%s" % e)
        sys.exit(1)


if __name__ == "__main__":
    main()
