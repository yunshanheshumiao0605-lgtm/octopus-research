# 🐙 Octopus · 章鱼

**你给一个话题，章鱼帮你搜集信息、核验来源、理清脉络，整理成有依据的中文研究。**

> 本项目基于 **[Matt Van Horn 的 last30days-skill](https://github.com/mvanhorn/last30days-skill)** 改良，沿用其 v3.3.2 采集引擎。原作者及贡献者提供了核心检索能力；Octopus 增加中文研究规则、按需启动的国内来源入口、每日增量记录和发布版配置说明。它是独立维护的衍生版本，不代表上游官方。

## 怎么用

安装到支持 Agent Skills 的助手后，直接说：

```text
章鱼，帮我研究下这个话题：中年女性独自旅行的真实需求和体验。
最近30天，AI 智能体有哪些真正落地的商业案例？
章鱼，比较这几种成人英语学习方法，区分研究证据和个人经验。
```

也可以显式调用 `$octopus`。研究不限于 AI、科技或商业；近期动态默认看近 30 天，专题归纳可以补充更早的背景资料。只有提出研究需求时才运行，普通聊天提到“章鱼”不会触发采集。

Octopus 是**一套供 AI 助手使用的研究技能和工具**。安装后，由具备联网检索能力的 AI 助手按照章鱼的流程搜集信息、核验来源，并整理成研究报告。采集脚本负责收集原始材料，资料分析与报告撰写由 AI 助手完成。

## 这个版本改了什么

- 根据问题选择来源，区分事实、宣传、个人经验、热度和推断。
- 关键判断提供直接来源和日期；查找反证，说明缺口，不以转载数量证明真实性。
- 取消固定英文模板和必须凑满的栏目，用中文按主题组织结果。
- 提供每日增量工具，处理日期、事实去重和成功截止时间；**不自动创建定时任务**。
- 国内来源按本次需要临时启动，正常结束、报错、超时或正常取消后清理本次进程。
- 发布包只包含代码和示例，不带维护者的账号、Cookie、API 密钥、个人资料或研究历史。

## 安装

基础运行需要 **Python 3.12+**，以及具备工具调用和联网检索能力的 AI 助手。部分来源另需 Node.js 或 API 配置。按需服务管理与每日增量工具使用 POSIX 功能，当前目标环境为 macOS / Linux；尚未验证 Windows 原生运行。

```sh
git clone https://github.com/yunshanheshumiao0605-lgtm/octopus-research.git
cd octopus-research
python3.12 tools/install.py
```

安装器把 `octopus` 和中文入口复制到 `${CODEX_HOME:-~/.codex}/skills/`。目标已存在时会拒绝覆盖，保护你自己的配置。安装不会下载第三方服务、导入登录信息或创建启动项。

使用其他支持 Agent Skills 的 AI 助手时，可将 `skills/octopus/` 和 `skills/octopus-query-alias/` 复制到对应的技能目录。如果 AI 助手尚未识别新技能，可重新打开会话后使用 `$octopus`。

## 信息来源与边界

| 来源 | 发布版提供什么 | 使用条件与限制 |
| --- | --- | --- |
| 公开网页、官方资料、研究与报道 | 按问题检索、打开原文、核验和归纳的规则 | 使用 AI 助手的联网工具执行 |
| Reddit、Hacker News、GitHub 等 | 上游采集引擎及适配器 | 实际受网络、权限、限流和各来源配置影响 |
| X、YouTube、其他社交平台 | 上游支持的可选采集路径 | 部分需要第三方 API、工具或用户凭据 |
| 小红书 | HTTP 适配器及按需服务入口 | 自行安装服务并扫码登录；列表不保证完整正文或准确日期 |
| 微信公众号 | WeRSS 客户端、按需启动入口 | 自行安装 WeRSS、扫码并配置公众号；不保证完整历史 |
| 微博、知乎、B 站 | RSSHub 采集入口及微博热榜扩展 | 是热榜/排行榜线索，不是全站搜索或视频转写 |

国内来源属于**可选集成**，不是这些平台提供的官方开放 API。第三方服务本体、浏览器、虚拟环境和可执行文件均不随仓库发布。安装和配置见 [可选信息源说明](docs/local-sources.md)。

来源失败时可以用 AI 助手的网页检索功能补充，但报告必须说明实际覆盖，不能把网页检索说成平台接口成功。

## 配置与保存

保留上游兼容设置：`LAST30DAYS_*` 环境变量、`~/.config/last30days/.env`、底层 `last30days.py` 文件名，以及默认输出目录 `~/Documents/Last30Days`。可设置 `LAST30DAYS_MEMORY_DIR` 改变报告目录。

[.env.example](.env.example) 只提供空值示例。按实际需要配置来源，基本网页研究不要求你购买所有 API。底层引擎沿用上游配置读取方式，包括环境变量、配置文件及可用的本机认证来源；不要把自己的 `.env` 或认证文件提交到仓库。

浏览器 Cookie 提取默认关闭：`FROM_BROWSER=off`、`BROWSER_CONSENT=false`。普通研究不安装新服务、不升级代码、不创建调度或对外发送消息。个人偏好可以写在技能目录的 `preferences.local.md` 中，该文件默认排除版本控制。

## 验证

```sh
python3.12 tools/check_release.py
python3.12 tools/run_checks.py
```

检查包含发布文件边界、路径、许可证、离线采集回归、日期去重和配置初始化。另附 [GitHub Actions 配置示例](docs/github-actions-example.yml)，需要有工作流权限的仓库管理员自行放入 `.github/workflows/` 后启用；本仓库尚未启用云端自动检查。离线通过不代表所有平台已登录、实时接口成功或每种主题的研究质量均已验证。

## 来源与许可证

- 核心引擎：[mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)，MIT，Copyright © 2026 Matt Van Horn。
- 随引擎保留的 Bird 搜索子集：Peter Steinberger 的 `@steipete/bird` v0.8.0，MIT，保留其独立许可证。
- 可选外部服务：[RSSHub](https://github.com/DIYgod/RSSHub)、[WeRSS](https://github.com/rachelos/we-mp-rss)、[xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp)；各自的许可证和版本见 [第三方来源声明](NOTICE.md)。

本仓库自有修改采用 MIT，保留上游版权与许可。详见 [LICENSE](LICENSE)。本项目不打包、转售或授权第三方平台内容。
