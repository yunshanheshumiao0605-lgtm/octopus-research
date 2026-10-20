# 可选本地来源：配置与按需运行

本文件适用于 macOS / Linux。操作系统、第三方依赖和平台行为可能变化；以下版本是集成参考，不是全平台可用保证。平台访问应使用自己的账号及获准访问的内容。

## 1. 初始化私有配置

先安装 Octopus，再选需要的组件。以下命令以 Codex 安装位置为例；使用其他 AI 助手时，把 `skill_dir` 改成实际的技能安装路径。

```sh
skill_dir="${CODEX_HOME:-$HOME/.codex}/skills/octopus"
python3.12 "$skill_dir/scripts/init_local_sources.py" --services domestic,xiaohongshu
```

也可以只选 `domestic` 或 `xiaohongshu`。初始化器只生成私有配置和随机认证信息，不下载依赖、不导入 Cookie、不登录或启动服务。已有配置保持原样。私有文件写入各组件的 `runtime/` 目录，文件权限为 `0600`。

默认端口固定为 RSSHub `18200`、WeRSS `18001`、小红书 `18060`，均绑定 `127.0.0.1`。当前启动器的健康检查与端口对应，配置中不要单独改变端口。端口已被占用时启动器拒绝接管或停止已有服务。

## 2. 微博、知乎和 B 站：RSSHub

来源：[DIYgod/RSSHub](https://github.com/DIYgod/RSSHub)，AGPL-3.0。参考提交为 `1c7e106e63bcc6725fe6b13f39544385666c89c0`。该版本要求 Node.js `^22.22.2` 或 `^24.15.0`，集成参考使用 pnpm `10.34.6`。

自行安装对应 Node.js 和 pnpm 后：

```sh
mkdir -p "$skill_dir/local-sources/domestic/services"
git clone https://github.com/DIYgod/RSSHub.git "$skill_dir/local-sources/domestic/services/rsshub"
git -C "$skill_dir/local-sources/domestic/services/rsshub" checkout 1c7e106e63bcc6725fe6b13f39544385666c89c0
cd "$skill_dir/local-sources/domestic/services/rsshub"
pnpm install --frozen-lockfile --ignore-scripts
pnpm build
```

如依赖或构建发生变化，参照对应提交的上游说明。`run_rsshub.py` 从 `PATH` 查找 Node.js，也支持设置 `NODE_BIN` 为可执行文件的绝对路径。需要浏览器的路由可以设置 `CHROME_BIN` 为自己安装的 Chrome/Chromium 路径；示例微博路由不提取浏览器 Cookie。

按需采集：

```sh
python3.12 "$skill_dir/scripts/domestic_sources.py" --sources weibo,zhihu,bilibili --output /tmp/octopus-candidates.json
```

编辑 `local-sources/domestic/runtime/sources.json` 可以调整 RSSHub 路由和关键词。默认 `topics` 为空；关键词只产生标签，不过滤候选。默认 B 站路由是科技区排行榜，换研究领域时应选择相关路由或跳过。

## 3. 微信公众号：WeRSS

来源：[rachelos/we-mp-rss](https://github.com/rachelos/we-mp-rss)，参考提交 `d94db01372105bc479db81a0ac91829dac7f43e4`，该提交的 LICENSE 为 MIT。

```sh
mkdir -p "$skill_dir/local-sources/domestic/services"
git clone https://github.com/rachelos/we-mp-rss.git "$skill_dir/local-sources/domestic/services/werss"
git -C "$skill_dir/local-sources/domestic/services/werss" checkout d94db01372105bc479db81a0ac91829dac7f43e4
python3.12 -m venv "$skill_dir/local-sources/domestic/services/werss/.venv"
"$skill_dir/local-sources/domestic/services/werss/.venv/bin/python" -m pip install -r "$skill_dir/local-sources/domestic/services/werss/requirements.txt"
```

按上游说明安装其需要的浏览器；已有 Chrome/Chromium 可以通过 `CHROME_BIN` 指定。使用本包的启动器，不直接运行上游 `main.py`；本包关闭定时采集、外部通知和级联服务。

扫码登录使用自己的微信读书会话：

```sh
python3.12 "$skill_dir/scripts/source_session.py" --services werss -- python3.12 "$skill_dir/local-sources/domestic/wx_client.py" qr --wait-login
```

命令输出二维码图片的本机路径，打开图片扫码；成功或等待超时后服务自动关闭。助手执行时应展示二维码供使用者本人确认。

公众号列表默认为空。在 `runtime/sources.json` 的 `wechat_accounts` 数组中填入自己确认的公众号，例如：

```json
{"id": "你确认的公众号ID", "name": "公众号名称"}
```

ID 可先用 `wx_client.py mp-test --mp-id <ID>` 在同一按需服务入口中验证。初始化器不会自动关注公众号；如需要，将公众号添加到自己的微信读书书架后再采集。

```sh
python3.12 "$skill_dir/scripts/domestic_sources.py" --sources wechat --sync-wechat --output /tmp/octopus-wechat.json
```

公众号覆盖取决于订阅列表、会话和接口。WeRSS 可能把采集时间写入备用日期字段，不能用它直接证明文章在今天发布。

## 4. 小红书

来源：[xpzouying/xiaohongshu-mcp v2.5.5](https://github.com/xpzouying/xiaohongshu-mcp/releases/tag/v2.5.5)，Apache-2.0。

从上游发布页下载适合自己系统的可执行文件，放到：

```text
local-sources/xiaohongshu/bin/xiaohongshu-mcp
```

赋予执行权限。也可在私有 `runtime/service.json` 的 `binary_path` 指定其他相对或绝对路径。默认 `headless` 为 false，运行时可能出现浏览器窗口。上游的其他浏览器依赖按其文档安装。

```sh
chmod +x "$skill_dir/local-sources/xiaohongshu/bin/xiaohongshu-mcp"
python3.12 "$skill_dir/scripts/source_session.py" --services xiaohongshu -- python3.12 "$skill_dir/local-sources/xiaohongshu/api_client.py" login --wait-login
```

初始化器生成独立的服务 token。按需入口只向本次子进程传入 `XIAOHONGSHU_API_BASE` 和 `XIAOHONGSHU_API_TOKEN`，不把值打印到终端，不需要把 token 写进命令行或提交到 GitHub。

登录后检查：

```sh
python3.12 "$skill_dir/scripts/source_session.py" --services xiaohongshu -- python3.12 "$skill_dir/local-sources/xiaohongshu/api_client.py" status
```

实际引擎调用见 [engine.md](engine.md) 的小红书段落。当前适配器的时间筛选是粗粒度发现机制，不保证覆盖任意指定日期区间；不把未知日期记作近 30 天内的已核实事实。

## 运行边界

初始化和登录是使用者明确执行的配置步骤。日常研究只启动选中的来源，用完关闭，不创建登录启动项、后台常驻或每日计划。强杀整个进程、断电等情况不能保证清理；不要根据代码存在就报告服务已可用。

登录状态、私有配置、数据库、日志、二维码和抓取结果只保存在本机。共享仓库时不要强制添加被忽略的 `runtime/`、`services/`、`bin/` 或 `.env`。
