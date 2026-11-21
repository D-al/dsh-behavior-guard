#!/usr/bin/env python3
"""科技树视图生成器（2026-11-21）。

读 ROADMAP_GRAPH.md（权威状态）+ CAPABILITY_LADDER.yaml（语义），
生成自包含交互式 HTML：依赖分层 + category 分色 + done/未做一目了然。

用法:
  python tools/tech_tree.py            # 生成 TECH_TREE.html
  python tools/tech_tree.py --check    # 只校验数据，不写文件
"""
import json
import re
import sys
import html
import subprocess
from collections import defaultdict
from pathlib import Path

import os
try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    alt = Path('D:/Python/python.exe')
    if alt.exists() and Path(sys.executable).resolve() != alt.resolve():
        os.execv(str(alt), [str(alt), str(Path(__file__).resolve())] + sys.argv[1:])
    raise

sys.path.insert(0, str(Path(__file__).resolve().parent))
from roadmap_check import roi_score  # 复用同一ROI公式，避免两处漂移

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / 'ROADMAP_GRAPH.md'
LADDER = ROOT / 'CAPABILITY_LADDER.yaml'
OUT = ROOT / 'TECH_TREE.html'

# 依赖层的语义标题（基于各层卡片构成的实证分析，2026-11-21）
LAYER_MEANING = {
    0: '地基与起点 · 无前置',
    1: '工程改造 · 低风险主力',
    2: '结构与校准 · 中风险',
    3: '高阶组合 · 人工决策',
    4: '自主化终局',
}
CAT_LABEL = {'short': '短期', 'mind': '心智', 'infra': '工程',
             'longterm': '长期', 'governance': '治理', 'autonomy': '自主',
             'evidence': '证据', 'rejected': '不做', 'gate': '闸门'}
CAT_COLOR = {'short': '#378ADD', 'mind': '#7F77DD', 'infra': '#1D9E75',
             'longterm': '#BA7517', 'governance': '#A32D2D', 'autonomy': '#0F6E56',
             'evidence': '#185FA5', 'rejected': '#A32D2D', 'gate': '#BA7517'}
STATUS_LABEL = {'done': '已完成', 'ready': '可领取', 'backlog': '待办',
                'manual-blocked': '人工阻塞'}


def load_rejected():
    """从 ROADMAP.md §4 解析"明确不做"表格 → 红色科技卡节点。"""
    md = (ROOT / 'ROADMAP.md').read_text(encoding='utf-8')
    m = re.search(r'## 4\. 明确不做.*?\n(.*?)(?:\n## |\n---)', md, re.S)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 2 or cells[0] in ('不做', '') or set(cells[0]) <= set('-: '):
            continue
        title = re.sub(r'\*\*', '', cells[0])
        reason = re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', cells[1])  # 链接→文字
        out.append({'id': 'X' + str(len(out) + 1), 'title': title, 'reason': reason[:200]})
    return out


def load():
    m = re.search(r'<!-- ROADMAP_GRAPH_BEGIN v1 -->\s*(.*?)\s*<!-- ROADMAP_GRAPH_END -->',
                  GRAPH.read_text(encoding='utf-8'), re.S)
    if not m:
        raise RuntimeError('GRAPH 权威块缺失')
    g = yaml.safe_load(m.group(1))
    mirror = yaml.safe_load(LADDER.read_text(encoding='utf-8')) if LADDER.exists() else {}
    sem = {i['id']: i for i in mirror.get('items', []) + mirror.get('autonomy_rungs', [])}
    return g, sem


def build(g, sem, rejected=None):
    items = g['items'] + g['rungs']
    anchors = set((g.get('anchors') or {}).keys())
    gates = {}
    for i in items:
        for pre in (sem.get(i['id'], {}).get('preconditions') or []):
            pid = str(pre).split(':')[0].strip()
            desc = str(pre).split(':', 1)[1].strip() if ':' in str(pre) else ''
            gates.setdefault(pid, {'title': desc or pid, 'cards': []})
            gates[pid]['cards'].append(i['id'])
    nodes = []
    for i in items:
        s = sem.get(i['id'], {})
        preids = [str(x).split(':')[0].strip() for x in (s.get('preconditions') or [])]
        nodes.append({
            'id': i['id'],
            'title': i.get('title', s.get('title', '')),
            'status': i.get('status', 'backlog'),
            'tier': i.get('tier', 0),
            'category': i.get('category', 'infra'),
            'deps': [d for d in (i.get('deps') or [])],
            'what': s.get('what', ''),
            'why': s.get('why', ''),
            'unlocks': s.get('unlocks') or [],
            'risk': i.get('risk', ''), 'kind': 'card',
            'roi': roi_score(s),
            'roi_valid': '已完成' not in str(s.get('benefit', '')),
            'gates': preids,
        })
    # 证据卡：anchors 是"卡也是证据"，被其他卡 deps 引用；画出来才能看清依赖来源
    ANCHOR_TITLE = {'ground': '地基数据/规则', 'S1_data': '8147行trace证据',
                    'GWT_FEP': 'GWT+FEP验证', 'M4_budget': '注入预算证据',
                    'S1_p0p2': 'Self-Harness P0-P2', 'CritBank': '失败经验库',
                    'S6_rule': '注入检测规则'}
    for a in sorted(anchors):
        meta = (g.get('anchors') or {}).get(a, {})
        nodes.append({'id': a, 'title': ANCHOR_TITLE.get(a, a), 'status': 'evidence',
                      'tier': 0, 'category': 'evidence', 'deps': [],
                      'what': meta.get('note', '') or meta.get('artifact', ''),
                      'why': meta.get('verify', '') or '证据节点：其他卡依赖它',
                      'unlocks': [n['id'] for n in nodes if a in n['deps']],
                      'risk': 'evidence', 'kind': 'evidence'})
    # 前置闸门卡：卡在"条件未验证"上，橙色；跨卡共享 P-ID 只画一个
    for pid, meta in sorted(gates.items()):
        nodes.append({'id': pid, 'title': meta['title'][:34], 'status': 'gate',
                      'tier': 0, 'category': 'gate', 'deps': [],
                      'what': '前置条件：' + meta['title'],
                      'why': '闸门未满足则依赖它的卡 blocked。相关卡：' + ', '.join(meta['cards']),
                      'unlocks': meta['cards'], 'risk': 'gate', 'kind': 'gate',
                      'roi': 0, 'roi_valid': False, 'gates': []})
    # 明确不做：红色科技卡，独立列（最左）
    for x in (rejected or []):
        nodes.append({'id': x['id'], 'title': x['title'], 'status': 'rejected',
                      'tier': 0, 'category': 'rejected', 'deps': [],
                      'what': x['reason'], 'why': '已证伪/明确不做——不要重造轮子',
                      'unlocks': [], 'risk': 'rejected', 'kind': 'rejected'})
    return nodes, sorted(anchors)


def layout(nodes, anchors):
    """计算依赖层级（从 anchors 出发的最长路径），供分列布局。"""
    ids = {n['id'] for n in nodes}
    depth = {a: 0 for a in anchors}
    deps = {n['id']: n['deps'] for n in nodes}
    for _ in range(30):
        changed = False
        for k, ds in deps.items():
            if all(d in depth for d in ds):
                nd = max((depth[d] for d in ds), default=-1) + 1
                if depth.get(k, -1) < nd:
                    depth[k] = nd
                    changed = True
        if not changed:
            break
    for n in nodes:
        if n.get('kind') in ('rejected', 'gate'):
            n['depth'] = -1          # 独立最左列"已排除"
        elif n.get('kind') == 'evidence':
            n['depth'] = 0           # 证据列（与第0层卡同层但在渲染时分组）
        else:
            n['depth'] = depth.get(n['id'], 0)
    return nodes


HTML = r'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Agent 能力科技树</title>
<style>
:root{--bg:#faf9f7;--panel:#fff;--line:#d3d1c7;--text:#2c2c2a;--muted:#5f5e5a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
 font:13px/1.6 -apple-system,"Segoe UI",sans-serif}
header{padding:18px 24px;border-bottom:1px solid var(--line);background:var(--panel)}
h1{margin:0 0 6px;font-size:18px;font-weight:600}
.sub{color:var(--muted);font-size:12px}
.legend{display:flex;gap:14px;flex-wrap:wrap;margin-top:10px;font-size:12px}
.legend span{display:inline-flex;align-items:center;gap:5px}
.dot{width:10px;height:10px;border-radius:3px;display:inline-block}
.wrap{display:flex;height:calc(100vh - 120px)}
#tree{flex:1;overflow:auto;position:relative;padding:24px}
#cols{position:relative;z-index:2}
.col{display:inline-block;vertical-align:top;width:158px;margin-right:12px}
.col-h{font-size:10px;color:var(--muted);margin-bottom:6px;text-align:center;
 border-bottom:1px dashed var(--line);padding-bottom:6px}
.node{background:var(--panel);border:1px solid var(--line);border-radius:6px;
 padding:5px 6px;margin-bottom:5px;cursor:pointer;position:relative;
 box-shadow:0 1px 2px rgba(0,0,0,.04);transition:transform .1s}
.node:hover{transform:translateY(-1px)}
.node.done{border-left-width:4px}
.node.todo{opacity:.62;border-style:dashed;border-left-width:4px}
.node .id{font:10px ui-monospace,monospace;color:var(--muted)}
.node .t{font-weight:500;margin:1px 0;font-size:11px;line-height:1.3}
.node .meta{font-size:10px;color:var(--muted)}
.chip{display:inline-block;padding:0 4px;border-radius:8px;color:#fff;font-size:9px}
.roi{float:right;font:10px ui-monospace,monospace;color:#854F0B;background:#FAEEDA;padding:0 4px;border-radius:6px}
.ok{color:#1D9E75;font-weight:600}
svg.links{position:absolute;top:0;left:0;pointer-events:none;z-index:1}
.node{position:relative;z-index:2}
.node.dim{opacity:.13!important;filter:grayscale(1)}
.node.sel{box-shadow:0 0 0 2px #2C2C2A,0 2px 8px rgba(0,0,0,.2);opacity:1!important}
.node.up-node{box-shadow:0 0 0 2px #185FA5;opacity:1!important}
.node.down-node{box-shadow:0 0 0 2px #A32D2D;opacity:1!important}
path.link-dim{opacity:.06!important}
path.link-hot{stroke:#A32D2D!important;stroke-width:2.2!important;opacity:1!important}
path.link-hot.dir-up{stroke:#185FA5!important}
path.link-hot.dir-down{stroke:#A32D2D!important}
path.link-unlock.hot{stroke:#7F77DD!important}
path.link-unlock.hot.dir-up{stroke:#378ADD!important;stroke-dasharray:"4 3"}
path.link-unlock.hot.dir-down{stroke:#D85A30!important;stroke-dasharray:"4 3"}
#side{width:320px;border-left:1px solid var(--line);background:var(--panel);
 padding:18px;overflow:auto}
#side h2{font-size:15px;margin:0 0 8px}
#side .field{margin:10px 0}
#side .field b{font-size:11px;color:var(--muted);display:block}
.kbd{background:#f1efe8;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font:11px monospace}
button{font:inherit;padding:4px 10px;border:1px solid var(--line);background:#fff;border-radius:6px;cursor:pointer}
</style></head><body>
<header>
<h1>Agent 能力科技树</h1>
<div class="sub" id="sub"></div>
<div class="legend" id="legend"></div>
<div style="margin-top:8px"><button onclick="setMode('all')">全部</button>
<button onclick="setMode('todo')">只看未做</button>
<button onclick="setMode('done')">只看已完成</button>
<button onclick="highlightHubs()">高亮枢纽 A1</button></div>
</header>
<div class="wrap"><div id="tree"><svg class="links" id="links"><defs>
<marker id="arrow-dep" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M2 1L8 5L2 9" fill="none" stroke="#b4b2a9" stroke-width="1.5"/></marker>
<marker id="arrow-unlock" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M2 1L8 5L2 9" fill="none" stroke="#7F77DD" stroke-width="1.5"/></marker>
<marker id="arrow-gate" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M2 1L8 5L2 9" fill="none" stroke="#BA7517" stroke-width="1.5"/></marker>
</defs></svg><div id="cols"></div></div>
<aside id="side"><h2>点击节点看详情</h2><div class="sub">依赖链、解锁项、判据状态都在这里。</div></aside></div>
<script>
const DATA=__DATA__;
const CATL=__CATL__,CATC=__CATC__,SL=__SL__,LAYER=__LAYER__;
// 统一边集：每条关系一条线，from=上游(前置)，to=下游(依赖方)。双向遍历都基于它。
const EDGES=(()=>{const m=new Map(),PRI={dep:0,gate:1,unlock:2},add=(f,t,kind)=>{
  if(!DATA.some(n=>n.id===f)||!DATA.some(n=>n.id===t))return;
  const key=f+'>'+t,prev=m.get(key);
  if(!prev||PRI[kind]<PRI[prev.kind])m.set(key,{from:f,to:t,kind})};  // 同一对只留一条，硬关系优先
 DATA.forEach(n=>{
  (n.deps||[]).forEach(d=>add(d,n.id,'dep'));
  (n.gates||[]).forEach(g=>add(g,n.id,'gate'));
  (n.unlocks||[]).forEach(t=>add(n.id,t,'unlock'));
 });return [...m.values()]})();
const $=s=>document.querySelector(s);
function esc(s){return String(s||'').replace(/[<>]/g,'')}
function setMode(m){window.__mode=m;render()}
function highlightHubs(){window.__hub=!window.__hub;render()}
function init(){
 const done=DATA.filter(n=>n.status==='done').length;
 $('#sub').textContent=`${DATA.length} 张卡 · ${done} 已完成 · ${DATA.length-done} 未做 · 从左到右按依赖层级展开`;
 $('#legend').innerHTML=Object.keys(CATL).map(k=>
   `<span><i class="dot" style="background:${CATC[k]}"></i>${CATL[k]}</span>`).join('')+
   `<span><i class="dot" style="border:1px dashed #888"></i>虚线框=未完成</span>`+
 `<span style="color:#185FA5">━ 蓝=上游(它依赖的)</span>`+
 `<span style="color:#A32D2D">━ 红=下游(依赖它的)</span>`+
 `<span style="color:#5F5E5A">━ 灰实线=实际依赖(必须先做)</span>`+
 `<span style="color:#7F77DD">╌ 紫虚线=语义解锁(做了才具备条件)</span>`;
 render();
}
function render(){
 const mode=window.__mode||'all';
 const ns=DATA.filter(n=>mode==='all'||(mode==='done'?n.status==='done':n.status!=='done'));
 const maxd=Math.max(...ns.map(n=>n.depth));
 // 每层内：未完成靠上、已完成靠下（当前该做的自然浮到视线里）
 const rank=n=>(n.status==='done'?1:0);
 // 列定义：已排除(红) | 证据 | 第0..N层
 const specs=[{key:'rejected',head:'⛔ 明确不做'},{key:'gate',head:'⏳ 前置闸门'},{key:'evidence',head:'▤ 证据/地基'}];
 for(let d=0;d<=maxd;d++)specs.push({key:'layer'+d,head:'第'+d+'层·'+(LAYER[d]||'')});
 const cols=specs.map(sp=>{
  let arr;
  if(sp.key==='rejected')arr=ns.filter(n=>n.kind==='rejected');
  else if(sp.key==='gate')arr=ns.filter(n=>n.kind==='gate');
  else if(sp.key==='evidence')arr=ns.filter(n=>n.kind==='evidence');
  else arr=ns.filter(n=>n.kind==='card'&&n.depth===Number(sp.key.slice(5)));
  // 未完成在前；组内按性价比(ROI)降序——最划算的浮到最上面
  return {key:sp.key,head:sp.head,nodes:arr.sort((a,b)=>rank(a)-rank(b)||
    ((b.roi||0)-(a.roi||0))||a.tier-b.tier||a.id.localeCompare(b.id))};
 });
 $('#cols').style.width=((cols.length)*170)+'px';
 $('#cols').innerHTML=cols.map(col=>{
  const todo=col.nodes.filter(n=>n.status!=='done'&&n.kind==='card').length;
  const done=col.nodes.filter(n=>n.status==='done').length;
  const prog=(col.key!=='rejected'&&col.key!=='evidence'&&col.key!=='gate')?` · <span style="color:#A32D2D">${todo} 待办</span> / <span style="color:#1D9E75">${done} 完成</span>`:'';
  return `<div class="col"><div class="col-h">${col.head}${prog}</div>`+
  col.nodes.map(n=>{
   const done=n.status==='done';
   const hubdim=window.__hub && n.id!=='A1' && !n.deps.includes('A1');
   const sel=window.__sel===n.id;
   const isUp=window.__chains && window.__chains.up.has(n.id) && !sel;
   const isDown=window.__chains && window.__chains.down.has(n.id) && !sel;
   const inchain=window.__chain && window.__chain.has(n.id);
   const fade=window.__chain && !inchain;
   const cls=['node',done?'done':'todo',sel?'sel':'',isUp?'up-node':'',isDown?'down-node':'',fade?'dim':''].filter(Boolean).join(' ');
   const c=CATC[n.category]||'#888';
   return `<div class="${cls}" data-id="${esc(n.id)}" style="border-left-color:${c};opacity:${hubdim?'0.25':''}" onclick="show('${esc(n.id)}')">
    <span class="chip" style="background:${c}">${CATL[n.category]||'其他'}</span>
    <span class="roi" title="性价比=收益÷成本">${n.kind==='card'?(n.roi_valid?'ROI '+n.roi:'已兑现'):''}</span>
    ${done?'<span class="ok">✓</span>':''}
    <div class="id">${esc(n.id)} · tier ${n.tier}</div>
    <div class="t">${esc(n.title)}</div>
    <div class="meta">${SL[n.status]||n.status} · ${esc(n.risk)}</div></div>`
  }).join('')+'</div>';}).join('');
 drawLinks(ns);
}
function drawLinks(ns){
 const svg=$('#links'),tree=$('#tree');
 const pos={};document.querySelectorAll('.node').forEach(el=>{
  const r=el.getBoundingClientRect(),p=tree.getBoundingClientRect();
  pos[el.dataset.id]={x:r.left-p.left+tree.scrollLeft,y:r.top-p.top+tree.scrollTop+10,w:r.width};
 });
 let paths='';
 const edge=(from,to,soft,style)=>{
  const a=pos[from],b=pos[to];if(!a||!b)return;
  const x1=a.x+a.w,y1=a.y,x2=b.x,y2=b.y;
  const hot=window.__chain && window.__chain.has(from) && window.__chain.has(to);
  const fade=window.__chain && !hot;
  // 方向分色：to在上游(含选中)→蓝；from在下游(含选中)且to不在上游→红
  let dir='';
  if(hot && window.__chains){
    const toInUp=window.__chains.up.has(to);
    const fromInDown=window.__chains.down.has(from);
    if(toInUp)dir='up';
    else if(fromInDown)dir='down';
  }
  const cls=(hot?'link-hot':'')+(soft?' link-unlock':'')+(dir?' dir-'+dir:'')+(style==='gate'?' link-gate':'');
  const col=style==='gate'?'#BA7517':(soft?'#7F77DD':'#b4b2a9');
  // 箭头让互连方向可见：从上游(from)指向下游(to)
  const midX=(x1+x2)/2;
  paths+=`<path class="${cls}" d="M${x1},${y1} C${x1+18},${y1} ${x2-18},${y2} ${x2},${y2}" fill="none" stroke="${col}" stroke-width="${style==='gate'?'1.5':'1'}" ${soft?'stroke-dasharray="4 3"':''} marker-end="url(#arrow-${style==='gate'?'gate':soft?'unlock':'dep'})"/>`;
 };
 EDGES.forEach(e=>{
  const soft=e.kind!=='dep';
  edge(e.from,e.to,soft,e.kind);   // 一条边只画一次，方向/颜色由 kind 决定
 });
 svg.setAttribute('width',tree.scrollWidth);svg.setAttribute('height',tree.scrollHeight);
 svg.innerHTML=paths;
}
function chainOf(id){
 // 基于统一边集双向递归：上游=所有指向我的边的起点，下游=所有我从它出发的边的终点
 const up=new Set([id]),down=new Set([id]);
 const go=(x,seen,byNode)=>{byNode(x).forEach(d=>{if(!seen.has(d)){seen.add(d);go(d,seen,byNode)}})};
 go(id,up,x=>EDGES.filter(e=>e.to===x).map(e=>e.from));      // 反向：谁指向我(含deps/unlocks/gates)
 go(id,down,x=>EDGES.filter(e=>e.from===x).map(e=>e.to));    // 正向：我指向谁
 return {up,down,all:new Set([...up,...down])};
}
function show(id){
 const n=DATA.find(x=>x.id===id);if(!n)return;
 window.__sel=id;window.__chains=chainOf(id);window.__chain=window.__chains.all;
 render();  // 重绘以应用高亮
 const rev=DATA.filter(x=>x.deps.includes(id)).map(x=>x.id);
 $('#side').innerHTML=`<h2>${esc(n.id)} · ${esc(n.title)}</h2>
 <div class="sub">${CATL[n.category]} · ${SL[n.status]} · tier ${n.tier} · ${esc(n.risk)}</div>
 <div class="field"><b>前置闸门 · 未满足则 blocked（橙虚线）</b>${(n.gates||[]).map(d=>`<span class="kbd" style="background:#FAEEDA">${esc(d)}</span>`).join(' ')||'无'}</div>
 <div class="field"><b>实际依赖 · 必须先完成（灰实线）</b>${n.deps.map(d=>`<span class="kbd">${esc(d)}</span>`).join(' ')||'无'}</div>
 <div class="field"><b>解锁 · 逻辑声明（紫虚线）</b>${(n.unlocks||[]).map(d=>`<span class="kbd">${esc(d)}</span>`).join(' ')||'无'}</div>
 <div class="field"><b>解锁 · 硬依赖反推（灰实线）</b>${rev.filter(d=>!(n.unlocks||[]).includes(d)).map(d=>`<span class="kbd">${esc(d)}</span>`).join(' ')||'无'}</div>
 <div class="field"><b>做什么</b>${esc(n.what)}</div>
 <div class="field"><b>为什么</b>${esc(n.why)}</div>
 <div class="field"><button onclick="clearSel()">清除高亮</button></div>`;
}
function clearSel(){window.__sel=null;window.__chain=null;render();
 $('#side').innerHTML='<h2>点击节点看详情</h2><div class="sub">依赖链、解锁项、判据状态都在这里。</div>';}
$('#tree').addEventListener('click',e=>{if(e.target.id==='tree'||e.target.id==='cols')clearSel()});
init();window.addEventListener('resize',()=>drawLinks(DATA));
</script></body></html>'''


def main():
    check = '--check' in sys.argv
    g, sem = load()
    rejected = load_rejected()
    nodes, anchors = build(g, sem, rejected)
    nodes = layout(nodes, anchors)
    # 自检：无环、层级合理
    if len({n['id'] for n in nodes}) != len(nodes):
        print('FAIL 节点ID重复'); return 1
    if any(n['depth'] > 30 for n in nodes):
        print('FAIL 依赖层级异常（可能有环）'); return 1
    gates = [n for n in nodes if n.get('kind') == 'gate']
    print(f'OK {len(nodes)} 卡 / {len(anchors)} anchors / 层级 0-{max(n["depth"] for n in nodes)}')
    print(f'GATE_COUNT={len(gates)}')
    if check:
        return 0
    payload = json.dumps(nodes, ensure_ascii=False)
    out = (HTML.replace('__DATA__', payload)
               .replace('__CATL__', json.dumps(CAT_LABEL, ensure_ascii=False))
               .replace('__CATC__', json.dumps(CAT_COLOR))
               .replace('__SL__', json.dumps(STATUS_LABEL, ensure_ascii=False))
               .replace('__LAYER__', json.dumps(LAYER_MEANING, ensure_ascii=False)))
    # 可失败性自检：生成后立刻用 node --check 验 JS 语法，防止空白页面（2026-11-21 踩过坑）
    m = re.search(r'<script>(.*?)</script>', out, re.S)
    if not m:
        print('FAIL 生成的 HTML 无 script 块'); return 1
    tmp = ROOT / 'tools' / '_tech_tree_check.js'
    try:
        tmp.write_text(m.group(1), encoding='utf-8')
        r = subprocess.run(['node', '--check', str(tmp)], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            print('FAIL 生成的 JS 语法错误: ' + r.stderr.strip()[:200]); return 1
    finally:
        if tmp.exists(): tmp.unlink()
    OUT.write_text(out, encoding='utf-8')
    print(f'WROTE {OUT.name} ({len(out)} bytes) [JS语法已验]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
