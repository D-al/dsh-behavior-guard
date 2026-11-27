# -*- coding: utf-8 -*-
"""一键汇总判优实验：判分正确性 → hard_stop主判据 → tool_calls次指标 → 样本量决策"""
import subprocess, json, sys, os

PY = 'D:/Python/python.exe'
ROOT = r'D:/Brain/publish/dsh-behavior-guard'
RESULT = r'D:/Brain/workspace/bench/_ab_reflection_result.json'
V2 = r'D:/Brain/workspace/bench/_ab_v2_only.json'

def run(args, cwd=ROOT):
    r = subprocess.run([PY] + args, cwd=cwd, capture_output=True, text=True, timeout=120)
    return r.stdout, r.stderr

print('='*70)
print('判优实验一键汇总')
print('='*70)

# 0. 去重 + 导出 v2
out, err = run(['-B', '-c', '''
import json,collections
p=r"D:/Brain/workspace/bench/_ab_reflection_result.json"
r=json.load(open(p,encoding="utf-8"))
seen=set();d=[]
for x in r:
    if x["sid"] in seen:continue
    seen.add(x["sid"]);d.append(x)
json.dump(d,open(p,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
v=[x for x in d if x.get("batch")=="v2"]
json.dump(v,open(r"D:/Brain/workspace/bench/_ab_v2_only.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("去重后",len(d),"v2",len(v),dict(collections.Counter(x["group"] for x in v)))
'''])
print(out.strip() or err.strip()[:200])

# 1. 答案正确性判分
print('\n--- 1. 质量判分（answer_correct）---')
out, err = run(['tools/ab_score_correctness.py'])
print(out[-600:] if len(out)>600 else out.strip())

# 判分改写了 RESULT，重新导出 v2
run(['-B', '-c', '''
import json
r=json.load(open(r"D:/Brain/workspace/bench/_ab_reflection_result.json",encoding="utf-8"))
v=[x for x in r if x.get("batch")=="v2"]
json.dump(v,open(r"D:/Brain/workspace/bench/_ab_v2_only.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
'''])

# 2. hard_stop 主判据
print('\n--- 2. hard_stop 主判据 ---')
out, err = run(['tools/ab_hardstop_verdict.py', V2])
print(out.strip())

# 3. tool_calls 次指标
print('\n--- 3. tool_calls 次指标（全部检验）---')
out, err = run(['tools/ab_significance.py', V2])
# 只打关键行
for l in out.splitlines():
    if any(k in l for k in ('###', '主指标均值', '主检验=', '判定:', '样本复核')):
        print(' ', l.strip())

# 4. 样本量决策
print('\n--- 4. 样本量决策 ---')
out, err = run(['tools/ab_sample_decider.py'])
print(out.strip())

print('\n' + '='*70)
print('产物: _ab_hardstop_verdict.json / _ab_significance_result.json / _ab_reflection_result.json')
