# -*- coding: utf-8 -*-
"""docs 报告合并执行器（2026-11-25）。

策略：
- 按 20+ 主题组把 docs/*.md 报告合并成少数专题卷
- 每份原报告降一级标题作为章节，保留全文与日期
- 被外部引用的原文件留 3 行桩（指向合并卷）；无引用直接删除
- 活文档（入口/索引/手册/总纲）与 decisions/lineage/skills/snapshots 不动

用法：python tools/consolidate_docs.py [--dry]
"""
import sys, re, subprocess
from pathlib import Path

ROOT = Path('D:/Brain/publish/dsh-behavior-guard')
DOCS = ROOT / 'docs'

# 不参与合并的活文档
KEEP_LIVE = {
    'README.md', 'MANUALS.md', 'METHODOLOGY.md', 'MANIFEST.md',
    'MD_SYSTEM_PLAN.md', 'USAGE_GUIDE.md', 'BRAIN_PARITY.md',
}

# 合并分组：(卷文件名, 卷标题, 组说明, [成员文件名])
GROUPS = [
    ('PIPELINE_AND_INFRA_BRIDGE_20261120.md', '流水线与基础设施桥接（2026-11-20）',
     '从思考链依赖到落地桥接，再到下一步：IDE 落地机制的完整链条', [
        'FILE_RW_CAPABILITY_PLAN_20261120.md', 'DSH_CUSTOM_TOOL_API_20261122.md',
        'M3_ANCHOR_COST_BENEFIT_20261122.md', 'M3_VALUE_REVIEW_20261122.md',
        'M3_PROTOTYPE_VALIDATION_20261122.md', 'M3_PATTERN_GUARD_LANDING_20261122.md',
        'FIRST_STEP_PREDICTION_EVIDENCE_20261122.md', 'CLOUD_TODO_TRIGGER_MECHANISM_20261122.md',
        'TOOL_SELECTION_MECHANISM_20261122.md', 'TOOL_FAILURE_ANALYSIS_20261122.md',
        'TOOL_SURFACE_ATTENTION_20261122.md', 'TOOL_SURFACE_EVIDENCE_20261122.md',
        'FIRST_PRINCIPLES_GOVERNANCE_20261122.md', 'COMPLEXITY_BUDGET_GOAL_ALIGNED_20261122.md',
        'DECC_ARCHITECTURE_REVIEW_20261122.md', 'OFFICIAL_VS_CUSTOM_AUDIT_20261122.md',
        'HUMAN_VIEW_ENHANCE_20261120.md', 'HUMAN_VIEW_RETIRED_20261121.md',
     ]),
    ('GOAL_STATEMENT_EVOLUTION_20261122.md', '目标陈述演进（2026-11-22）',
     'V2.1→V3→V3.1→最终版，及伴随的落地规划/质量评审/路线重绘', [
        'GOAL_STATEMENT_V2_1_20261122.md', 'GOAL_STATEMENT_V3_20261122.md',
        'GOAL_STATEMENT_V3_1_20261122.md',
        'STRATEGIC_GOAL_QUALITY_20261122.md', 'GOAL_LANDING_PLAN_20261122.md',
        'CARD_DRIVEN_ROADMAP_20261120.md', 'NEXT_STEPS_PRIORITIZATION_20261122.md',
        'ROI_SORT_DECISION_20261120.md', 'ROI_35B_OPINION_20261120.md',
        'ROI_35B_DECISION_PROCESS_REVIEW.md',
     ]),
    ('WALK_EXPERIMENT_SERIES_20261120.md', '「学会自己走路」实验系列（2026-11-20）',
     '基线 + A1/A3.5/M1/M8 五张卡 + 三份反思，完整实验轨迹', [
        'WALK_EXPERIMENT_20261120.md', 'WALK_EXPERIMENT_A1_20261120.md',
        'WALK_EXPERIMENT_A3_5_20261120.md', 'WALK_EXPERIMENT_M1_20261120.md',
        'WALK_EXPERIMENT_M8_20261120.md', 'reflection-A0.md', 'reflection-A1.md',
        'reflection-A1_5.md', 'reflection-A1_6.md', 'reflection-A3_5.md',
        'reflection-M1.md', 'reflection-M8.md', 'reflection-S14.md',
     ]),
    ('AUTONOMY_AND_SELF_HARNESS_20261122.md', '自主化与 Self-Harness 路线（2026-11-20~22）',
     '自主化路线/差距/阶段规划与 Self-Harness P0-P2 实证', [
        'AUTONOMY_GAP_20261120.md', 'WALKING_PLAN_20261120.md', 'SELF_HARNESS_PLAN.md',
        'S1_SELF_HARNESS_P0P1_RESULT.md', 'S4_ADAPTIVE_AB_RESULT.md',
        'S7_SMALL_MODEL_BENCH_RESULT.md', 'SESSION_BRAKE_20261120.md',
        'SINGLE_SESSION_ANTI_POLLUTION_20261121.md', 'M9_REPOSITION_RESEARCH_20261122.md',
        'ROUTE_POSITION_AND_EVOLUTION_20261121.md', 'STRATEGIC_SESSION_ANALYSIS_20261121.md',
     ]),
    ('CITATION_AND_EVIDENCE_GOVERNANCE_20261120.md', '引用与证据治理（2026-11-20~21）',
     '引用审计协议+结果、证据分层标准、闸门证据标准', [
        'CITATION_AUDIT_PROTOCOL_20261120.md', 'CITATION_AUDIT_RESULTS_20261120.md',
        'REAL_TRACE_ACCEPTANCE_20261120.md', 'GATE_EVIDENCE_STANDARD_20261121.md',
     ]),
    ('COMPACTION_CONTEXT_CADENCE_20261120.md', '压缩/上下文/频次治理（2026-11-20~22）',
     '压缩与角色诊断、频次审计与重设计、MECHANISM_TRIGGER_AUDIT', [
        'COMPACTION_AND_ROLES_DIAGNOSIS.md', 'CADENCE_AUDIT.md', 'CADENCE_REDESIGN.md',
        'MECHANISM_TRIGGER_AUDIT_20261120.md',
     ]),
    ('FUTURE_CLAIM_AND_CONSISTENCY_20261120.md', '未来断言与一致性守卫（2026-11-20）',
     'FUTURE_CLAIM_GUARD 设计+分析、一致性设计与裁决、DIAGNOSIS_CORRECTION、GAP_REVIEW', [
        'FUTURE_CLAIM_GUARD_20261120.md', 'FUTURE_CLAIM_GUARD_ANALYSIS_20261120.md',
        'CONSISTENCY_GUARD_DESIGN_20261120.md', 'CONSISTENCY_VERDICT_20261120.md',
        'DIAGNOSIS_CORRECTION_20261120.md', 'GAP_REVIEW_20261120.md',
     ]),
    ('S6_DECISION_WIRE_SERIES_20261122.md', 'S6 决策导线系列（2026-11-22）',
     'S6 模型证据审计→真实测试→延迟根因→下侧评估', [
        'S6_MODEL_EVIDENCE_AUDIT_20261122.md', 'S6_DECISION_WIRE_REAL_TEST_20261122.md',
        'S6_SERVER_LATENCY_ROOTCAUSE_20261122.md', 'S6_DOWNSIDE_ASSESSMENT_20261122.md',
     ]),
    ('S24_VERIFY_LOOP_SERIES_20261122.md', 'S24 验证与读取回路（2026-11-22）',
     '验证/读取回路设计与复测修复', [
        'S24_VERIFY_AND_READ_LOOP_20261122.md', 'S24_RETEST_AND_VERIFY_FIX_20261122.md',
     ]),
    ('SKILLS_AB_SERIES_20261122.md', 'Skills A/B 实验（2026-11-22）',
     '首轮 A/B 与受控复测', [
        'SKILLS_AB_RESULT_20261122.md', 'SKILLS_AB_CONTROLLED_RESULT_20261122.md',
     ]),
    ('CLASSIFIER_BENCH_SERIES_20261121.md', '分类器基准与评测协议（2026-11-21~22）',
     '评测协议、V3/V4 基线、最终基准、生态调研', [
        'CLASSIFIER_EVAL_PROTOCOL_20261121.md', 'CLASSIFIER_BENCH_V3_BASELINE.md',
        'CLASSIFIER_BENCH_FINAL_20261121.md', 'CLASSIFIER_ECOSYSTEM_RESEARCH_20261122.md',
        'CLASSIFIERS_FOR_MIND_MODEL_EVALUATION.md',
     ]),
    ('MIND_MODEL_CAPABILITY_EVAL_20261121.md', '心智模型能力评估（2026-11-21~22）',
     '异构/外设/反馈蒸馏三类评估与科学测量', [
        'HETEROGENEOUS_MODELS_EVALUATION.md', 'PERIPHERAL_MODELS_EVALUATION.md',
        'FEEDBACK_LOOP_AND_DISTILLATION_EVALUATION.md', 'SCIENTIFIC_MEASUREMENT_20261122.md',
        'PERIPHERAL_CAPABILITIES.md', 'PEER_HARNESS_BENCHMARK.md',
     ]),
    ('MIND_GAPS_AND_TRUST_20261122.md', '心智缺口与信任锚（2026-11-20~22）',
     'MIND_GAPS 广搜、六路线调研、信任锚、竞争分析', [
        'MIND_GAPS_RESEARCH.md', 'TRUST_ANCHOR_RESEARCH_20261122.md',
        'COMPETITIVE_ANALYSIS.md',
     ]),
    ('MEMORY_AND_REFACTOR_20261120.md', '记忆蒸馏与重构模式（2026-11-20~21）',
     '三层记忆→心智模型、重构模式、深度维护两版、完成审计', [
        'MEMORY_TO_MIND_MODEL_20261120.md', 'REFACTOR_PATTERN_20261121.md',
        'REFACTOR_ASSESSMENT_20261120.md', 'DEEP_MAINTENANCE_20261119.md',
        'DEEP_MAINTENANCE_20261121.md', 'COMPLETION_AUDIT_20261119.md',
        'BRAIN_AUDIT_20261118.md', 'AUTOCARD_POSTMORTEM_20261122.md',
     ]),
    ('PLATFORM_REPAIR_20261120.md', '平台整治与复盘（2026-11-18~20）',
     'dsh 源码核查、平台层修复、弹窗修复、铁律复盘', [
        'DSH_SOURCE_AUDIT_20261119.md', 'DSH_PLATFORM_REPAIR_20261120.md',
        'POPUP_CONSOLE_FIX_20261119.md', 'POSTMORTEM_20261120.md',
        'FRAME_LIMITER_SLOTS_BUG_20261120.md', 'WORKSPACE_PATH_AUDIT_20261120.md',
        'EDIT_PROTOCOL_S14_20261120.md', 'INCIDENT_EDIT_TRUNCATION_20261120.md',
        'MORNING_REPORT_20261118.md',
     ]),
    ('ROADMAP_EVOLUTION_20261120.md', '路线图演进（2026-11-19~20）',
     '重定基线→重绘→拆分分析→拆分完成', [
        'ROADMAP_REBASELINE_20261119.md', 'ROADMAP_REDRAW_20261120.md',
        'ROADMAP_SPLIT_ANALYSIS_20261120.md', 'ROADMAP_SPLIT_DONE_20261120.md',
     ]),
    ('ENGINE_V1_RESEARCH_20261123.md', 'llama.cpp v1.0 调研与升级（2026-11-23）',
     'v1.0 发布调研→升级部署→性能实测', [
        'LLAMACPP_V1_RESEARCH_20261123.md', 'UPGRADE_V1_DEPLOY_AND_GDN_PATCH_20261123.md',
        'ENGINE_AB_RESULTS_20261123.md', 'IQ4XS_VS_Q4KXL_RESEARCH_20261123.md',
        'HISTORICAL_DATA_VALIDITY_AUDIT_20261123.md',
     ]),
    ('ENGINE_OPT_CORE_20261123.md', '引擎优化核心：卸载/缓存/精度（2026-11-23）',
     'MoE 卸载优化、缓存与精度、混合精度专家质量', [
        'MOE_OFFLOAD_OPTIMIZATION_20261123.md', 'CACHE_AND_MB256_AND_PRECISION_20261123.md',
        'MIXED_PRECISION_EXPERTS_QUALITY_20261123.md',
     ]),
    ('ENGINE_OPT_DEEP_20261123.md', '引擎优化深入：预取/源码/显存（2026-11-23）',
     'Q4_K 预取、源码级优化、显存剖析、mmproj Q8 发现', [
        'Q4K_PREFETCH_AND_QUANT_MODEL_RESEARCH_20261123.md',
        'SOURCE_LEVEL_OPTIMIZATION_FINAL_20261123.md',
        'FIRST_PRINCIPLES_OPERATOR_OPTIMIZATION_20261123.md',
        'ENGINE_BLOAT_AUDIT_AND_MULTIMODAL_VRAM_20261123.md',
        'Q8_MMPROJ_FOUND_20261123.md', 'WHY_7_7G_VRAM_20261123.md',
        'EXPERT_PARALLEL_PATCH_RESULT_20261123.md',
     ]),
    ('ENGINE_OPT_VERIFY_20261124.md', '引擎优化验证与理论极限（2026-11-24）',
     '流水线研究/带宽修正→理论极限→MTP/上下文→FA/DFlash→视觉/缓存', [
        'PIPELINE_RESEARCH_AND_BANDWIDTH_CORRECTION_20261123.md',
        'THEORETICAL_LIMIT_AND_PATH_TO_IT_20261124.md',
        'MEM_GAP_AND_MTP_HEADS_20261124.md', 'ACC_PER_POS_AND_SMALLER_MTP_20261124.md',
        'CTX_VS_MTP_ON_GPU_20261124.md', 'MTP_AND_KV_QUALITY_AB_20261123.md',
        'FA_VERIFY_AND_DFLASH_TEST_20261124.md', 'VISUAL_VS_CACHE_VS_SIDECAR_20261124.md',
     ]),
    ('LEVERS_AND_BROAD_RESEARCH_20261124.md', '杠杆盘点与广搜（2026-11-24）',
     'BFCL 基线→杠杆落地计划→上线清单→广搜（本轮调研入口）', [
        'BFCL_BASELINE_20261124.md', 'LEVERS_LANDING_PLAN_20261124.md',
        'LEVERS_GO_LIVE_20261124.md', 'BROAD_RESEARCH_20261124.md',
     ]),
]

# 高引用活文档：不合并、不删（保留原位）
KEEP_IN_PLACE = {
    'MIND_GAPS_RESEARCH.md', 'COMPETITIVE_ANALYSIS.md',
    'HETEROGENEOUS_MODELS_EVALUATION.md', 'PERIPHERAL_MODELS_EVALUATION.md',
    'FEEDBACK_LOOP_AND_DISTILLATION_EVALUATION.md', 'SELF_HARNESS_PLAN.md',
    'CADENCE_AUDIT.md', 'CADENCE_REDESIGN.md', 'COMPACTION_AND_ROLES_DIAGNOSIS.md',
    'MECHANISM_TRIGGER_AUDIT_20261120.md', 'FUTURE_CLAIM_GUARD_20261120.md',
    'TOOL_SURFACE_EVIDENCE_20261122.md', 'S7_SMALL_MODEL_BENCH_RESULT.md',
    'S1_SELF_HARNESS_P0P1_RESULT.md', 'REAL_TRACE_ACCEPTANCE_20261120.md',
    'POSTMORTEM_20261120.md', 'DEEP_MAINTENANCE_20261121.md',
}


NEW_VOLUMES = {g[0] for g in GROUPS}


def external_refs(name):
    """统计原有文件（排除本次新建合并卷）中按文件名引用它的数量。"""
    n = 0
    for q in ROOT.rglob('*'):
        if not q.is_file() or q.suffix not in ('.md', '.json', '.mjs', '.py', '.ini', '.jinja'):
            continue
        if '.git' in q.parts or 'node_modules' in q.parts:
            continue
        if q.name == name or q.name in NEW_VOLUMES or q.name == 'consolidate_docs.py':
            continue
        try:
            t = q.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        if name in t:
            n += 1
    return n


def demote(text):
    """标题降一级：# → ##，## → ###，避免与卷标题冲突。"""
    out = []
    for line in text.splitlines():
        m = re.match(r'^(#{1,5})(\s+.*)$', line)
        if m:
            out.append('#' + m.group(1) + m.group(2))
        else:
            out.append(line)
    return '\n'.join(out)


def main():
    dry = '--dry' in sys.argv
    all_members = []
    for _, _, _, members in GROUPS:
        all_members.extend(members)

    # 校验：成员存在、不重复、不与 KEEP 冲突
    seen = set()
    missing = []
    for name in all_members:
        if name in seen:
            print(f'⚠ 重复成员: {name}')
        seen.add(name)
        if not (DOCS / name).exists():
            missing.append(name)
        if name in KEEP_LIVE:
            print(f'⚠ 成员是活文档，不应合并: {name}')
    if missing:
        print(f'⚠ 缺失文件 {len(missing)} 个: {missing[:10]}')

    print(f'组数={len(GROUPS)} 成员总数={len(all_members)} 缺失={len(missing)}')
    # ===== 阶段一：先把所有卷写好（此时原件全部完好） =====
    written = {}  # 卷文件名 -> 本卷实际收录的成员
    for fname, title, desc, members in GROUPS:
        parts = [f'# {title}\n', f'> {desc}\n',
                 f'> 本卷合并 {len(members)} 份原报告（2026-11-25 整理）。\n']
        parts.append('## 本卷目录\n')
        exist = []
        for m in members:
            p = DOCS / m
            if not p.exists():
                continue
            exist.append(m)
            parts.append(f'- `{m}`' + ('（原文件保留为引用桩）' if m in KEEP_IN_PLACE else ''))
        parts.append('')
        for m in exist:
            p = DOCS / m
            text = p.read_text(encoding='utf-8-sig', errors='ignore')
            parts.append('---\n')
            parts.append(f'## 原报告：`{m}`\n')
            parts.append(demote(text))
            parts.append('')
        out = DOCS / fname
        if dry:
            print(f'[DRY] {fname}: {len(exist)} 份, {sum(len(x) for x in parts)} 字符')
        else:
            out.write_text('\n'.join(parts), encoding='utf-8')
            print(f'[写] {fname}: {len(exist)} 份')
        written[fname] = exist

    # ===== 阶段二：全部写完后，再统一删除原件/留桩 =====
    deleted = kept = 0
    if not dry:
        for fname, exist in written.items():
            for m in exist:
                p = DOCS / m
                if not p.exists():
                    continue
                refs = external_refs(m)
                if refs > 0 or m in KEEP_IN_PLACE:
                    stub = (f'# {m}\n\n'
                            f'> 本文已并入 [{fname}](./{fname})（2026-11-25 报告整理）。\n'
                            f'> 完整内容见合并卷；本文件仅作为外部引用兼容桩保留。\n')
                    p.write_text(stub, encoding='utf-8')
                    kept += 1
                else:
                    p.unlink()
                    deleted += 1
    print(f'结果: 删除原件 {deleted}, 留桩 {kept}')


if __name__ == '__main__':
    main()
