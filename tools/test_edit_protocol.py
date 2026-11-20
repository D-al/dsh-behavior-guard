#!/usr/bin/env python3
"""Verify that the edit protocol in config/AGENTS.md contains all required elements."""

import re
import sys

AGENTS_PATH = "config/AGENTS.md"

# Protocol elements that must be present (keywords/phrases to search for)
REQUIRED_ELEMENTS = [
    {
        "id": "short_file_write",
        "label": "Short file (<400 lines) → write full file",
        "patterns": [r"<\s*400\s*>.*(?:write|整块)", r"(?:短文件|短.*<400).*(?:write|整块)"],
    },
    {
        "id": "long_file_anchor",
        "label": "Long file ≥400 lines → near-read + minimal anchor",
        "patterns": [r">=\s*400.*(?:anchor|锚点|近读|near.?read)", r"(?:长文件|≥400).*(?:anchor|锚点|minimal)"],
    },
    {
        "id": "compaction_reread",
        "label": "Compaction/long session → force reread before edit",
        "patterns": [r"(?:压缩|compaction|长会话).*(?:重读|reread|强制)"],
    },
    {
        "id": "edit_doctor",
        "label": "Edit failure → doctor mode: byte-level diff, don't loop blindly",
        "patterns": [r"(?:edit.*失败|编辑.*失败|doctor).*(?:字节|byte|diff|差异)", r"(?:(?:tab|crlf|nbspace)|缩进).*差"],
    },
    {
        "id": "root_cause_rope",
        "label": "Root cause: RoPE offset + small model drift evidence",
        "patterns": [r"(?:RoPE|位置编码|偏移|drift|漂移).*(?:2607\.16072|arXiv)"],
    },
]


def main():
    try:
        with open(AGENTS_PATH, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"FAIL: {AGENTS_PATH} not found")
        return 1

    all_pass = True
    for elem in REQUIRED_ELEMENTS:
        matched = False
        for pat in elem["patterns"]:
            if re.search(pat, content, re.IGNORECASE | re.DOTALL):
                matched = True
                break
        status = "PASS" if matched else "FAIL"
        print(f"[{status}] {elem['label']} ({elem['id']})")
        if not matched:
            all_pass = False

    # Also check that the protocol section header exists
    if not re.search(r"编辑协议.*S14|降低复现负担", content):
        print("[FAIL] Protocol section header (S14 / 降低复现负担)")
        all_pass = False
    else:
        print("[PASS] Protocol section header (S14 / 降低复现负担)")

    total = len(REQUIRED_ELEMENTS) + 1
    passed = sum(1 for e in REQUIRED_ELEMENTS if any(re.search(p, content, re.I | re.S) for p in e["patterns"])) + (
        1 if re.search(r"编辑协议.*S14|降低复现负担", content) else 0
    )
    print(f"\nResult: {passed}/{total} checks passed")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
