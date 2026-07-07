#!/bin/zsh
#
# FigDataX headless extraction — the engine behind the Finder Quick Action.
# Usage: figx-headless.sh IMAGE [IMAGE...]
#
# Runs `claude -p` (billed to your Claude subscription) with a self-contained prompt:
# Claude follows the FigDataX SKILL.md autonomous loop on each image, writes
# {stem}_extracted.csv + {stem}_validation.png next to it, gathers a multi-sheet
# Excel when 2+ images are given, then we pop a macOS notification.
#
# Headless policy: Claude cannot ask questions here. At the SKILL.md gates it
# proceeds with its best judgment and FLAGS the uncertainty in the report/CSV.
# For tricky figures prefer the interactive /figx command in Claude Code.
#
# Env overrides:  FIGX_MODEL=claude-opus-4-8   (default: your configured model)

set -u
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

LOG="$HOME/Library/Logs/FigDataX-quickaction.log"
mkdir -p "$(dirname "$LOG")"

notify() {  # $1 title, $2 body
    /usr/bin/osascript -e "display notification \"$2\" with title \"$1\"" 2>/dev/null || true
}

if [ $# -eq 0 ]; then
    notify "FigDataX" "未收到图片。请选中图片后再运行。"
    exit 1
fi

CLAUDE="$(command -v claude || true)"
if [ -z "$CLAUDE" ]; then
    notify "FigDataX" "找不到 claude CLI。请确认已安装并登录 Claude Code。"
    echo "$(date '+%F %T') ERROR: claude CLI not on PATH" >> "$LOG"
    exit 1
fi

# Absolute paths; run from the first image's directory so outputs land beside it.
typeset -a IMGS
for f in "$@"; do
    IMGS+=("${f:A}")
done
WORKDIR="$(dirname "${IMGS[1]}")"
cd "$WORKDIR" || exit 1
N=${#IMGS[@]}

PATHS_BLOCK=""
for f in "${IMGS[@]}"; do
    PATHS_BLOCK+="- $f"$'\n'
done

PROMPT="使用 FigDataX skill(位于 ~/.claude/skills/FigDataX,先按其 SKILL.md 完成环境预检)提取以下 ${N} 张图片中的数据:

${PATHS_BLOCK}
无头模式规则(本次没有人可以回答问题):
- 严格按 SKILL.md 自主循环执行;禁止提问。遇到 GATE(刻度不可读/图例映射模糊)时按最合理判断继续,并在报告和 CSV 旁注中明确标注不确定项。
- 每张图输出 {stem}_extracted.csv 与 {stem}_validation.png,保存在该图所在目录。
- 图片≥2 张时,用 figdatax xlsx 汇总多 sheet Excel(含溯源表),保存为 $(basename "$WORKDIR")_figures.xlsx 于 ${WORKDIR}。
- 全部完成后,最后单独打印一行:SUMMARY: <图数> figures, <总点数> points, <不确定项数> flags"

MODEL_ARGS=()
[ -n "${FIGX_MODEL:-}" ] && MODEL_ARGS=(--model "$FIGX_MODEL")

notify "FigDataX" "开始提取 ${N} 张图… 完成后会再次通知。"
echo "$(date '+%F %T') START n=$N dir=$WORKDIR" >> "$LOG"

OUTPUT="$("$CLAUDE" -p "$PROMPT" --output-format text \
    --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Skill,Task,TodoWrite" \
    "${MODEL_ARGS[@]}" 2>>"$LOG")"
RC=$?
print -r -- "$OUTPUT" >> "$LOG"
echo "$(date '+%F %T') END rc=$RC" >> "$LOG"

SUMMARY="$(print -r -- "$OUTPUT" | grep -E '^SUMMARY:' | tail -1)"
if [ $RC -eq 0 ]; then
    notify "FigDataX 完成" "${SUMMARY:-输出已保存在图片目录} "
    # Reveal the workbook (batch) or the first CSV in Finder.
    XLSX="$WORKDIR/$(basename "$WORKDIR")_figures.xlsx"
    FIRST_CSV="${IMGS[1]%.*}_extracted.csv"
    if [ -f "$XLSX" ]; then open -R "$XLSX"; elif [ -f "$FIRST_CSV" ]; then open -R "$FIRST_CSV"; fi
else
    notify "FigDataX 失败" "详见日志: ~/Library/Logs/FigDataX-quickaction.log"
    open "$LOG"
fi
exit $RC
