#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M3 重定位原型：反模式匹配的目标锚定 + 确定性状态机（RGE 式，2026-11-22）

依据：
- Apollo Research arXiv:2505.02709：state complexity ablation 证明"状态复杂度"不是漂移成因，
  主因是长上下文的 pattern-matching → 所以不建"更大的意图槽"，而是检测"行为是否在模仿历史模式"
- RGE arXiv:2608.17718：LLM 只做一次性结构化抽取，信任更新/投影/干预全用确定性代码
- StepShield arXiv:2601.22136：高召回但时机随机=没用 → 检测结果必须带"时机"

原型边界（诚实）：
- extract_anchor 用启发式规则，**不是生产版**；生产版应在会话起点/用户改口时用一次 LLM 抽取
  (Role, Goal, Evidence) 三元组（RGE 式），成本约一次 35B 调用
- 状态机/漂移检测是确定性代码，可直接复用
- 不改 index.mjs 的 bdi 结构（需人工确认，M3 autonomous=false）
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict

# ── 1. 抽取器（原型启发式；生产版换 LLM 一次抽取）──

GOAL_VERBS = ('写', '做', '建', '实现', '改成', '生成', '检查', '修', '分析', '对比', '验证', '测试',
              '查', '找', '统计', '运行', '总结', '评估', '试', '补', '重测', '提交', '推送', '复核')
STOP = set('帮我 请你 一个 这个 一下 什么 怎么 可以 是否 以及 然后 现在 需要 给个 展示 能不能 有没有'.split())


def keywords(t: str) -> set:
    return {w for w in re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z][\w-]{1,}', t) if w not in STOP}


@dataclass
class Anchor:
    role: str           # 用户身份/协作角色（原型：从"我是/作为"抽，缺省"用户"）
    goal: str           # 当前主目标（首条指令的核心句）
    evidence: List[str] = field(default_factory=list)  # 已确认的约束/追加需求
    superseded: List[str] = field(default_factory=list)  # 被推翻/折叠的旧需求
    updated_at_step: int = 0


def extract_anchor(text: str, step: int = 0) -> Anchor:
    """单次抽取（原型启发式）。生产版：此处调 LLM 一次，输出同结构。"""
    clean = re.split(r'[。！\n]', text.strip())[0][:120]
    role_m = re.search(r'(我是|作为|我是个)\s*([\u4e00-\u9fa5]{2,10})', text)
    role = role_m.group(2) if role_m else '用户'
    return Anchor(role=role, goal=clean, evidence=[clean], updated_at_step=step)


# ── 2. 确定性状态机：意图生命周期（折叠用户改口）──

class AnchorState:
    def __init__(self, anchor: Anchor):
        self.anchor = anchor
        self.drift_events: List[Dict] = []

    def update(self, user_text: str, step: int) -> bool:
        """用户新指令：追加证据 or 推翻旧目标（折叠）。返回是否发生目标级冲突。"""
        kw = keywords(user_text)
        old_kw = keywords(self.anchor.goal)
        overlap = len(kw & old_kw) / max(1, len(old_kw))
        hard_override = bool(re.search(
            r'(不要|别|取消|改成|改为|换成|重新|不做了|放弃|忽略之前|覆盖之前)', user_text))
        if hard_override and overlap < 0.25:
            # 目标级改口：折叠旧目标进 superseded，新目标上位（StateForge 式折叠）
            self.anchor.superseded.append(self.anchor.goal)
            self.anchor.goal = re.split(r'[。！\n]', user_text.strip())[0][:120]
            self.anchor.evidence = [self.anchor.goal]
            self.anchor.updated_at_step = step
            self.drift_events.append({'step': step, 'type': 'goal_override',
                                      'overlap': round(overlap, 3)})
            return True
        # 需求追加：进证据，不动目标
        self.anchor.evidence.append(user_text[:160])
        self.anchor.updated_at_step = step
        return False

    def snapshot(self) -> Dict:
        return {'role': self.anchor.role, 'goal': self.anchor.goal,
                'evidence_count': len(self.anchor.evidence),
                'superseded_count': len(self.anchor.superseded),
                'updated_at_step': self.anchor.updated_at_step}


# ── 3. 反模式匹配检测（核心创新点，确定性、零 LLM）──

def pattern_match_drift(tool_sequence: List[str], anchor: Anchor, window: int = 12) -> Dict:
    """检测 agent 行为是否陷入"重复历史模式"而偏离锚定目标。

    论文依据：goal drift 主因是长上下文 pattern-matching（arXiv:2505.02709），
    不是状态没存好。所以信号不是"意图槽变没变"，而是"行为序列的重复度"。
    """
    if len(tool_sequence) < window:
        return {'detected': False, 'reason': 'too-short', 'n': len(tool_sequence)}
    recent = tool_sequence[-window:]
    prior = tool_sequence[-2*window:-window]
    if not prior:
        return {'detected': False, 'reason': 'no-prior', 'n': len(tool_sequence)}
    # 连续重复同一工具（循环）+ 与锚定目标关键词脱节 → 反模式匹配告警
    from collections import Counter
    c = Counter(recent)
    most, count = c.most_common(1)[0]
    repetition = count / window
    # 目标关键词在最近工具参数里是否还出现
    goal_kw = keywords(anchor.goal)
    recent_text = ' '.join(recent).lower()
    goal_hit = sum(1 for w in goal_kw if w.lower() in recent_text) / max(1, len(goal_kw))
    detected = repetition >= 0.6 and goal_hit < 0.15
    return {'detected': detected, 'step': len(tool_sequence),
            'dominant_tool': most, 'repetition': round(repetition, 3),
            'goal_keyword_hit': round(goal_hit, 3),
            'reason': 'pattern-loop-off-goal' if detected else 'ok'}
