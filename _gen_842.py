"""BIBLE v8.4.2 generator — applies targeted modifications to v8.4.1 base"""
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

INPUT = "BIBLE/BIBLE_Helix AI Studio_8.4.1.md"
OUTPUT = "BIBLE/BIBLE_Helix AI Studio_8.4.2.md"

with open(INPUT, "r", encoding="utf-8") as f:
    content = f.read()

original_len = len(content)

# =============================================
# 1. Title line
# =============================================
content = content.replace(
    '# BIBLE \u2014 Helix AI Studio v8.4.1 "Contextual Intelligence"',
    '# BIBLE \u2014 Helix AI Studio v8.4.2 "Contextual Intelligence"',
)

# =============================================
# 2. Version metadata block
# =============================================
content = content.replace(
    '**\u30d0\u30fc\u30b8\u30e7\u30f3**: 8.4.1 "Contextual Intelligence" (Patch)',
    '**\u30d0\u30fc\u30b8\u30e7\u30f3**: 8.4.2 "Contextual Intelligence" (Patch 2)',
)
content = content.replace(
    '**\u524d\u30d0\u30fc\u30b8\u30e7\u30f3**: 8.4.0 "Contextual Intelligence"',
    '**\u524d\u30d0\u30fc\u30b8\u30e7\u30f3**: 8.4.1 "Contextual Intelligence" (Patch)',
)

# =============================================
# 3. Project overview table (1.1)
# =============================================
content = content.replace(
    "| \u30d0\u30fc\u30b8\u30e7\u30f3 | 8.4.1 |",
    "| \u30d0\u30fc\u30b8\u30e7\u30f3 | 8.4.2 |",
)

# =============================================
# 4. Version history table — add v8.4.2 row
# =============================================
old_841_row = (
    "| **v8.4.1** | **Contextual Intelligence (Patch)** "
    "| **BibleParser\u756a\u53f7\u4ed8\u304d\u898b\u51fa\u3057\u5bfe\u5fdc\u30fbBIBLE\u8a18\u8ff0\u4fee\u6b63"
    "\uff08\u30bf\u30a4\u30e0\u30a2\u30a6\u30c8\u914d\u7f6e\u30fbGPU\u540d\u79f0\uff09** |"
)
new_rows = (
    "| v8.4.1 | Contextual Intelligence (Patch) "
    "| BibleParser\u756a\u53f7\u4ed8\u304d\u898b\u51fa\u3057\u5bfe\u5fdc\u30fbBIBLE\u8a18\u8ff0\u4fee\u6b63"
    "\uff08\u30bf\u30a4\u30e0\u30a2\u30a6\u30c8\u914d\u7f6e\u30fbGPU\u540d\u79f0\uff09 |\n"
    "| **v8.4.2** | **Contextual Intelligence (Patch 2)** "
    "| **BibleParser\u6839\u672c\u4fee\u6b63\uff08discover\u2192parse_full\uff09"
    "\u30fb\u8a2d\u5b9a\u6c38\u7d9a\u5316\u4fee\u6b63\u30fb\u4fdd\u5b58\u30dc\u30bf\u30f3\u7d71\u4e00** |"
)
content = content.replace(old_841_row, new_rows)

# =============================================
# 5. Add v8.4.2 changelog section
# =============================================
# Find the v8.4.1 changelog file table (Appendix G)
# We'll insert v8.4.2 changelog right before the architecture section (## 3.)
# Actually, better: insert right after the v8.4.1 Patch section ends

v842_section = """
---

## v8.4.2 "Contextual Intelligence" Patch 2 \u5909\u66f4\u5c65\u6b74

### \u30b3\u30f3\u30bb\u30d7\u30c8

v8.4.1\u691c\u8a3c\u3067\u767a\u898b\u3055\u308c\u305fP0\u30d0\u30b0\u306e\u6839\u672c\u4fee\u6b63\u3068UI\u7d71\u4e00\u3002BibleParser\u304c\u30bb\u30af\u30b7\u30e7\u30f3\u30920\u4ef6\u3068\u8868\u793a\u3057\u7d9a\u3051\u3066\u3044\u305f3\u30d0\u30fc\u30b8\u30e7\u30f3\u8de8\u304e\u306e\u30d0\u30b0\u3092\u6839\u672c\u89e3\u6c7a\u3002

### \u4e3b\u306a\u5909\u66f4\u70b9

1. **[P0] BibleParser\u6839\u672c\u4fee\u6b63** \u2014 `BibleDiscovery.discover()`\u304c`parse_header()`\u306e\u307f\u547c\u3073\u51fa\u3057\u3066\u3044\u305f\u305f\u3081\u30bb\u30af\u30b7\u30e7\u30f3\u304c\u5e38\u306b0\u4ef6\u3060\u3063\u305f\u554f\u984c\u3092\u4fee\u6b63\u3002`parse_full()`\u306b\u5909\u66f4\u3057\u3001\u5168BIBLE\u3067\u30bb\u30af\u30b7\u30e7\u30f3\u691c\u51fa\u30fb\u5b8c\u5168\u6027\u30b9\u30b3\u30a2\u304c\u6b63\u5e38\u306b\u52d5\u4f5c\u3002\u691c\u8a3c\u7d50\u679c: 32 BIBLE\u691c\u51fa\u3001\u6700\u65b0v8.4.1\u306f23\u30bb\u30af\u30b7\u30e7\u30f3/89.0%\u5b8c\u5168\u6027
2. **[P0] \u8a2d\u5b9a\u4fdd\u5b58\u4e0d\u80fd\u30d0\u30b0\u4fee\u6b63** \u2014 `max_phase2_retries`\u304c`OrchestratorConfig`\u306edataclass\u30d5\u30a3\u30fc\u30eb\u30c9\u306b\u5b58\u5728\u305b\u305a\u3001`_update_config_from_ui()`\u3067\u3082\u66f4\u65b0\u3055\u308c\u3066\u3044\u306a\u304b\u3063\u305f\u554f\u984c\u3092\u4fee\u6b63\u3002dataclass\u30d5\u30a3\u30fc\u30eb\u30c9\u8ffd\u52a0\u30fb`to_dict()`\u5bfe\u5fdc\u30fb\u8d77\u52d5\u6642\u5fa9\u5143(`_restore_ui_from_config`)\u30fb\u4fdd\u5b58\u6642\u66f4\u65b0\u306e\u5b8c\u5168\u30b5\u30a4\u30af\u30eb\u3092\u5b9f\u88c5
3. **[P1] mixAI\u4fdd\u5b58\u30dc\u30bf\u30f3\u5f62\u72b6\u7d71\u4e00** \u2014 \u5168\u5e45\u30b7\u30a2\u30f3`PRIMARY_BTN`\u30b9\u30bf\u30a4\u30eb\u304b\u3089soloAI/\u4e00\u822c\u8a2d\u5b9a\u3068\u540c\u3058\u53f3\u5bc4\u305b\u5c0f\u578b\u30dc\u30bf\u30f3\u306b\u5909\u66f4\u3002`QHBoxLayout` + `addStretch()` + `addWidget()`\u30d1\u30bf\u30fc\u30f3

### \u6839\u672c\u539f\u56e0\u5206\u6790

| \u30d0\u30b0 | \u539f\u56e0 | \u4fee\u6b63 |
|------|------|------|
| BIBLE 0\u30bb\u30af\u30b7\u30e7\u30f3 | `BibleDiscovery.discover()` L67,L84\u304c`parse_header()`\u3092\u547c\u3073\u51fa\u3057\u3002`parse_header()`\u306f\u30e1\u30bf\u30c7\u30fc\u30bf\u306e\u307f\u62bd\u51fa\u3057\u3001`sections`\u30ea\u30b9\u30c8\u3092\u5e38\u306b\u7a7a\u306e\u307e\u307e\u8fd4\u5374 | `parse_full()`\u306b\u5909\u66f4\u3002\u30bb\u30af\u30b7\u30e7\u30f3\u691c\u51fa\u30fb\u5b8c\u5168\u6027\u30b9\u30b3\u30a2\u304c\u6b63\u5e38\u306b\u52d5\u4f5c |
| \u8a2d\u5b9a\u4fdd\u5b58\u4e0d\u80fd | `max_phase2_retries`\u304c`OrchestratorConfig`\u306edataclass\u30d5\u30a3\u30fc\u30eb\u30c9\u306b\u306a\u304f\u3001`_update_config_from_ui()`\u3067\u3082\u672a\u66f4\u65b0\u3002SpinBox\u5024\u306f\u9001\u4fe1\u6642\u306b\u76f4\u63a5\u8aad\u307f\u53d6\u3089\u308c\u308b\u304c\u6c38\u7d9a\u5316\u3055\u308c\u306a\u3044 | dataclass\u30d5\u30a3\u30fc\u30eb\u30c9\u8ffd\u52a0\u30fb`to_dict()`\u5bfe\u5fdc\u30fb\u8d77\u52d5\u6642\u5fa9\u5143\u30fb\u4fdd\u5b58\u6642\u66f4\u65b0 |
| \u30dc\u30bf\u30f3\u4e0d\u7d71\u4e00 | mixAI\u306e\u307f`PRIMARY_BTN`\u30b9\u30bf\u30a4\u30eb\u3067\u5168\u5e45\u30b7\u30a2\u30f3\u30dc\u30bf\u30f3\u3002soloAI/\u4e00\u822c\u8a2d\u5b9a\u306f\u53f3\u5bc4\u305b\u5c0f\u578b | `QHBoxLayout` + `addStretch()`\u3067\u53f3\u5bc4\u305b\u7d71\u4e00 |

### \u5909\u66f4\u30d5\u30a1\u30a4\u30eb\u4e00\u89a7 (v8.4.2)

| \u30d5\u30a1\u30a4\u30eb | \u5909\u66f4\u5185\u5bb9 |
|----------|----------|
| `src/bible/bible_discovery.py` | `parse_header()` \u2192 `parse_full()` (L67, L84) |
| `src/backends/tool_orchestrator.py` | `OrchestratorConfig`\u306b`max_phase2_retries: int = 2`\u30d5\u30a3\u30fc\u30eb\u30c9\u8ffd\u52a0\u3001`to_dict()`\u306b\u8ffd\u52a0 |
| `src/tabs/helix_orchestrator_tab.py` | `_update_config_from_ui()`\u306b`max_phase2_retries`\u66f4\u65b0\u8ffd\u52a0\u3001`_restore_ui_from_config()`\u65b0\u8a2d\u3001\u4fdd\u5b58\u30dc\u30bf\u30f3\u53f3\u5bc4\u305b\u7d71\u4e00 |
| `src/utils/constants.py` | `APP_VERSION` \u2192 "8.4.2"\u3001`APP_DESCRIPTION`\u66f4\u65b0 |
| `config/app_settings.json` | `version` \u2192 "8.4.2" |
"""

# Find insertion point: after the v8.4.1 patch section, before "## 3." (Architecture)
# The v8.4.1 section has a file table ending, followed by ---
# Let's find "## 3." which is the architecture section
arch_marker = "\n## 3. "
arch_idx = content.find(arch_marker)
if arch_idx > 0:
    # Insert v8.4.2 section before ## 3.
    content = content[:arch_idx] + v842_section + content[arch_idx:]
    print(f"Inserted v8.4.2 changelog before architecture section at pos {arch_idx}")
else:
    print("WARNING: Could not find ## 3. marker!")

# =============================================
# 6. Add Appendix H for v8.4.2
# =============================================
appendix_h = """
---

## \u4ed8\u9332H: v8.4.2 Patch 2 \u5909\u66f4\u8a73\u7d30

| # | \u5bfe\u8c61 | \u5909\u66f4\u5185\u5bb9 | \u512a\u5148\u5ea6 |
|---|--------|----------|--------|
| 1 | `bible_discovery.py` L67 | `BibleParser.parse_header(match)` \u2192 `BibleParser.parse_full(match)` | P0 |
| 2 | `bible_discovery.py` L84 | \u540c\u4e0a\uff08Phase 2\u89aa\u30c7\u30a3\u30ec\u30af\u30c8\u30ea\u63a2\u7d22\uff09 | P0 |
| 3 | `tool_orchestrator.py` OrchestratorConfig | `max_phase2_retries: int = 2` \u30d5\u30a3\u30fc\u30eb\u30c9\u8ffd\u52a0 | P0 |
| 4 | `tool_orchestrator.py` to_dict() | `"max_phase2_retries": self.max_phase2_retries` \u8ffd\u52a0 | P0 |
| 5 | `helix_orchestrator_tab.py` _update_config_from_ui() | `self.config.max_phase2_retries = self.max_retries_spin.value()` \u8ffd\u52a0 | P0 |
| 6 | `helix_orchestrator_tab.py` __init__ | `_restore_ui_from_config()` \u65b0\u8a2d\uff08\u8d77\u52d5\u6642\u306bSpinBox\u5024\u5fa9\u5143\uff09 | P0 |
| 7 | `helix_orchestrator_tab.py` \u4fdd\u5b58\u30dc\u30bf\u30f3 | `PRIMARY_BTN`\u5168\u5e45 \u2192 `QHBoxLayout`+`addStretch()`\u53f3\u5bc4\u305b\u5c0f\u578b | P1 |
| 8 | `constants.py` | `APP_VERSION` "8.4.1" \u2192 "8.4.2" | P2 |
| 9 | `app_settings.json` | `version` "8.4.1" \u2192 "8.4.2" | P2 |

### \u691c\u8a3c\u7d50\u679c

| \u30c6\u30b9\u30c8 | \u7d50\u679c |
|--------|------|
| `BibleParser.parse_full()` \u76f4\u63a5\u5b9f\u884c | 23\u30bb\u30af\u30b7\u30e7\u30f3 / 89.0% \u5b8c\u5168\u6027 |
| `BibleDiscovery.discover('.')` | 32 BIBLE\u691c\u51fa\u3001\u5168\u4ef6sections > 0 |
| \u5fc5\u9808\u30bb\u30af\u30b7\u30e7\u30f3\u30c1\u30a7\u30c3\u30af | 5/6 PASS (FILE_LIST\u306e\u307f\u672a\u691c\u51fa \u2014 \u898b\u51fa\u3057\u5f62\u5f0f\u304c\u300c\u5909\u66f4\u30d5\u30a1\u30a4\u30eb\u4e00\u89a7\u300d\u306e\u305f\u3081) |

"""

# Insert Appendix H at the end (before the final generation notice)
gen_notice = "*\u3053\u306eBIBLE\u306f"
gen_idx = content.rfind(gen_notice)
if gen_idx > 0:
    content = content[:gen_idx] + appendix_h + "\n---\n\n" + content[gen_idx:]
    # Update the generation notice
    content = content.replace(
        "*\u3053\u306eBIBLE\u306f Helix AI Studio v8.4.1",
        "*\u3053\u306eBIBLE\u306f Helix AI Studio v8.4.2",
    )
    print(f"Inserted Appendix H before generation notice at pos {gen_idx}")
else:
    # Just append
    content += appendix_h
    print("Appended Appendix H at end of file")

# =============================================
# 7. Update any remaining "v8.4.1" in generation notices
# =============================================
content = content.replace(
    "BIBLE_Helix AI Studio_8.4.1",
    "BIBLE_Helix AI Studio_8.4.2",
    1,  # Only first occurrence in generation notice at bottom
)

# =============================================
# Write output
# =============================================
with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(content)

lines = content.count("\n") + 1
print(f"\nGenerated: {OUTPUT}")
print(f"Lines: {lines}")
print(f"Chars: {len(content)}")
print(f"Delta from v8.4.1: +{len(content) - original_len} chars")
