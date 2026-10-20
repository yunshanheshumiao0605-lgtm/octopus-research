# HTML 导出

仅在用户要求时导出。先完成有来源、日期和覆盖说明的中文研究，再把正文写入本次运行目录的 `synthesis.md`。

使用同一技能目录的引擎，将正文传给渲染器：

```sh
FROM_BROWSER=off BROWSER_CONSENT=false FUN_LEVEL=off python3.12 "$skill_dir/scripts/last30days.py" "$topic" --emit=html --synthesis-file "$synthesis_file" --save-dir "$run_dir"
```

先核对当前引擎参数。使用本次研究已保存的材料，不因导出重复进行无关检索；不能把生成 HTML 等同于外部发布。核对文件存在、来源链接及重要的覆盖缺口仍在正文中，再交付文件。

渲染器保留部分上游 last30days 标识与来源信息，这是底层引擎的命名；不会自动更改成平台官方报告或暗示第三方背书。
