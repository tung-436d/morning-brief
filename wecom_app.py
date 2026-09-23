"""WeCom internal app: access token -> temporary image -> application message."""
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid

API = 'https://qyapi.weixin.qq.com/cgi-bin/'


class WeComError(RuntimeError):
    pass


def request_api(endpoint, params=None, body=None, content_type=None):
    url = API + endpoint
    if params:
        url += '?' + urllib.parse.urlencode(params)
    headers = {'Content-Type': content_type} if content_type else {}
    request = urllib.request.Request(url, data=body, headers=headers)
    proxy = os.environ.get('WECOM_HTTPS_PROXY')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({'https': proxy})) if proxy else urllib.request.build_opener()
    try:
        with opener.open(request, timeout=40) as response:
            data = json.load(response)
    except (urllib.error.URLError, OSError, ValueError):
        raise WeComError('企业微信网络或响应异常；不自动重发，避免重复消息') from None
    if not isinstance(data, dict):
        raise WeComError('企业微信响应格式异常')
    code = data.get('errcode', 0)
    if type(code) is not int or code != 0:
        if code == 60020:
            # Only expose the IP, never the raw response or token-bearing URL.
            match = re.search(r'from ip:\s*([0-9a-fA-F:.]+)', str(data.get('errmsg', '')))
            ip = match.group(1).rstrip(',') if match else '未知'
            raise WeComError('企业微信错误60020：出口IP ' + ip + ' 未在应用可信IP中；云端定时发送需要固定出口')
        raise WeComError('企业微信 API 错误码：' + str(code))
    return data


def get_token(corpid, corpsecret):
    if not corpid or not corpsecret:
        raise WeComError('缺少 CORPID 或 CORPSECRET')
    data = request_api('gettoken', {'corpid': corpid, 'corpsecret': corpsecret})
    if not data.get('access_token'):
        raise WeComError('企业微信未返回 access_token')
    return data['access_token']


def check_agent(token, agentid):
    if not str(agentid).isdigit():
        raise WeComError('AGENTID 必须为数字')
    request_api('agent/get', {'access_token': token, 'agentid': agentid})
    print('[WeCom App] 应用访问检查通过')


def upload_image(token, path):
    data = Path(path).read_bytes()
    if not 5 <= len(data) <= 2 * 1024 * 1024:
        raise WeComError('企业微信图片素材需介于5字节与2MB之间')
    boundary = 'MorningBrief' + uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="media"; filename="brief.png"\r\n'
            'Content-Type: image/png\r\n\r\n').encode() + data + f'\r\n--{boundary}--\r\n'.encode()
    result = request_api('media/upload', {'access_token': token, 'type': 'image'}, body,
                         'multipart/form-data; boundary=' + boundary)
    if not result.get('media_id'):
        raise WeComError('企业微信未返回素材 media_id')
    return result['media_id']


def send_app_image(path, cfg, check_only=False):
    token = get_token(cfg.get('corpid'), cfg.get('corpsecret'))
    agentid = cfg.get('agentid', '')
    check_agent(token, agentid)
    if check_only:
        return {'channel': 'wecom_app', 'status': 'connection_ok'}
    user = cfg.get('touser', '').strip()
    if not user or user == '@all':
        raise WeComError('请配置 TOUSER 为接收人的成员UserID；不默认广播给全体成员')
    media = upload_image(token, path)
    payload = {'touser': user, 'agentid': int(agentid), 'msgtype': 'image',
               'image': {'media_id': media}, 'safe': 0}
    result = request_api('message/send', {'access_token': token},
                         json.dumps(payload).encode(), 'application/json')
    if any(result.get(k) for k in ('invaliduser', 'invalidparty', 'invalidtag', 'unlicenseduser')):
        raise WeComError('企业微信报告接收人不可用或不在应用可见范围，不能确认全部发送成功')
    print('[WeCom App] 图片消息 API 返回成功；微信端接收仍需关注微信插件并在应用可见范围内')
    return {'channel': 'wecom_app', 'status': 'api_success', 'msgid': result.get('msgid')}


def app_config(local):
    cfg = dict(local.get('wecom_app', {}))
    for field in ('corpid', 'corpsecret', 'agentid', 'touser'):
        if os.environ.get(field.upper()):
            cfg[field] = os.environ[field.upper()]
    return cfg
