# DECISIONS — FigDataX

> This document records every meaningful methodological, technical, and process decision made in this project.
> After reaching a decision with Claude Code or a collaborator, sink the conclusion here within 24 hours.
> Goal: preserve "why we did this" knowledge across devices, years, and tool changes.
>
> **Maintainer**: Shaowen Ye
> **Started**: 2026-07-07
> **Last updated**: 2026-07-07

---

## 1. Project metadata

| Field | Value |
|---|---|
| Project name | FigDataX — 高精度科学图表数据提取 skill |
| Primary goal | 从用户提供的论文图表图片中精准、自动地提取数值数据(agentic Claude Code skill) |
| Key deliverables | Claude Code skill(SKILL.md + `scripts/figdatax/` 引擎)、每图 CSV + 验证叠加图、批量 Excel 汇总 |
| Working directory | `~/.claude/skills/FigDataX` |
| Main repository | https://github.com/Shaowen-Ye/FigDataX |
| Funding / sponsor | — |

---

## 2. Decision index

> Quick scan. Update this table whenever a decision's status changes.

| ID | Date | Topic | Domain | Status |
|---|---|---|---|---|
| D-009 | 2026-07-07 | 零打字入口:/figx 命令 + Finder 快捷操作,替代自建 GUI | tooling | ✅ Accepted |
| D-008 | 2026-07-07 | 交付格式:CSV 为主 + Excel 汇总双轨 | process | ✅ Accepted |
| D-007 | 2026-07-07 | 架构分工:引擎管几何、Claude 管语义;detect_ticks 以测试把关 | code architecture | ✅ Accepted |
| D-006 | 2026-07-07 | 砍掉 PDF 摄取,输入一律为用户手动裁剪的图片 | scope | ✅ Accepted |
| D-005 | 2026-07-07 | 砍掉表格提取与文本数据线索挖掘 | scope | ✅ Accepted |
| D-004 | 2026-07-07 | 放弃桌面 App,全力打造 agentic skill | strategy | ✅ Accepted |
| D-003 | 2026-07-06 | 双轨产品:skill + PySide6 桌面 App | strategy | ❌ Superseded (D-004) |
| D-002 | 2026-07-06 | skill 自带 .venv(uv 引导)+ 重依赖惰性导入 | engineering | ✅ Accepted |
| D-001 | 2026-07-06 | 原地升级 FigDataX,不另立新名/新仓库 | process | ✅ Accepted |

**Status legend**

- ✅ Accepted — applied to analysis / code / writing
- 🟡 Proposed — under evaluation, awaiting evidence
- ⏸ Deferred — out of scope this phase
- 🔁 Revised — superseded in D-XXX
- ❌ Superseded — replaced by D-XXX (see section 4)

---

## 3. Decision records

> Reverse-chronological order. Newest at top.
> Once a decision is marked ✅ Accepted, the body is immutable. Changes go in a new D-XXX entry referencing the original.

---

### D-009 零打字入口:/figx 斜杠命令 + Finder 快捷操作,替代自建 GUI

- **Date**: 2026-07-07
- **Status**: ✅ Accepted
- **Domain**: tooling
- **Phase**: v2.0 易用性

**Background**

日常用法是在 iTerm2 的 Claude Code 里打一段话调 skill,重复且啰嗦。用户提出"能否搭 GUI 减少文字输入"。但 D-004 已确立不再维护独立 GUI 产品,需要在"减少打字"与"不造第二产品"之间找方案。

**Options considered**

1. 自建 GUI 启动器(小窗口/网页收图 → 调 `claude -p`)— 又一个要维护的产品,且必然阉割交互关口
2. `/figx` 斜杠命令 — 打字降到 5 字符 + 拖图,保留完整对话交互
3. Finder 右键快捷操作 — 真正零打字,`claude -p` 无头运行,但无法中途提问

**Decision**

采用 ②+③ 组合(`integrations/`):交互场景用 `/figx`,批量标准图用 Finder 右键"FigDataX 提取数据";不自建 GUI。

**Rationale**

1. Finder 本身就是 GUI——约 30 行脚本拿到"选图→右键→出结果"的全部收益,零维护面
2. 交互关口(GATE)只有对话内才能实现;斜杠命令保住这条路
3. 无头模式定义了明确的替代策略:不提问、按最优判断继续、把不确定项写入 `*_NOTES.txt`

**Consequences**

- ✓ 文字输入基本归零;AI 自主性不受损
- ✓ 逻辑集中在 `figx-headless.sh`,可测试、可同步 GitHub
- ✗ 无头模式遇疑难图不能问人,只能标注(疑难图应回到 /figx)
- ✗ Quick Action 依赖 macOS Services 机制,新装后可能需重启 Finder/重登录才出现在菜单

**References**

- Code: `integrations/claude-commands/figx.md`, `integrations/macos/figx-headless.sh`, `integrations/macos/install.sh`
- CC session: 2026-07-07 `GUI 减少文字输入 /figx quick action 无头`
- Related decisions: D-004

---

### D-008 交付格式:CSV 为主 + Excel 汇总双轨

- **Date**: 2026-07-07
- **Status**: ✅ Accepted
- **Domain**: process
- **Phase**: v2.0 收敛

**Background**

提取结果需要固定的默认交付格式。用户最初诉求包含"导出到 excel",但 CSV 更通用、可复现、易被后续分析脚本消费。

**Options considered**

1. 只出 CSV — 最简,但用户要 Excel 时多一步
2. 只出 Excel — 单文件友好,但不便脚本消费
3. CSV + Excel 双轨 — 每图一 CSV,多图汇总一个多 sheet Excel

**Decision**

采用双轨:每图 `{stem}_extracted.csv`(主输出)+ 批量时 `figdatax xlsx` 汇总多 sheet 工作簿(每图一表 + Index + Provenance 溯源表:方法/RMSE/验证轮数)。

**Rationale**

1. CSV 是可复现分析的通用接口;Excel 满足浏览与交付习惯
2. Provenance 表把"这批数是怎么来的"固化在交付物里,符合"无静默降级"原则

**Consequences**

- ✓ 两类使用场景都覆盖;溯源随文件走
- ✗ 引擎需维护 openpyxl 导出路径(已含测试)

**References**

- Code: `scripts/figdatax/export.py`, CLI `xlsx` 子命令
- CC session: 2026-07-07 `导出格式 CSV Excel 双轨`
- Related decisions: D-005

---

### D-007 架构分工:引擎管几何、Claude 管语义;detect_ticks 以测试把关保留

- **Date**: 2026-07-07
- **Status**: ✅ Accepted
- **Domain**: code architecture
- **Phase**: v2.0 核心设计

**Background**

旧流程要求人(或 Claude 猜测)提供刻度像素坐标与取色目标,是精度与易用性的最大瓶颈。需要确定自动化的边界:哪些环节机器做,哪些环节视觉/人做。

**Options considered**

1. 全引擎自动(含 OCR 读刻度值)— 引入重依赖,且 OCR 在小字体轴标签上不可靠
2. 全 Claude 视觉(连像素坐标也目测)— 像素级坐标目测误差大,违背亚像素精度目标
3. 分工:引擎测几何(绘图区、刻度线像素位、系列颜色、亚像素质心),Claude 视觉读语义(刻度值、图例),校准数学连接两者

**Decision**

采用 ③。新增 `detect_ticks`(亚像素刻度线定位,`spacing_cv` 置信信号,无刻度线时诚实返回 None)、`suggest_series`(颜色+几何分类)、`geometry` 一站式命令;配对约定固化:x 升序 px ↔ 升序值,y 升序 py ↔ **降序**值;校准 RMSE<1% 为硬门槛。`detect_ticks` 以合成图真值测试把关(线性 6/6、对数轴 4/4 主刻度 ±1px),不可靠即砍——最终通过保留。

**Rationale**

1. Claude 的视觉即 OCR,零依赖且能理解上下文(单位、量级)——这正是 agentic skill 相对纯程序的优势
2. 几何量必须亚像素精确,只有确定性算法能保证且可被 ground-truth 测试
3. "不可靠就砍"的把关原则避免了为长尾鲁棒性无限投入(负例:无刻度线图返回 None 回退网格叠加图)

**Consequences**

- ✓ 人工"点刻度/取色"环节完全消失;精度可测试、可回归
- ✓ 失败模式诚实(None / spacing_cv 警告),不会静默给错值
- ✗ y 轴配对方向是头号易错点,需在 SKILL.md 反复强调
- ✗ 无刻度线的图仍需网格叠加图人工/视觉读位

**References**

- Code: `scripts/figdatax/core.py` (`detect_ticks`, `draw_geometry_overlay`), `scripts/figdatax/extract.py` (`suggest_series`), `tests/test_ticks.py`
- CC session: 2026-07-07 `detect_ticks 测试把关 geometry 几何语义分工`
- Related decisions: D-004, D-006

---

### D-006 砍掉 PDF 摄取,输入一律为用户手动裁剪的图片

- **Date**: 2026-07-07
- **Status**: ✅ Accepted
- **Domain**: scope
- **Phase**: v2.0 收敛

**Background**

曾实现"加载 PDF → 检出并裁剪其中的图 → 喂给数字化提取"(pypdfium2,位图检测 + 矢量页整页渲染兜底)。用户实际试用判断:自己手动裁剪/截图/粘贴图更直接可控,自动检图反而引入不必要环节。

**Options considered**

1. 保留 PDF 摄取作为可选路径 — 维护面与依赖仍在,与主线无关
2. 完全移除,输入只收图片文件 — 最简

**Decision**

完全移除 `pdf.py`、`pdf-figures`/`pdf-page` 命令与 pypdfium2 依赖;skill 输入永远是用户提供的图片(单张或多张)。

**Rationale**

1. 用户裁图 10 秒可完成且完全可控;自动检图的矢量图兜底路径复杂且不可靠
2. 每砍一个依赖,环境引导与 CI 就更稳一分

**Consequences**

- ✓ 依赖回到 6 个核心包;范围叙事简单("图片进,数据出")
- ✗ 批量整刊处理需用户先自行裁图

**References**

- Code: commit `231bf6e`(移除),`27049ce`→reset(首版实现)
- CC session: 2026-07-07 `PDF不要 手动裁剪 复制粘贴上传`
- Related decisions: D-005, D-007

---

### D-005 砍掉表格提取与文本数据线索挖掘

- **Date**: 2026-07-07
- **Status**: ✅ Accepted
- **Domain**: scope
- **Phase**: v2.0 收敛

**Background**

扩张期曾设计并部分实现:pdfplumber 表格提取、正则数据线索扫描(均值±SD、n=、p 值等,含页码定位与图表交叉引用)。用户判断整体"搞得太复杂",这些功能产生需要人工筛选的信息噪音,偏离"从图里精准提数据"的核心。

**Options considered**

1. 保留为可选模块 — 噪音与维护面仍在
2. 全部移除 — 回归单一主线

**Decision**

移除 `mentions.py`、`detect_tables`/`TableRef` 及 pdfplumber 依赖;工作簿导出精简为仅图数据。

**Rationale**

1. 表格数据用户可直接复制;文本线索是"可能有用"而非"确定需要",违背按需原则
2. 单一主线让 SKILL.md 剧本、测试与文档都显著变短变准

**Consequences**

- ✓ 范围红线明确,防再次铺开
- ✗ 若未来确需表格,需另起独立工具而非塞回本 skill

**References**

- Code: commit `3fac834`(figures-only 重写)
- CC session: 2026-07-07 `太复杂 表格提取 文本数字性资料识别 都不要`
- Related decisions: D-004, D-006

---

### D-004 放弃桌面 App,全力打造 agentic skill

- **Date**: 2026-07-07
- **Status**: ✅ Accepted
- **Domain**: strategy
- **Phase**: 战略转向

**Background**

App(D-003)开发到 v0.2.0(数字化画布、项目保存、PDF 面板、AI provider 层、py2app 打包)后,用户实际评估:GUI 需要太多人工操作(点校准、取色、筛选结果),产生需要人工过滤的噪音——而这些恰是 Claude Code 原生能力(视觉、推理、对话)本可自动完成的。

**Options considered**

1. 继续双轨 — 维护两个产品,GUI 的交互模式与 AI 自动化根本冲突
2. 放弃 App,skill 单线 — Claude Code 本身就是"AI 层",skill 直接运行其上

**Decision**

停止 App 开发并从主干移除(源码存档于 tag `app-v0.2.0`,GitHub 上 app releases 删除、tag 保留);全部投入 agentic skill,最大化自动化,人机交互仅保留必要节点。

**Rationale**

1. App 内做 AI 集成是在复刻 Claude Code 已有能力,方向性错误
2. "减少人工操作"的正解是把人从执行环节移除,而不是给执行环节做更好的按钮
3. 单产品让测试、CI、文档、发布全部减半

**Consequences**

- ✓ 仓库回归纯 skill,聚焦干净;AI provider 层随 App 消亡(Claude Code 即 AI 层)
- ✓ App 期间沉淀的可移植模块(PDF/导出)曾短暂并入引擎(后续 D-005/D-006 进一步裁剪)
- ✗ 约两天的 App 开发投入沉没(但 py2app 打包、CI 经验与部分代码得到复用)

**References**

- Code: commit `d385ab5`(移除 app/)
- CC session: 2026-07-07 `不要app了 一门心思打造好skill 自动化智能化`
- Related decisions: 取代 D-003;引出 D-005, D-006, D-007, D-009

---

### D-003 双轨产品:skill + PySide6 桌面 App

- **Date**: 2026-07-06
- **Status**: ❌ Superseded (D-004)
- **Domain**: strategy
- **Phase**: 扩张期

**Background**

skill v1.0 硬化完成后,用户提出开发 macOS GUI 软件以"最大程度方便使用和管理",并支持 PDF 全文加载、图表检出、Excel 导出、数据线索提示,以及接入 Claude Max/Codex 订阅与第三方 API 的 AI 层。

**Options considered**

1. Python + Qt (PySide6) 复用引擎 — 单一语言,引擎零复制
2. Swift 原生 / Electron / Tauri — 需桥接或双语言栈

**Decision**

单仓双制品:根目录 skill + `app/` PySide6 桌面应用,双版本轨 `skill-v*` / `app-v*`,py2app 出未签名 .dmg。

**Rationale**

1. PySide6 与引擎同语言,`engine_bridge` 直接 import,单一真源
2. 无 Apple 开发者账号,未签名 .dmg + "右键→打开"可接受

**Consequences**

- ✓ 快速出到 v0.2.0(画布/项目/AI 层/打包/CI)
- ✗ 实际使用后发现 GUI 与 AI 自动化模式冲突 → 被 D-004 取代

**References**

- Code: tag `app-v0.2.0`(存档)
- CC session: 2026-07-06 `mac app GUI PDF excel 订阅`
- Related decisions: 被 D-004 取代

---

### D-002 skill 自带 .venv(uv 引导)+ 重依赖惰性导入

- **Date**: 2026-07-06
- **Status**: ✅ Accepted
- **Domain**: engineering
- **Phase**: v1.0 硬化

**Background**

审计发现 skill 在本机完全无法运行:所有系统 Python 都缺 scipy/matplotlib(PEP 668 保护无法直接 pip install),且模块级 import 使一个缺依赖拖垮全部功能。

**Options considered**

1. 文档指导用户手动装依赖 — 每台机器重复踩坑
2. skill 自带 `.venv`,`scripts/setup.sh` 用 uv 一键引导(回退 python -m venv)+ matplotlib/scipy 惰性导入
3. 依赖全部硬性要求 — 与"无静默降级"冲突且脆弱

**Decision**

采用 ②:SKILL.md 规定预检顺序(优先 `.venv/bin/python`,缺则 setup.sh 引导,再缺则显式告知降级项);仅 cv2+numpy 即可用大部分功能,缺重依赖的函数抛出带修复指引的 FigDataXError。

**Rationale**

1. uv 使全量安装仅数十秒,skill-local venv 不污染系统
2. 惰性导入 + 明确报错符合全局"无静默降级"原则
3. CI 用同一 setup 路径,环境问题在 CI 即暴露

**Consequences**

- ✓ 新机器/新用户一条命令可用;`self-test` 一键体检
- ✗ .venv 占约几百 MB 磁盘

**References**

- Code: `scripts/setup.sh`, `scripts/figdatax/core.py` `_require`
- CC session: 2026-07-06 `依赖阻断 PEP668 uv venv 惰性导入`
- Related decisions: D-007

---

### D-001 原地升级 FigDataX,不另立新名/新仓库

- **Date**: 2026-07-06
- **Status**: ✅ Accepted
- **Domain**: process
- **Phase**: v1.0 硬化

**Background**

大幅优化前,用户考虑"保留旧 FigDataX,新功能另立新名 skill + 新 GitHub 仓库"。需要权衡历史延续性、维护成本与触发词冲突。

**Options considered**

1. 新名 + 新仓库 — 旧版原封保留,但双份维护、社区资产归零、两个 skill 触发词冲突
2. 原地升级 + legacy tag 存档 — 单仓单 skill,旧版永久可回溯
3. 仓库保留、app 起副牌名 — 折中(随 D-004 失去意义)

**Decision**

原地升级:旧版打 `skill-v0.1.0-legacy` tag(GitHub Release 挂存档),新版本沿 `skill-vX.Y.Z` 演进;不新建仓库。

**Rationale**

1. 本次改动是严格超集(同目的、同 API 路径、同触发词),这正是版本号的用途
2. 两个近同触发词的 skill 同装会互相冲突,"保留旧版继续用"技术上不成立(旧版实测本就无法运行)
3. 存档价值用一个 tag 即完美实现

**Consequences**

- ✓ 历史/star/引用连续;单处维护
- ✗ 无(切换时尚未 push,零成本)

**References**

- Code: tags `skill-v0.1.0-legacy`, `skill-v1.0.0`, `skill-v2.0.0`
- CC session: 2026-07-06 `保留之前的 新名称 新github库 客观分析`
- Related decisions: D-003, D-004

---

## 4. Superseded decisions

> Preserved for traceability. Do not delete; mark with ❌ and note the replacing D-XXX.

- D-003(双轨产品:skill + 桌面 App)→ 被 D-004 取代,2026-07-07。App 源码存档于 tag `app-v0.2.0`。

---

## 5. Open questions

> Things that need a decision soon but aren't ripe. Once decided, move into section 3.

- [ ] `detect_ticks` 在真实论文扫描图(倾斜/低分辨率/内侧刻度)上的表现追踪——若失败率高,是否需要扩充启发式或维持网格叠加图兜底即可
- [ ] 同色多系列(全黑标记)图的形态学管线在 v2.0 剧本中的实战验证
- [ ] 是否需要 Windows/Linux 的零打字入口等价物(当前仅 macOS Quick Action)

---

## 6. Maintenance protocol

1. **Timeliness** — record decisions within 24 hours; memory drifts fast.
2. **Immutability** — accepted decisions are not edited. New direction = new D-XXX referencing the prior.
3. **Granularity** — one decision per entry. Split entangled topics.
4. **CC session references** — record date + keywords only. Do NOT paste raw conversation transcripts.
5. **Cross-project links** — use `[project-name]/D-XXX` if depending on another project's decision.
6. **Version control** — commit after each new entry: `decisions: D-XXX <title>`.

---

*Format inspired by Architecture Decision Records (ADR) but adapted for general research / engineering project use. See [adr.github.io](https://adr.github.io) for the original ADR concept.*
