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

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / 'ROADMAP_GRAPH.md'
LADDER = ROOT / 'CAPABILITY_LADDER.yaml'
OUT = ROOT / 'TECH_TREE.html'

CAT_LABEL = {'short': '短期', 'mind': '心智', 'infra': '工程',
             'longterm': '长期', 'governance': '治理', 'autonomy': '自主'}
CAT_COLOR = {'short': '#378ADD', 'mind': '#7F77DD', 'infra': '#1D9E75',
             'longterm': '#BA7517', 'governance': '#A32D2D', 'autonomy': '#0F6E56'}
STATUS_LABEL = {'done': '已完成', 'ready': '可领取', 'backlog': '待办',
                'manual-blocked': '人工阻塞'}


def load():
    m = re.search(r'<!-- ROADMAP_GRAPH_BEGIN v1 -->\s*(.*?)\s*<!-- ROADMAP_GRAPH_END -->',
                  GRAPH.read_text(encoding='utf-8'), re.S)
    if not m:
        raise RuntimeError('GRAPH 权威块缺失')
    g = yaml.safe_load(m.group(1))
    mirror = yaml.safe_load(LADDER.read_text(encoding='utf-8')) if LADDER.exists() else {}
    sem = {i['id']: i for i in mirror.get('items', []) + mirror.get('autonomy_rungs', [])}
    return g, sem


def build(g, sem):
    items = g['items'] + g['rungs']
    anchors = set((g.get('anchors') or {}).keys())
    nodes = []
    for i in items:
        s = sem.get(i['id'], {})
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
            'risk': i.get('risk', ''),
        })
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
.col{display:inline-block;vertical-align:top;width:210px;margin-right:26px}
.col-h{font-size:11px;color:var(--muted);margin-bottom:10px;text-align:center;
 border-bottom:1px dashed var(--line);padding-bottom:6px}
.node{background:var(--panel);border:1px solid var(--line);border-radius:8px;
 padding:9px 10px;margin-bottom:10px;cursor:pointer;position:relative;
 box-shadow:0 1px 2px rgba(0,0,0,.04);transition:transform .1s}
.node:hover{transform:translateY(-1px)}
.node.done{border-left-width:4px}
.node.todo{opacity:.62;border-style:dashed;border-left-width:4px}
.node .id{font:11px ui-monospace,monospace;color:var(--muted)}
.node .t{font-weight:500;margin:2px 0}
.node .meta{font-size:11px;color:var(--muted)}
.chip{display:inline-block;padding:0 5px;border-radius:8px;color:#fff;font-size:10px}
.ok{color:#1D9E75;font-weight:600}
svg.links{position:absolute;top:0;left:0;pointer-events:none;z-index:1}
.node{position:relative;z-index:2}
.node.dim{opacity:.13!important;filter:grayscale(1)}
.node.sel{box-shadow:0 0 0 2px #A32D2D,0 2px 8px rgba(0,0,0,.15);opacity:1!important}
.node.inchain{opacity:1!important}
path.link-dim{opacity:.06!important}
path.link-hot{stroke:#A32D2D!important;stroke-width:2.2!important;opacity:1!important}
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
<div class="wrap"><div id="tree"><svg class="links" id="links"></svg><div id="cols"></div></div>
<aside id="side"><h2>点击节点看详情</h2><div class="sub">依赖链、解锁项、判据状态都在这里。</div></aside></div>
<script>
const DATA=__DATA__;
const CATL=__CATL__,CATC=__CATC__,SL=__SL__;
const $=s=>document.querySelector(s);
function esc(s){return String(s||'').replace(/[<>]/g,'')}
function setMode(m){window.__mode=m;render()}
function highlightHubs(){window.__hub=!window.__hub;render()}
function init(){
 const done=DATA.filter(n=>n.status==='done').length;
 $('#sub').textContent=`${DATA.length} 张卡 · ${done} 已完成 · ${DATA.length-done} 未做 · 从左到右按依赖层级展开`;
 $('#legend').innerHTML=Object.keys(CATL).map(k=>
   `<span><i class="dot" style="background:${CATC[k]}"></i>${CATL[k]}</span>`).join('')+
   `<span><i class="dot" style="border:1px dashed #888"></i>虚线=未完成</span>`;
 render();
}
function render(){
 const mode=window.__mode||'all';
 const ns=DATA.filter(n=>mode==='all'||(mode==='done'?n.status==='done':n.status!=='done'));
 const maxd=Math.max(...ns.map(n=>n.depth));
 // 每层内：未完成靠上、已完成靠下（当前该做的自然浮到视线里）
 const rank=n=>(n.status==='done'?1:0);
 const cols=[];for(let d=0;d<=maxd;d++)cols.push(
   ns.filter(n=>n.depth===d).sort((a,b)=>rank(a)-rank(b)||a.tier-b.tier||a.id.localeCompare(b.id)));
 $('#cols').style.width=((maxd+1)*236)+'px';
 $('#cols').innerHTML=cols.map((col,d)=>{
  const todo=col.filter(n=>n.status!=='done').length,done=col.length-todo;
  return `<div class="col"><div class="col-h">第 ${d} 层 · <span style="color:#A32D2D">${todo} 待办</span> / <span style="color:#1D9E75">${done} 完成</span></div>`+
  col.map(n=>{
   const done=n.status==='done';
   const hubdim=window.__hub && n.id!=='A1' && !n.deps.includes('A1');
   const sel=window.__sel===n.id, inchain=window.__chain && window.__chain.has(n.id);
   const fade=window.__chain && !inchain;
   const cls=['node',done?'done':'todo',sel?'sel':'',inchain?'inchain':'',fade?'dim':''].filter(Boolean).join(' ');
   const c=CATC[n.category]||'#888';
   return `<div class="${cls}" data-id="${esc(n.id)}" style="border-left-color:${c};opacity:${hubdim?'0.25':''}" onclick="show('${esc(n.id)}')">
    <span class="chip" style="background:${c}">${CATL[n.category]||'其他'}</span>
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
 ns.forEach(n=>n.deps.forEach(d=>{
  const a=pos[d],b=pos[n.id];if(!a||!b)return;
  const x1=a.x+a.w,y1=a.y,x2=b.x,y2=b.y;
  const hot=window.__chain && window.__chain.has(d) && window.__chain.has(n.id);
  const fade=window.__chain && !hot;
  const cls=hot?'link-hot':(fade?'link-dim':'');
  paths+=`<path class="${cls}" d="M${x1},${y1} C${x1+18},${y1} ${x2-18},${y2} ${x2},${y2}" fill="none" stroke="#b4b2a9" stroke-width="1"/>`;
 }));
 svg.setAttribute('width',tree.scrollWidth);svg.setAttribute('height',tree.scrollHeight);
 svg.innerHTML=paths;
}
function chainOf(id){
 // 递归上游(deps)+下游(谁依赖它)，返回整条链的 id 集合
 const up=new Set([id]),down=new Set([id]);
 const go=(x,seen,get)=>{get(x).forEach(d=>{if(!seen.has(d)){seen.add(d);go(d,seen,get)}})};
 go(id,up,x=>{const n=DATA.find(y=>y.id===x);return n?n.deps:[]});
 go(id,down,x=>DATA.filter(y=>y.deps.includes(x)).map(y=>y.id));
 return new Set([...up,...down]);
}
function show(id){
 const n=DATA.find(x=>x.id===id);if(!n)return;
 window.__sel=id;window.__chain=chainOf(id);
 render();  // 重绘以应用高亮
 const rev=DATA.filter(x=>x.deps.includes(id)).map(x=>x.id);
 $('#side').innerHTML=`<h2>${esc(n.id)} · ${esc(n.title)}</h2>
 <div class="sub">${CATL[n.category]} · ${SL[n.status]} · tier ${n.tier} · ${esc(n.risk)}</div>
 <div class="field"><b>依赖（前置）</b>${n.deps.map(d=>`<span class="kbd">${esc(d)}</span>`).join(' ')||'无'}</div>
 <div class="field"><b>解锁（下游）</b>${(n.unlocks.length?n.unlocks:rev).map(d=>`<span class="kbd">${esc(d)}</span>`).join(' ')||'无'}</div>
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
    nodes, anchors = build(g, sem)
    nodes = layout(nodes, anchors)
    # 自检：无环、层级合理
    if len({n['id'] for n in nodes}) != len(nodes):
        print('FAIL 节点ID重复'); return 1
    if any(n['depth'] > 30 for n in nodes):
        print('FAIL 依赖层级异常（可能有环）'); return 1
    print(f'OK {len(nodes)} 卡 / {len(anchors)} anchors / 层级 0-{max(n["depth"] for n in nodes)}')
    if check:
        return 0
    payload = json.dumps(nodes, ensure_ascii=False)
    out = (HTML.replace('__DATA__', payload)
               .replace('__CATL__', json.dumps(CAT_LABEL, ensure_ascii=False))
               .replace('__CATC__', json.dumps(CAT_COLOR))
               .replace('__SL__', json.dumps(STATUS_LABEL, ensure_ascii=False)))
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
