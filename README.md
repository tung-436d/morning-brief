# 每日晨报 → QQ

GitHub Actions 在云端运行，电脑关机不影响执行。Python 仅使用标准库，无需大模型或联网检索服务。

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

Qmsg 沿用原项目的 `/v3/send/{key}` 接口，消息按 950 字符分段，间隔 5 秒，严格校验响应 `success=true`。网络结果不明确时不自动重试，避免重复消息；多段推送失败时前面的片段可能已经送达。

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
