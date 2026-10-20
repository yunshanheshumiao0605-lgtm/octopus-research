# 引擎调用

本技能安装目录为 `octopus`。底层引擎仍使用上游文件名 `last30days.py` 和既有配置项，以下 `skill_dir` 应指向当前 Octopus 的主 SKILL.md 所在目录。

使用主 SKILL.md 所在目录的 `scripts/last30days.py`，不要在其他缓存目录寻找同名脚本。Python 需 3.12+；优先使用本机已存在的 `python3.12`，缺失时寻找已有受支持解释器，不自动安装。

## 预研究与查询计划

先确认用户主题；人物、机构、地名、产品或项目同名时通过公开网页消歧。根据领域选择相关社区、机构或其他已启用平台的目标；技术主题可查 GitHub 仓库，不强制包含开发者平台或每个平台。

近期动态默认 30 天。专题知识或历史研究按问题使用适当日期窗口；更早的基础资料可通过公开网页和原始文献补充并注明年代，不能把引擎日期限制误写成整个技能的主题或资料限制。没有相关平台适配器时以对应领域的网页证据完成研究，如实报告引擎未覆盖的部分。

主持模型把 1–4 个有针对性的子问题写入 JSON 文件。不要把 JSON 内联到 shell 引号中。最低结构示例：

```json
{
  "intent": "product",
  "freshness_mode": "balanced_recent",
  "cluster_mode": "story",
  "subqueries": [
    {
      "label": "primary",
      "search_query": "用户指定产品名 具体用途",
      "ranking_query": "哪些新变化有明确证据，哪些反馈来自具体使用经验？",
      "sources": ["reddit", "hackernews", "github"],
      "weight": 1.0
    }
  ]
}
```

示例中的产品和来源按实际任务替换。日更或新闻用 `intent=breaking_news` 和 `freshness_mode=strict_recent`；比较用 `cluster_mode=debate`。概念和教程可用 `evergreen_ok`，但旧资料必须标注。

查询词保留准确专名和类别，时间由日期参数处理。检索关键词、排名问题和实际证据分开，不能把想要的结论写成事实。

## 普通调用

```sh
FROM_BROWSER=off BROWSER_CONSENT=false FUN_LEVEL=off python3.12 "$skill_dir/scripts/last30days.py" "$topic" --plan "$plan_file" --search "$sources" --days "$lookback_days" --emit=compact --save-dir "$run_dir"
```

这里的路径、主题和来源变量由当前任务先明确设置。shell 参数保持引用，使用唯一运行目录。用户没有选择深度时采用默认；`--quick` 和 `--deep` 仅调整采集量。不要把 `--deep` 与需要额外服务的 `--deep-research` 混淆。

可按已解析结果添加 `--x-handle`、`--x-related`、`--subreddits`、`--github-user`、`--github-repo`、`--tiktok-hashtags`、`--tiktok-creators`、`--ig-creators`。不要传空参数或未经核对的账号。实际参数以同版本 parser 为准。

比较任务可用 `A vs B` 和 `--competitors-plan <JSON文件>`，分别指定实体的账号、社区和仓库。实体参数只对相应实体使用，避免把 A 的账号套给 B。

计划无法使用主持环境网页检索时，可以在已配置后端允许的范围内使用 `--auto-resolve`；缺少资料就说明。不要为运行研究自动启动首次配置向导。

## 证据、输出与保存

完整读取结果中的来源、日期、错误、原文摘录和不确定性。必要时补充公开网页搜索，尤其是中国来源、官方可用性与独立反证；根据缺口决定搜索量，不为固定数量重复查找。

把补充资料的直接 URL、日期、支持的关键事实写入本次 `web-supplement.md`。保存最终中文简报到本次 `brief.md`。引擎保存的 raw 文件保留调试证据，聊天输出不复制其英文格式和统计树。

保存路径采用 UTC 时间戳、稳定主题摘要及唯一运行标识，支持中文并防止覆盖。以日志返回的实际路径为准。

普通调用显式禁用浏览器提取。只有获得针对该动作的明确同意后，才能同时使用有效的 `FROM_BROWSER` 与 `BROWSER_CONSENT=true`；不自动沿用未经确认的旧开关。

## 小红书按需运行

仅当本次选用 xiaohongshu 时，用下列入口包裹原引擎命令，避免先做可用性检查而把正常停机的信息源误判为未配置：

```sh
FROM_BROWSER=off BROWSER_CONSENT=false FUN_LEVEL=off python3.12 "$skill_dir/scripts/source_session.py" --services xiaohongshu -- python3.12 "$skill_dir/scripts/last30days.py" "$topic" --plan "$plan_file" --search "$sources" --days "$lookback_days" --emit=compact --save-dir "$run_dir"
```

`sources` 仍按本次任务选择并包含 xiaohongshu。包装入口等待本机服务就绪，命令结束后清理服务及其浏览器子进程；默认命令时限 900 秒，可按任务需要显式调整 `--timeout`。不要重新创建 LaunchAgent 或常驻服务。不选用小红书时按普通调用运行，不启动该服务。
