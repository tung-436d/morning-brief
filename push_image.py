"""Send a generated PNG as a native WeCom group robot image message."""
import base64
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.parse

from push_brief import http_post_json


def send_image(path, webhook):
    parsed = urllib.parse.urlparse(webhook)
    if (parsed.scheme != 'https' or parsed.netloc != 'qyapi.weixin.qq.com'
            or parsed.path != '/cgi-bin/webhook/send'
            or not urllib.parse.parse_qs(parsed.query).get('key')):
        raise ValueError('请配置有效的 WECOM_WEBHOOK 企业微信群机器人地址')
    data = Path(path).read_bytes()
    if len(data) > 2 * 1024 * 1024:
        raise ValueError('图片超过企业微信2MB限制，未发送')
    payload = {'msgtype': 'image', 'image': {
        'base64': base64.b64encode(data).decode('ascii'),
        'md5': hashlib.md5(data).hexdigest()}}
    try:
        response = json.loads(http_post_json(webhook, payload))
    except (urllib.error.URLError, OSError, ValueError):
        raise RuntimeError('企业微信请求或响应异常；未自动重发以免重复') from None
    code = response.get('errcode') if isinstance(response, dict) else None
    if type(code) is not int or code != 0:
        raise RuntimeError('企业微信拒绝图片消息，错误码：%s' % code)
    print('[WeCom] 图片消息接口返回成功：' + Path(path).name)
