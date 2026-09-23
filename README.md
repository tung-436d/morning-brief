# 每日晨报 → QQ

GitHub Actions 在云端运行，电脑关机不影响执行。采集与推送使用 Python 标准库，图片排版使用 Pillow 和中文字体，无需大模型或联网检索服务。

## 每日时间（北京时间）

- **07:40**：读取 RSS，选取近 24 小时的国内、国际、财经、科技新闻，各最多 4 条，保存当天缓存。
- **08:00**：读取当天缓存，通过 Qmsg 推送 QQ。没有当天有效结果时重新采集；所有来源都不可用则任务失败，不发送旧新闻。

GitHub 的 cron 使用 UTC，分别是 `40 23 * * *` 和 `0 0 * * *`。定时任务可能延迟或被平台跳过，无法保证准点到达。公开仓库长期无活动时定时任务可能被停用，需要在 Actions 中重新启用。参见 [GitHub 定时任务说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

## GitHub 配置

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret | 用途 |
| --- | --- |
| `QMSG_KEY` | 必填，Qmsg 推送密钥 |
| `QMSG_QQ` | 可选，指定 QQ；空值沿用 Qmsg 后台接收人 |
| `QMSG_GROUP` | 可选，群号；设置时优先于 QQ |

工作流必须存在于默认分支。Actions → 每日晨报 → Run workflow 默认只预览；勾选 `send` 才会真实发送。手动推送及重跑会再次发送，请勿在已成功发送后重复执行。

公开仓库可查看源代码和工作流日志。密钥只保存在 Actions Secrets，本地 `config.json` 被 Git 忽略。不要上传任何真实配置。

## 新闻与输出

编辑 `feeds.json` 调整来源与条数。当前使用 [中新网官方 RSS](https://www.chinanews.com.cn/rss/) 和 [IT之家 RSS](https://www.ithome.com/rss/)。按发布时间过滤、按标题去重；部分源失败时使用其余来源，并注明缺失栏目。无日期或超过 24 小时的条目不会作为当天新闻。

QQ 正文只含新闻原标题和来源，不生成评论或事实推断。`output/brief.md` 保留原文链接，`brief.json` 保留结构化数据，`brief.txt` 是推送内容；每次运行的 Actions artifact 保留 7 天。为兼容 Qmsg 的消息过滤，QQ 消息不附 URL。

Qmsg 使用 `/v3/send/{key}` 提交，再通过 `/v3/msg/status/{key}` 查询 QQ 发送回执。提交成功不代表送达：只有状态 `1` 视为发送成功，`2` 为内容拦截，`-1` 为发送失败，`0` 为尚未回执（最多等待 60 秒）。按栏目分别提交，每条最多 950 字符；被拦截的栏目不改写重发，其余栏目继续处理。存在拦截时工作流会标记失败，具体结果记录在 artifact 的 `delivery.json` 中。网络结果不明确时不自动重发，以免重复。参见 [Qmsg 官方文档](https://qmsg.zendee.cn/docs)。

## 本地运行

需要 Python 3.10+。

```sh
python -m unittest discover -s tests -v
python collect_news.py
python cloud_brief.py --dry-run
```

真实推送前可复制 `config.example.json` 为 `config.json` 并填写密钥，或设置环境变量 `QMSG_KEY`：

```sh
python cloud_brief.py
```

此项目从既有 WorkBuddy 推送脚本迁移，所有后续修改在独立晨报工作目录中进行。


## 自动生成晨报长图

每天生成两份 1080 像素宽的 PNG：`output/brief-paper.png`（白底双栏）和 `output/brief-dark.png`（深色分区）。内容为 RSS 真实标题及源站摘要截取，附来源和发布时间；没有摘要时只展示标题，不编造正文或热度。图片与其他产物一起存入 Actions artifact。

当前 Qmsg 3.0 官方文档未公开图片消息接口，**长图已可自动生成，但尚未实现 QQ 图片直发**；现有文字推送保持运行。接入图片推送需要另行提供支持图片的消息接口，不能把图片网址当作已发送图片。

本地图片生成：

```sh
python -m pip install -r requirements.txt
python collect_news.py
python render_brief.py
```

Windows 自动使用微软雅黑；Ubuntu 安装 `fonts-noto-cjk`，或通过 `BRIEF_FONT` 指定中文字体文件。云端工作流已自动安装字体。
