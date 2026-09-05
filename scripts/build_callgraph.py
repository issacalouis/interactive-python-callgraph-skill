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
<script src="{VIS_NETWORK}"></script><style>*{{box-sizing:border-box}}html,body{{margin:0;width:100%;height:100%;overflow:hidden}}body{{font:14px Arial,"Microsoft YaHei";background:#f5f7fb;color:#172033}}header{{height:64px;padding:0 20px;display:flex;align-items:center;gap:18px;background:#132748;color:white}}h1{{font-size:18px;margin:0}}header span{{color:#cdd9ee}}#app{{display:grid;grid-template-columns:205px 1fr;height:calc(100% - 64px)}}aside{{padding:15px;background:#fbfcfe;border-right:1px solid #d7dfeb}}button,input{{width:100%;padding:9px;margin-bottom:8px;border:1px solid #ccd6e5;border-radius:8px;background:white;font:inherit}}button{{cursor:pointer;text-align:left}}aside p{{color:#667085;line-height:1.6}}main{{position:relative;min-width:0}}#network{{position:absolute;inset:0}}#view{{display:none;position:absolute;z-index:10;width:min(800px,calc(100% - 28px));max-height:80%;border:1px solid #82a4d4;border-radius:11px;overflow:hidden;background:#101827;box-shadow:0 20px 55px #18243b55}}#bar{{height:42px;padding:0 11px;display:flex;align-items:center;background:#e9f1ff;color:#173e7e}}#bar b{{font-family:Consolas}}#bar button{{width:auto;margin:0 0 0 7px;padding:4px 8px;font-size:12px}}#copy{{margin-left:auto!important}}pre{{margin:0;padding:15px;overflow:auto;max-height:calc(80vh - 82px);color:#d9e6f6;font:13px/1.58 Consolas,monospace;white-space:pre}}@media(max-width:720px){{#app{{grid-template-columns:1fr}}aside{{display:none}}}}</style></head>
<body><header><h1>{title}</h1><span>箭头：被调用函数 → 调用者；悬停看真实源码，单击固定。</span></header><div id="app"><aside><input id="search" placeholder="搜索函数名"><button id="fit">适应全部函数</button><button id="close">关闭固定源码</button><p>只显示函数节点。展开内容来自生成时的原始源文件。</p></aside><main id="stage"><div id="network"></div><div id="view"><div id="bar"><b id="name"></b><button id="copy">复制源码</button><button id="pin">固定</button></div><pre id="code"></pre></div></main></div>
<script>const sources={payload},nodes=new vis.DataSet({node_data}),edges=new vis.DataSet({edge_data});const network=new vis.Network(document.getElementById('network'),{{nodes,edges}},{{layout:{{hierarchical:{{enabled:true,direction:'LR',sortMethod:'directed',levelSeparation:230,nodeSpacing:105}}}},physics:false,interaction:{{hover:true,hoverConnectedEdges:true,navigationButtons:true,keyboard:true}},nodes:{{shape:'box',margin:11,font:{{face:'Consolas',size:13}},borderWidth:1.5,shadow:true}},edges:{{arrows:{{to:{{enabled:true,scaleFactor:.65}}}},smooth:{{type:'cubicBezier',forceDirection:'horizontal'}}}},groups:{{0:{{color:'#e9f0fb'}},1:{{color:'#e6f6ed'}},2:{{color:'#fff0d7'}},3:{{color:'#f1e7fb'}},4:{{color:'#ffe8e3'}},5:{{color:'#ffd9d2'}}}}}});const view=document.getElementById('view'),code=document.getElementById('code'),nameEl=document.getElementById('name'),pin=document.getElementById('pin');let fixed=null,current=null;function show(id,p){{current=id;nameEl.textContent=id;code.textContent=sources[id];view.style.display='block';const box=document.getElementById('stage').getBoundingClientRect();view.style.left=Math.max(10,Math.min(p.x+16,box.width-view.offsetWidth-10))+'px';view.style.top=Math.max(10,Math.min(p.y+16,box.height-view.offsetHeight-10))+'px';network.selectNodes([id])}}function hide(){{if(fixed)return;view.style.display='none';network.unselectAll()}}network.on('hoverNode',p=>show(p.node,p.pointer.DOM));network.on('blurNode',()=>setTimeout(()=>{{if(!view.matches(':hover'))hide()}},70));network.on('click',p=>{{if(p.nodes.length){{fixed=p.nodes[0];show(fixed,p.pointer.DOM);pin.textContent='已固定'}}else{{fixed=null;hide()}}}});view.onmouseleave=hide;pin.onclick=()=>{{fixed=fixed?null:current;pin.textContent=fixed?'已固定':'固定';if(!fixed)hide()}};document.getElementById('copy').onclick=()=>navigator.clipboard.writeText(sources[current]);document.getElementById('fit').onclick=()=>network.fit({{animation:true}});document.getElementById('close').onclick=()=>{{fixed=null;pin.textContent='固定';hide()}};document.getElementById('search').oninput=e=>{{const q=e.target.value.toLowerCase(),found=Object.keys(sources).filter(x=>x.toLowerCase().includes(q));network.selectNodes(q?found:[]);if(q&&found[0])network.focus(found[0],{{scale:1.2,animation:true}})}};network.once('afterDrawing',()=>network.fit());</script></body></html>'''


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

