# CLAUDE.md — FigDataX 开发简报

本文件面向**开发这个仓库**的会话。使用 skill 提数据请看 [SKILL.md](SKILL.md)(唯一工作流真源)。

## 这个项目是什么

一个 agentic Claude Code skill:用户提供从论文裁剪的图表**图片**(单张或多张),skill 精准提取数值(CSV + 可选 Excel + 溯源),精度目标 ±0.5%,以验证叠加图自证。

架构分工(见 DECISIONS.md D-007):**引擎管几何**(绘图区、刻度像素位、系列颜色、亚像素质心——确定性、可测试),**Claude 管语义**(视觉读刻度值/图例),校准数学连接两者,RMSE<1% 硬门槛。

## 范围红线(勿建议扩回,详见 DECISIONS.md)

- ❌ 桌面 App(D-004,源码在 tag `app-v0.2.0`)
- ❌ PDF 摄取/自动检图(D-006,用户手动裁图)
- ❌ 表格提取、文本数据线索挖掘(D-005)
- ❌ OCR 依赖(Claude 视觉即 OCR)

新方向先记入 DECISIONS.md 再动手;重要决策 24 小时内落 D-XXX 条目。

## 布局与命令

```
scripts/figdatax/    引擎包(core/calibrate/extract/morph/charts/validate/export/cli)
scripts/setup.sh     .venv 一键引导(uv)
tests/               pytest,合成图 ground-truth(tests/synth.py 含刻度像素真值)
references/          SKILL.md 的按需加载文档
integrations/        /figx 命令 + macOS Finder Quick Action
```

```bash
PY=.venv/bin/python
bash scripts/setup.sh                               # 环境引导
PYTHONDONTWRITEBYTECODE=1 $PY -m pytest tests/ -q   # 全量测试(必须全绿)
$PY -m scripts.figdatax self-test                   # 快速体检(含刻度检测断言)
```

## 约定

- 版本 tag:`skill-vX.Y.Z`;每个逻辑变更一个 commit,改动必须带测试
- 惰性导入重依赖(core.py `_require` 模式);仅 cv2+numpy 时包必须可 import
- OpenCV 陷阱:BGR、H∈[0,179]、像素 y 向下(y 轴配对=升序 py↔降序值)
- 输出永远保存在输入图片旁,绝不写入 skill 目录
- CI:单 job(macos-14,pytest + self-test),push main 与 skill-v* tag 触发
