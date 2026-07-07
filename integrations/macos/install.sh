#!/bin/zsh
#
# Install the FigDataX zero-typing entry points:
#   1. /figx slash command  → ~/.claude/commands/figx.md
#   2. Finder Quick Action  → ~/Library/Services/FigDataX 提取数据.workflow
#      (select images in Finder → right-click → 快捷操作 → FigDataX 提取数据)
#
# Idempotent: re-running overwrites both. Uninstall: delete the two paths above.

set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "$HERE/../.." && pwd)"

# ── 1. slash command ──
mkdir -p "$HOME/.claude/commands"
cp "$SKILL_ROOT/integrations/claude-commands/figx.md" "$HOME/.claude/commands/figx.md"
echo "✓ /figx command → ~/.claude/commands/figx.md"

# ── 2. Finder Quick Action ──
chmod +x "$HERE/figx-headless.sh"
WF="$HOME/Library/Services/FigDataX 提取数据.workflow"
mkdir -p "$WF/Contents"

cat > "$WF/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>NSServices</key>
    <array>
        <dict>
            <key>NSBackgroundColorName</key>
            <string>background</string>
            <key>NSIconName</key>
            <string>NSActionTemplate</string>
            <key>NSMenuItem</key>
            <dict>
                <key>default</key>
                <string>FigDataX 提取数据</string>
            </dict>
            <key>NSMessage</key>
            <string>runWorkflowAsService</string>
            <key>NSSendFileTypes</key>
            <array>
                <string>public.image</string>
            </array>
        </dict>
    </array>
</dict>
</plist>
PLIST

# The workflow itself is a single Run-Shell-Script action ("as arguments") that
# delegates to figx-headless.sh — all real logic stays in that maintainable script.
cat > "$WF/Contents/document.wflow" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>AMApplicationBuild</key>
    <string>528</string>
    <key>AMApplicationVersion</key>
    <string>2.10</string>
    <key>AMDocumentVersion</key>
    <string>2</string>
    <key>actions</key>
    <array>
        <dict>
            <key>action</key>
            <dict>
                <key>AMAccepts</key>
                <dict>
                    <key>Container</key>
                    <string>List</string>
                    <key>Optional</key>
                    <true/>
                    <key>Types</key>
                    <array>
                        <string>com.apple.cocoa.string</string>
                    </array>
                </dict>
                <key>AMActionVersion</key>
                <string>2.0.3</string>
                <key>AMApplication</key>
                <array>
                    <string>Automator</string>
                </array>
                <key>AMParameterProperties</key>
                <dict>
                    <key>COMMAND_STRING</key>
                    <dict/>
                    <key>CheckedForUserDefaultShell</key>
                    <dict/>
                    <key>inputMethod</key>
                    <dict/>
                    <key>shell</key>
                    <dict/>
                    <key>source</key>
                    <dict/>
                </dict>
                <key>AMProvides</key>
                <dict>
                    <key>Container</key>
                    <string>List</string>
                    <key>Types</key>
                    <array>
                        <string>com.apple.cocoa.string</string>
                    </array>
                </dict>
                <key>ActionBundlePath</key>
                <string>/System/Library/Automator/Run Shell Script.action</string>
                <key>ActionName</key>
                <string>Run Shell Script</string>
                <key>ActionParameters</key>
                <dict>
                    <key>COMMAND_STRING</key>
                    <string>exec "\$HOME/.claude/skills/FigDataX/integrations/macos/figx-headless.sh" "\$@"</string>
                    <key>CheckedForUserDefaultShell</key>
                    <true/>
                    <key>inputMethod</key>
                    <integer>1</integer>
                    <key>shell</key>
                    <string>/bin/zsh</string>
                    <key>source</key>
                    <string></string>
                </dict>
                <key>BundleIdentifier</key>
                <string>com.apple.RunShellScript</string>
                <key>CFBundleVersion</key>
                <string>2.0.3</string>
                <key>CanShowSelectedItemsWhenRun</key>
                <false/>
                <key>CanShowWhenRun</key>
                <true/>
                <key>Class Name</key>
                <string>RunShellScriptAction</string>
                <key>InputUUID</key>
                <string>6A2B9F2E-0001-4E1A-9B6A-FIGDATAX0001</string>
                <key>Keywords</key>
                <array>
                    <string>Shell</string>
                </array>
                <key>OutputUUID</key>
                <string>6A2B9F2E-0002-4E1A-9B6A-FIGDATAX0002</string>
                <key>UUID</key>
                <string>6A2B9F2E-0003-4E1A-9B6A-FIGDATAX0003</string>
                <key>UnlocalizedApplications</key>
                <array>
                    <string>Automator</string>
                </array>
                <key>arguments</key>
                <dict/>
                <key>isViewVisible</key>
                <integer>1</integer>
                <key>location</key>
                <string>449.000000:316.000000</string>
                <key>nibPath</key>
                <string>/System/Library/Automator/Run Shell Script.action/Contents/Resources/Base.lproj/main.nib</string>
            </dict>
            <key>isViewVisible</key>
            <integer>1</integer>
        </dict>
    </array>
    <key>connectors</key>
    <dict/>
    <key>workflowMetaData</key>
    <dict>
        <key>applicationBundleIDsByPath</key>
        <dict/>
        <key>applicationPaths</key>
        <array/>
        <key>inputTypeIdentifier</key>
        <string>com.apple.Automator.fileSystemObject.image</string>
        <key>outputTypeIdentifier</key>
        <string>com.apple.Automator.nothing</string>
        <key>presentationMode</key>
        <integer>15</integer>
        <key>processesInput</key>
        <integer>0</integer>
        <key>serviceInputTypeIdentifier</key>
        <string>com.apple.Automator.fileSystemObject.image</string>
        <key>serviceOutputTypeIdentifier</key>
        <string>com.apple.Automator.nothing</string>
        <key>serviceApplicationBundleID</key>
        <string>com.apple.finder</string>
        <key>serviceApplicationPath</key>
        <string>/System/Library/CoreServices/Finder.app</string>
        <key>systemImageName</key>
        <string>NSActionTemplate</string>
        <key>useAutomaticInputType</key>
        <integer>0</integer>
        <key>workflowTypeIdentifier</key>
        <string>com.apple.Automator.servicesMenu</string>
    </dict>
</dict>
</plist>
PLIST

# Refresh the Services registry so the menu item appears without a logout.
/System/Library/CoreServices/pbs -update 2>/dev/null || true

echo "✓ Finder Quick Action → $WF"
echo ""
echo "用法:"
echo "  · Claude Code 里:  /figx  然后把图片拖进终端"
echo "  · Finder 里:      选中图片 → 右键 → 快捷操作 → FigDataX 提取数据"
echo "  · 模型可用环境变量覆盖:  FIGX_MODEL=claude-opus-4-8"
