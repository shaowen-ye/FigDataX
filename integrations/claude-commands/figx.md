---
description: FigDataX 图表数据提取 — 拖入图片路径即可(单张或多张)
argument-hint: <图片路径…> [附加要求]
---

使用 FigDataX skill 提取以下图片中的数据:

$ARGUMENTS

执行要求:
- 严格按 FigDataX SKILL.md 的自主循环执行:几何检测(geometry 命令)→ 亲自查看注释图核验 → 视觉读刻度值并配对(x 升序、y 降序)→ 校准(RMSE<1% 硬门槛)→ 提取 → 亲自查看验证叠加图 → 必要时迭代(≤3 轮)。
- 每张图输出 `{stem}_extracted.csv` + `{stem}_validation.png`,保存在图片所在目录。
- 图片 ≥2 张时,额外用 `figdatax xlsx` 汇总一个多 sheet Excel(含溯源表),命名 `{目录名}_figures.xlsx`。
- 图片 ≥3 张时,按 SKILL.md 批量模式并行分派子代理。
- 仅在两个关口(刻度放大后仍不可读 / 图例与颜色映射模糊)时用 AskUserQuestion 问我;其余一律自主决策。
- 最终给出提取报告:每图的方法、校准 RMSE、点数、验证轮数、精度估计与输出路径。
