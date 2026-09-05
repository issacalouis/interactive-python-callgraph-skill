#!/usr/bin/env python3
"""Build an interactive, source-faithful Python function call graph."""

from __future__ import annotations

import argparse
import ast
import html
import json
from pathlib import Path


VIS_NETWORK = "https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"


def read_source(path: Path) -> str:
    if path.suffix.lower() != ".ipynb":
        return path.read_text(encoding="utf-8")
    notebook = json.loads(path.read_text(encoding="utf-8"))
    return "\n\n".join(
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    )


def collect_functions(source: str) -> tuple[dict[str, str], set[tuple[str, str]]]:
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    edges: set[tuple[str, str]] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id in functions:
                edges.add((child.func.id, node.name))
    return functions, edges


def dependency_scope(functions: dict[str, str], edges: set[tuple[str, str]], roots: list[str]) -> set[str]:
    if not roots:
        return set(functions)
    missing = set(roots) - set(functions)
    if missing:
        raise ValueError(f"Functions not found: {', '.join(sorted(missing))}")
    dependencies: dict[str, set[str]] = {name: set() for name in functions}
    for callee, caller in edges:
        dependencies[caller].add(callee)
    selected, pending = set(), list(roots)
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        selected.add(name)
        pending.extend(dependencies[name] - selected)
    return selected


def depth_map(names: set[str], edges: set[tuple[str, str]]) -> dict[str, int]:
    incoming = {name: set() for name in names}
    for callee, caller in edges:
        if callee in names and caller in names:
            incoming[caller].add(callee)
    memo: dict[str, int] = {}

    def depth(name: str, active: set[str]) -> int:
        if name in memo:
            return memo[name]
        if name in active:
            return 0
        memo[name] = 0 if not incoming[name] else 1 + max(depth(x, active | {name}) for x in incoming[name])
        return memo[name]

    return {name: depth(name, set()) for name in names}


def build_html(source_path: Path, functions: dict[str, str], edges: set[tuple[str, str]], selected: set[str]) -> str:
    shown = {name: functions[name] for name in sorted(selected)}
    shown_edges = sorted([edge for edge in edges if edge[0] in selected and edge[1] in selected])
    depths = depth_map(selected, set(shown_edges))
    payload = json.dumps(shown, ensure_ascii=False).replace("</", "<\\/")
    node_data = json.dumps([{"id": n, "label": n, "level": depths[n], "group": min(depths[n], 5)} for n in shown], ensure_ascii=False)
    edge_data = json.dumps([{"from": a, "to": b} for a, b in shown_edges], ensure_ascii=False)
    title = html.escape(f"{source_path.name} 函数源码调用图")
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<script src="{VIS_NETWORK}"></script><style>
:root{{--ink:#172033;--muted:#667085;--line:#dce3ee;--blue:#2558d8;--navy:#101828;--panel:#fff;--canvas:#f4f7fb}}*{{box-sizing:border-box}}html,body{{margin:0;width:100%;height:100%;overflow:hidden}}body{{font:14px/1.45 Arial,"Microsoft YaHei",sans-serif;background:var(--canvas);color:var(--ink)}}button,input{{font:inherit}}header{{height:72px;padding:0 22px;display:flex;align-items:center;gap:20px;background:linear-gradient(115deg,#102447,#183f78);color:#fff;box-shadow:0 2px 14px #10244730;position:relative;z-index:3}}h1{{font-size:18px;margin:0;white-space:nowrap}}.subtitle{{color:#d7e4f8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}#stats{{margin-left:auto;padding:6px 10px;border:1px solid #ffffff30;border-radius:999px;background:#ffffff12;white-space:nowrap;font-size:12px}}#app{{display:grid;grid-template-columns:minmax(360px,1fr) 0;height:calc(100% - 72px);transition:grid-template-columns .22s ease}}#app.open{{grid-template-columns:minmax(360px,1fr) min(46vw,680px)}}main{{position:relative;min-width:0;border-right:1px solid var(--line)}}#network{{position:absolute;inset:0;background:radial-gradient(circle at 30% 25%,#fff 0,#f7f9fd 45%,#edf2f8 100%)}}#tools{{position:absolute;z-index:2;top:14px;left:14px;display:flex;gap:8px;align-items:center;padding:8px;border:1px solid var(--line);border-radius:12px;background:#fffffff2;box-shadow:0 7px 25px #18243b18;backdrop-filter:blur(8px)}}#search{{width:220px;padding:8px 11px;border:1px solid #cbd5e1;border-radius:8px;outline:none}}#search:focus{{border-color:#5d83e8;box-shadow:0 0 0 3px #5d83e820}}.tool,.action{{padding:8px 11px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;color:#344054;cursor:pointer;white-space:nowrap}}.tool:hover,.action:hover{{border-color:#7595df;background:#f5f8ff;color:#1746b0}}#hint{{position:absolute;left:18px;bottom:16px;z-index:2;color:#667085;font-size:12px;padding:7px 10px;border-radius:8px;background:#ffffffdc;border:1px solid #e4e9f1}}#view{{min-width:0;background:var(--panel);display:flex;flex-direction:column;overflow:hidden}}#empty{{height:100%;display:grid;place-content:center;text-align:center;padding:34px;color:var(--muted)}}#empty strong{{font-size:16px;color:#344054;margin-bottom:8px}}#content{{display:none;height:100%;min-height:0;flex-direction:column}}#view.active #empty{{display:none}}#view.active #content{{display:flex}}#bar{{padding:15px 16px 12px;border-bottom:1px solid var(--line);background:#fbfcfe}}#barTop{{display:flex;align-items:center;gap:8px}}#name{{font:700 16px Consolas,monospace;color:#173e7e;overflow:hidden;text-overflow:ellipsis}}#pinState{{padding:3px 7px;border-radius:999px;background:#eef2f7;color:#667085;font-size:11px}}#bar .spacer{{flex:1}}.action{{padding:6px 9px;font-size:12px}}#close{{font-size:17px;line-height:1;padding:6px 9px}}#relations{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:11px}}.relationTitle{{display:block;color:#667085;font-size:11px;margin-bottom:5px}}.chips{{display:flex;flex-wrap:wrap;gap:5px;min-height:24px}}.chip{{max-width:100%;padding:3px 7px;border:0;border-radius:6px;background:#edf3ff;color:#2753b5;font:11px Consolas,monospace;cursor:pointer;overflow:hidden;text-overflow:ellipsis}}.chip:hover{{background:#dce8ff}}.none{{font-size:12px;color:#98a2b3}}pre{{margin:0;padding:18px;overflow:auto;min-height:0;flex:1;background:#101827;color:#dce8f7;font:13px/1.58 Consolas,"Courier New",monospace;white-space:pre;tab-size:4}}@media(max-width:900px){{header{{height:64px;padding:0 14px}}.subtitle{{display:none}}#app,#app.open{{height:calc(100% - 64px);grid-template-columns:1fr;grid-template-rows:minmax(280px,1fr) 0}}#app.open{{grid-template-rows:minmax(260px,56%) minmax(220px,44%)}}main{{border-right:0;border-bottom:1px solid var(--line)}}#tools{{right:10px;left:10px;flex-wrap:wrap}}#search{{flex:1;min-width:145px}}#hint{{display:none}}#relations{{grid-template-columns:1fr}}}}
/* Restrained scientific palette; stable click-only source inspection. */
header{{height:60px;background:#fff;color:#263746;box-shadow:none;border-bottom:1px solid #dce2e6}}
h1{{font-size:16px;font-weight:600}}.subtitle{{color:#7c8790;font-size:12px}}#stats{{background:#f1f4f5;border-color:#e0e5e8;color:#657481}}
#app{{height:calc(100% - 60px);transition:none}}#app.open{{grid-template-columns:minmax(360px,1fr) min(40vw,620px)}}
#network{{background:#fafbfc}}#tools{{border-radius:5px;box-shadow:0 2px 8px #24374609;backdrop-filter:none;top:16px;left:16px}}.tool,.action,#search{{border-radius:4px}}#search{{width:185px}}#hint{{border:0;background:#fafbfce8;color:#84909a}}
#bar{{background:#f5f7f8}}#barTop{{flex-wrap:wrap}}#name{{font-size:14px;color:#3d6075;overflow-wrap:anywhere;white-space:normal}}#relations{{grid-template-columns:1fr;max-height:145px;overflow:auto}}.chip{{background:#e8eef2;color:#42637a;border-radius:3px}}pre{{background:#fff;color:#293d4c;font-size:13px;line-height:1.75;border-top:1px solid #e2e7ea}}#view{{border-left:1px solid #dce2e6}}
@media(max-width:900px){{#app,#app.open{{height:calc(100% - 60px);grid-template-columns:1fr}}}}
</style></head><body><header><h1>{title}</h1><span class="subtitle">函数节点与真实源码联动审查</span><span id="stats">{len(shown)} 个函数 · {len(shown_edges)} 条调用</span></header>
<div id="app" class="open"><main><div id="network"></div><div id="tools"><input id="search" placeholder="搜索函数名…" autocomplete="off"><button class="tool" id="fit">适应全图</button><button class="tool" id="direction">纵向布局</button></div><div id="hint">箭头：被调用函数 → 调用者　·　单击查看源码 · 拖动画布 · 滚轮缩放</div></main><aside id="view"><div id="empty"><strong>选择一个函数</strong><span>单击左侧函数查看真实源码。\n审查栏始终保留，拖动与缩放不会打断阅读。</span></div><div id="content"><div id="bar"><div id="barTop"><b id="name"></b><span class="spacer"></span><button class="action" id="copy">复制源码</button><button class="action" id="close" title="清空选择（Esc）">×</button></div><div id="relations"><div><span class="relationTitle">调用了</span><div class="chips" id="calls"></div></div><div><span class="relationTitle">被这些函数调用</span><div class="chips" id="callers"></div></div></div></div><pre id="code"></pre></div></aside></div>
<script>
const sources={payload},nodeData={node_data},edgeData={edge_data};
const nodes=new vis.DataSet(nodeData),edges=new vis.DataSet(edgeData),app=document.getElementById('app'),view=document.getElementById('view'),code=document.getElementById('code'),nameEl=document.getElementById('name');
const links={{}};Object.keys(sources).forEach(n=>links[n]={{calls:[],callers:[]}});edgeData.forEach(e=>{{links[e.to].calls.push(e.from);links[e.from].callers.push(e.to)}});Object.values(links).forEach(x=>{{x.calls.sort();x.callers.sort()}});
let direction='LR',current=null;
const options={{layout:{{hierarchical:{{enabled:true,direction,sortMethod:'directed',levelSeparation:235,nodeSpacing:105,treeSpacing:160}}}},physics:false,interaction:{{hover:true,hoverConnectedEdges:true,navigationButtons:true,keyboard:true,multiselect:false}},nodes:{{shape:'box',margin:12,font:{{face:'Consolas',size:13,color:'#24324a'}},borderWidth:1.5,chosen:{{node:true,label:true}},shadow:false}},edges:{{arrows:{{to:{{enabled:true,scaleFactor:.7}}}},color:{{color:'#94a3b8',highlight:'#2457d6',hover:'#4f75cf'}},width:1.4,selectionWidth:2,smooth:{{type:'cubicBezier',forceDirection:'horizontal',roundness:.42}}}},groups:{{0:{{color:{{background:'#E5EEF3',border:'#4C7895'}}}},1:{{color:{{background:'#E3EEEA',border:'#528779'}}}},2:{{color:{{background:'#F3ECDD',border:'#B39859'}}}},3:{{color:{{background:'#ECE8F0',border:'#8A7B9B'}}}},4:{{color:{{background:'#F2E6E1',border:'#B47C68'}}}},5:{{color:{{background:'#E5E9ED',border:'#697E90'}}}}}}}};
const network=new vis.Network(document.getElementById('network'),{{nodes,edges}},options);
function renderLinks(target,names){{target.replaceChildren();if(!names.length){{const span=document.createElement('span');span.className='none';span.textContent='无';target.append(span);return}}names.forEach(id=>{{const b=document.createElement('button');b.className='chip';b.textContent=id;b.title=id;b.onclick=()=>show(id);target.append(b)}})}}
function show(id){{current=id;nameEl.textContent=id;code.textContent=sources[id];renderLinks(document.getElementById('calls'),links[id].calls);renderLinks(document.getElementById('callers'),links[id].callers);app.classList.add('open');view.classList.add('active');network.selectNodes([id],true)}}
function closePreview(){{current=null;view.classList.remove('active');network.unselectAll()}}
network.on('click',p=>{{if(p.nodes.length)show(p.nodes[0])}});
document.getElementById('close').onclick=closePreview;
document.getElementById('copy').onclick=async e=>{{if(!current)return;const button=e.currentTarget;try{{await navigator.clipboard.writeText(sources[current]);button.textContent='已复制'}}catch{{button.textContent='请选中代码复制'}}setTimeout(()=>button.textContent='复制源码',1400)}};
document.addEventListener('keydown',e=>{{if(e.key==='Escape')closePreview()}});
document.getElementById('fit').onclick=()=>network.fit({{animation:{{duration:350,easingFunction:'easeInOutQuad'}}}});document.getElementById('direction').onclick=e=>{{direction=direction==='LR'?'UD':'LR';network.setOptions({{layout:{{hierarchical:{{direction}}}},edges:{{smooth:{{forceDirection:direction==='LR'?'horizontal':'vertical'}}}}}});e.currentTarget.textContent=direction==='LR'?'纵向布局':'横向布局';setTimeout(()=>network.fit({{animation:true}}),80)}};
document.getElementById('search').oninput=e=>{{const q=e.target.value.trim().toLowerCase(),found=Object.keys(sources).filter(x=>x.toLowerCase().includes(q));network.selectNodes(q?found:[]);if(q&&found.length){{network.focus(found[0],{{scale:1.15,animation:true}})}}else if(!q)closePreview(true)}};network.once('afterDrawing',()=>network.fit());
</script></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--roots", nargs="*", default=[])
    args = parser.parse_args()
    source = read_source(args.source)
    functions, edges = collect_functions(source)
    selected = dependency_scope(functions, edges, args.roots)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_html(args.source, functions, edges, selected), encoding="utf-8")
    print(f"Wrote {args.output} with {len(selected)} functions and {sum(a in selected and b in selected for a, b in edges)} edges")


if __name__ == "__main__":
    main()
