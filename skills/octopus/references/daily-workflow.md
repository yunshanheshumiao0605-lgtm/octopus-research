# 每日增量执行说明

`scripts/daily_brief.py` 是标准库本地工具，无网络、无模型调用，不读取认证配置。它不创建调度，也不发送消息。所有调用均使用同一选定的 `state_dir`（默认研究输出根目录）和本次唯一 `run_dir`。

本流程适用于用户主动请求的某领域日更研究，不限于 AI、科技和商业。不同主题或地区的连续简报应使用各自稳定的 `state_dir` 子目录，避免另一主题的成功截止时间让本次遗漏信息；同一主题后续调用复用原目录。没有主题时才使用默认综合兴趣。此规则不创建每日定时计划。

## 1. 确定时间和历史

```sh
python3.12 "$skill_dir/scripts/daily_brief.py" --state-dir "$state_dir" window > "$run_dir/window.json"
```

返回北京时间起止、内部 UTC 时间戳、上次成功截止时间、历史版本，以及用于引擎粗筛的 `engine_lookback_days`。首次看过去 24 小时；检索额外覆盖至少近 7 天以寻找延迟材料。随后按原始时间戳精筛，不能把日级日期当作精确时刻。

历史不存在时首次建立，不声称已经核对旧简报。历史损坏时工具报错且不会重置；应保留文件，说明无法确认跨日重复，修复前不写成功状态。

## 2. 采集并整理候选

按 `engine.md` 调用相关引擎来源，并补充符合主题与地区范围的公开网页。国内动态按主题和证据缺口选择来源；需要这些平台时才按 `sources.md` 调用 `scripts/domestic_sources.py --sources <所选平台> --output "$run_dir/domestic-candidates.json"`，选公众号时增加 `--sync-wechat`。入口负责临时启动和结束清理。从实际返回中挑选线索，再核验原文与发布时间。该输出不是已核实事件 manifest，不能原样提交。平台未配置或不可用时记录为 unavailable。不要向外发送个人背景。核实候选后写入 `manifest.json`，结构如下（内容仅演示，不是真实新闻；coverage 的来源与 required 应随实际范围调整，不要求地方主题强行覆盖海外）：

```json
{
  "coverage": [
    {"source": "国内公开网页与原始出处", "status": "ok", "required": true},
    {"source": "海外公开网页与原始出处", "status": "ok", "required": true},
    {"source": "Reddit", "status": "unavailable", "required": false}
  ],
  "events": [
    {
      "event_key": "示例公司|示例产品v2发布",
      "claim": "从核验原文提取的一项具体变化",
      "facts": {"availability": "public_beta"},
      "published_at": "2026-10-20T08:00:00+08:00",
      "sources": ["https://example.com/actual-source"],
      "update_reason": "若之前报道过，说明本次新增的事实"
    }
  ]
}
```

必须替换示例为真实核验材料，不能凭空生成精确时间。只有日期时用 `YYYY-MM-DD`，未知时用 null。这里的 published_at 应指支撑本次新事实的原始证据时间，不能用今天的转载日期把旧闻变新。

`event_key` 以稳定实体、事件和版本命名，不使用新闻标题；相同事件在不同网站和语言间复用同一键。`facts` 的键和值统一表达同一语义，例如 availability / public_beta，避免措辞变化造成假更新。数字或价格用明确单位的字符串。新来源链接本身不算新增事实。

主题已有历史时，先参照 `daily-events.json` 的事件及事实键，识别同义事件。此语义归并由主持模型负责，脚本不宣称自动完成语义理解。观点相反或数据冲突先保留不确定性、回查证据，不覆盖成肯定结论。

## 3. 过滤与选稿

```sh
python3.12 "$skill_dir/scripts/daily_brief.py" --state-dir "$state_dir" select --window "$run_dir/window.json" --manifest "$run_dir/manifest.json" > "$run_dir/selection.json"
```

- `accepted`：有时间依据的新事实或已解释的实质更新。仍需人工/模型按可信度、重要性和相关性选稿，不是全部自动刊登。
- `review`：只有日期、时间不明、未来时间或没有解释增量；继续核验。找不到精确时间时只能作为日期待核/背景材料，不能当成已核实的 24 小时新增。
- `skipped`：已经报道的事实或超出检索窗口的材料。
- `delayed_evidence`：窗口前但在回看范围内首次发现的材料，入选时明确写“补充发现”，不能写成今天刚发生。

如果 selection 的判断需要改动，修改已核验的 manifest 再运行；不要手工改 selection 绕过检查。发生并行写入时工具会拒绝旧版本，应重新准备窗口与筛选。

## 4. 保存最终简报并提交记录

把实际入选事件的 `event_id` 数组写到 `included.json`，例如 `["实际返回的event_id"]`。没有值得入选的新内容时可以为 `[]`，简报如实说明检索结果。把最终中文简报保存为 `brief.md` 后执行：

```sh
python3.12 "$skill_dir/scripts/daily_brief.py" --state-dir "$state_dir" commit --selection "$run_dir/selection.json" --included "$run_dir/included.json" --brief "$run_dir/brief.md" --status complete
```

只提交实际写进简报且在 accepted 中的事件；待核内容不记成已核实的入选事实。required 来源未完成时用 `--status partial`，保留成功采集的材料但不推进完整完成时间。

工具验证简报存在、事件选择和历史版本，使用文件锁与原子替换保护索引。一次运行重复提交不会重复计数。索引保存报告文件哈希，交付状态始终为 `not_recorded`；工具不会声称推送成功。

这套规则在用户调用日更研究时执行。定时运行需由已有调度显式调用本技能，或在用户要求时另行配置；不要把修改技能等同于定时任务已更新。
