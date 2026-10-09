"""Build a standalone, offline report from allowlisted docs and source snapshots.

This builder never reads native sessions, credentials, runtime logs or user data.
"""
from __future__ import annotations

import ast
from collections import OrderedDict
from datetime import datetime
import hashlib
import html
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
UI = ROOT / "ui/mvp-report"
OUT = ROOT / "docs/workflow-mvp-report"
DOCS = [
    "WORKFLOW-MVP.md", "docs/DEVELOPMENT-HANDBOOK.md", "docs/OPERATIONS.md",
    "docs/BASELINE.md", "docs/FEATURES-AND-DECISIONS.md", "docs/RELEASE-NOTES.md",
    "docs/PUBLICATION-VERIFICATION.md", "PLAN.md", "PIPELINE.md", "README.md",
]
SOURCE_REFS = {
    "control_prompt": ("workflow.py", "control_prompt"),
    "registry": ("poc.py", "PocProviderRegistry"),
    "validate": ("workflow.py", "validate"),
    "save": ("workflow.py", "save"),
    "prepare": ("workflow.py", "prepare"),
    "next_step": ("workflow.py", "next_step"),
    "models": ("workflow.py", "validate_model_selection"),
    "accept": ("workflow.py", "_accept"),
    "observer": ("api.py", "ReadOnlyGateway"),
    "auth": ("api.py", "chat_entry_url"),
    "app_entry": ("workflow.py", "app_entry"),
    "parse": ("workflow_files.py", "parse_document"),
    "generate": ("workflow_library.py", "_generate"),
    "lifecycle": ("workflow_library.py", "delete_workflow"),
    "export": ("workflow_library.py", "export_sessions"),
    "archive": ("workflow_library.py", "archive_sessions"),
    "submit": ("workflow.py", "submit"),
    "reload": ("reload_gateway.py", "reload_when_idle"),
    "project": ("workflow.py", "project"),
    "receipts": ("workflow.py", "dispatch_receipts"),
}
ICON_PATHS = {
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "close": '<path d="m6 6 12 12M18 6 6 18"/>',
    "left": '<path d="m15 5-7 7 7 7"/>',
    "right": '<path d="m9 5 7 7-7 7"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    "compass": '<circle cx="12" cy="12" r="9"/><path d="m16 8-2.5 5.5L8 16l2.5-5.5L16 8Z"/>',
    "code": '<path d="m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18"/>',
    "shield": '<path d="M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6l-9-4Z"/><path d="m8 12 3 3 5-6"/>',
    "window": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M2 9h20M6 6.5h.01M10 6.5h.01"/>',
    "layers": '<path d="m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 17l10 5 10-5"/>',
    "bulb": '<path d="M8 17c0-4-3-4-3-8a7 7 0 0 1 14 0c0 4-3 4-3 8M8 18h8M9 22h6M12 8v7"/>',
    "branch": '<circle cx="6" cy="4" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="20" r="2"/><path d="M6 6v12m0-6c9 0 12-2 12-4"/>',
    "lock": '<rect x="5" y="10" width="14" height="12" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v3"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 3"/>',
    "activity": '<path d="M2 12h4l3-8 6 16 3-8h4"/>',
    "play": '<path d="m8 4 12 8-12 8V4Z"/>',
    "route": '<circle cx="5" cy="5" r="3"/><circle cx="19" cy="19" r="3"/><path d="M5 8v8a4 4 0 0 0 4 4h7M8 5h7a4 4 0 0 1 4 4v7m-7-8 3-3-3-3"/>',
    "unlink": '<path d="m9 15 6-6M8 3 3 8m13 13 5-5M5 12l-1 1a5 5 0 0 0 7 7l2-2m-2-12 2-2a5 5 0 0 1 7 7l-1 1M2 2l20 20"/>',
    "sliders": '<path d="M5 3v5m0 4v9M12 3v10m0 4v4M19 3v2m0 4v12M2 8h6m1 9h6m1-12h6"/>',
    "eye": '<path d="M2 12s4-8 10-8 10 8 10 8-4 8-10 8S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    "file": '<path d="M14 2H5v20h14V7l-5-5Zm0 0v6h5M8 12h8M8 16h8"/>',
    "folder": '<path d="M2 5h8l2 3h10v12H2V5Z"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 4 18 4 18 0V5M3 12c0 4 18 4 18 0"/>',
    "key": '<circle cx="7" cy="8" r="5"/><path d="m11 12 10 10m-6-6 3-3m0 6 3-3"/>',
    "power": '<path d="M12 2v10m-6-8a9 9 0 1 0 12 0"/>',
    "package": '<path d="m12 2 10 5v10l-10 5-10-5V7l10-5Zm0 10v10M2 7l10 5 10-5M7 4.5l10 5v4"/>',
    "message": '<path d="M3 3h18v14H9l-6 5V3Z"/><path d="M7 7h10M7 11h7"/>',
    "download": '<path d="M12 2v13m-5-5 5 5 5-5M3 16v6h18v-6"/>',
    "book": '<path d="M12 5C8 1 2 3 2 3v17s6-2 10 1c4-3 10-1 10-1V3s-6-2-10 2v16"/>',
    "present": '<path d="M2 3h20v13H2V3Zm10 13v6m-5 0 5-6 5 6"/>',
    "print": '<path d="M6 8V2h12v6M6 17H2V8h20v9h-4M6 14h12v8H6v-8ZM18 11h.01"/>',
    "check": '<path d="m4 12 5 5L20 5"/>',
    "zoom": '<circle cx="10" cy="10" r="7"/><path d="m16 16 6 6M10 6v8M6 10h8"/>',
}


def icon(name):
    return f'<svg class="icon" aria-hidden="true"><use href="#i-{name}"/></svg>'


def source_snapshots():
    result = {}
    for key,(filename,symbol) in SOURCE_REFS.items():
        raw=(ROOT/filename).read_text()
        tree=ast.parse(raw)
        node=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name==symbol)
        result[key]={"file":filename,"symbol":symbol,"line":node.lineno,
                     "sha256":hashlib.sha256(raw.encode()).hexdigest(),
                     "code":"\n".join(raw.splitlines()[node.lineno-1:node.end_lineno])}
    return result


def inline(value, docs):
    tokens=[]
    def protect(fragment):
        tokens.append(fragment);return f"\x01{len(tokens)-1}\x02"
    value=re.sub(r"`([^`]+)`",lambda m:protect("<code>"+html.escape(m[1])+"</code>"),value)
    def link(m):
        label,target=m[1],m[2]
        if target in docs:
            return protect(f'<button class="text-link" data-doc="{html.escape(target)}">{html.escape(label)}</button>')
        return protect(f'<span title="{html.escape(target)}">{html.escape(label)}</span>')
    value=re.sub(r"\[([^\]]+)\]\(([^)]+)\)",link,value)
    value=html.escape(value)
    value=re.sub(r"\*\*(.+?)\*\*",r"<strong>\1</strong>",value)
    value=re.sub(r"\x01(\d+)\x02",lambda m:tokens[int(m[1])],value)
    return value


def markdown_document(raw, docs, figure):
    lines=raw.splitlines(); out=[]; i=0; diagram_index=0
    diagram_order=["journey","auth","architecture","dispatch"]
    while i<len(lines):
        line=lines[i]
        if not line.strip(): i+=1;continue
        if line.startswith("```"):
            language=line[3:].strip(); i+=1; block=[]
            while i<len(lines) and not lines[i].startswith("```"):block.append(lines[i]);i+=1
            i+=1
            if language=="mermaid":
                out.append(figure(diagram_order[diagram_index]))
                diagram_index+=1
            else:out.append('<pre><code>'+html.escape("\n".join(block))+'</code></pre>')
            continue
        if re.match(r"^#{1,6} ",line):
            level=min(4,len(line.split(" ",1)[0])+1)
            out.append(f"<h{level}>"+inline(line.split(" ",1)[1],docs)+f"</h{level}>");i+=1;continue
        if line.startswith("|") and i+1<len(lines) and re.match(r"^\|[\s:|-]+\|$",lines[i+1]):
            rows=[line];i+=2
            while i<len(lines) and lines[i].startswith("|"):rows.append(lines[i]);i+=1
            out.append('<div class="table-wrap"><table><thead>')
            for idx,row in enumerate(rows):
                if idx==1:out.append("</thead><tbody>")
                tag="th" if idx==0 else "td"
                out.append("<tr>"+"".join(f"<{tag}>"+inline(cell.strip(),docs)+f"</{tag}>" for cell in row.strip("|").split("|"))+"</tr>")
            out.append("</tbody></table></div>" if len(rows)>1 else "</thead></table></div>")
            continue
        if re.match(r"^(?:- |\d+\. )",line):
            ordered=bool(re.match(r"\d+\. ",line)); tag="ol" if ordered else "ul";out.append("<"+tag+">")
            while i<len(lines) and re.match(r"^(?:- |\d+\. )",lines[i]):
                item=re.sub(r"^(?:- |\d+\. )","",lines[i]);i+=1
                while i<len(lines) and lines[i].startswith("  "):item+=" "+lines[i].strip();i+=1
                out.append("<li>"+inline(item,docs)+"</li>")
            out.append("</"+tag+">");continue
        if line.strip()=="---":out.append("<hr>");i+=1;continue
        paragraph=[line];i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r"^(#|```|\||- |\d+\. )",lines[i]):
            paragraph.append(lines[i]);i+=1
        out.append("<p>"+inline(" ".join(paragraph),docs)+"</p>")
    if diagram_index != len(diagram_order):raise ValueError("Source Mermaid diagram mapping needs updating")
    return "\n".join(out)


def main():
    spec=importlib.util.spec_from_file_location("mvp_diagram_tools",UI/"diagram_tools.py")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    graphs=mod.diagrams()
    docs={name:(ROOT/name).read_text() for name in DOCS}
    sources=source_snapshots()
    figure_count={}
    def figure(key):
        svg=graphs[key]
        title=html.unescape(re.search(r"<title>(.*?)</title>",svg)[1])
        desc=html.unescape(re.search(r"<desc>(.*?)</desc>",svg)[1])
        figure_count[key]=figure_count.get(key,0)+1
        # Prefix local SVG IDs so repeated diagrams cannot collide in the document.
        prefix=f"{key}-{figure_count[key]}-"
        embedded=svg.replace('id="arrow"',f'id="{prefix}arrow"').replace("url(#arrow)",f"url(#{prefix}arrow)")
        return (f'<figure class="diagram" data-diagram="{key}"><div class="figure-toolbar"><strong>{html.escape(title)}</strong>'
                f'<div><button data-zoom-diagram="{key}" aria-label="放大：{html.escape(title)}">{icon("zoom")}放大</button>'
                f'<button data-download-diagram="{key}" aria-label="下载：{html.escape(title)}">{icon("download")}SVG</button></div></div>'
                f'<div class="diagram-preview">{embedded}</div><figcaption>{html.escape(desc)}</figcaption></figure>')
    chapters="\n".join((UI/name).read_text() for name in ["chapters-core.html","chapters-runtime.html","chapters-operations.html"])
    chapters=re.sub(r"\{\{diagram:([\w-]+)\}\}",lambda m:figure(m[1]),chapters)
    def source_button(match):
        key,label=match[1],match[2]
        if key not in sources:raise KeyError(key)
        return f'<button class="source-button" data-source="{key}">{icon("code")}{html.escape(label)}</button>'
    chapters=re.sub(r"\{\{source:([\w-]+)\|([^}]+)\}\}",source_button,chapters)
    chapters=chapters.replace("{{original_document}}",markdown_document(docs["WORKFLOW-MVP.md"],docs,figure))
    files=list(dict.fromkeys(DOCS+[item[0] for item in SOURCE_REFS.values()]))
    manifest=[{"path":name,"sha256":hashlib.sha256((ROOT/name).read_bytes()).hexdigest()} for name in files]
    source_table='<div class="table-wrap"><table><thead><tr><th>构建输入</th><th>SHA-256（前 16 位）</th></tr></thead><tbody>'
    for item in manifest:
        path=html.escape(item["path"])
        label=f'<button class="text-link" data-doc="{path}">{path}</button>' if item["path"] in docs else path
        source_table+=f'<tr><td>{label}</td><td><code>{item["sha256"][:16]}</code></td></tr>'
    source_table+="</tbody></table></div>"
    chapters=chapters.replace("{{source_manifest}}",source_table)
    sections=[{"id":m[1],"title":m[2],"group":m[3]} for m in re.finditer(r'<section class="chapter" id="([^"]+)" data-title="([^"]+)" data-group="([^"]+)"',chapters)]
    assert len(sections)==17
    groups=OrderedDict()
    for i,item in enumerate(sections,1):groups.setdefault(item["group"],[]).append((i,item))
    nav=""
    for group,items in groups.items():
        nav+=f'<div class="nav-group"><h3>{html.escape(group)}</h3>'
        for i,item in items:nav+=f'<a href="#{item["id"]}" data-chapter-link="{item["id"]}"><span>{i:02d}</span>{html.escape(item["title"])}</a>'
        nav+="</div>"
    sha=subprocess.run(["git","rev-parse","--short","HEAD"],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    data={"sources":sources,"docs":docs,"diagrams":graphs,"chapters":sections,"source_commit":sha,"manifest":manifest}
    icons="".join(f'<symbol id="i-{key}" viewBox="0 0 24 24">{path}</symbol>' for key,path in ICON_PATHS.items())
    page=(UI/"template.html").read_text()
    replacements={"css":(UI/"report.css").read_text(),"js":(UI/"report.js").read_text(),
                  "icons":icons,"nav":nav,"chapters":chapters,
                  "data":json.dumps(data,ensure_ascii=False,separators=(",",":")).replace("<","\\u003c")}
    # Substitute in one pass, so source text cannot be interpreted as a new token.
    page=re.sub(r"\{\{(css|js|icons|nav|chapters|data)\}\}",lambda m:replacements[m[1]],page)
    if re.search(r"\{\{(?:diagram|source|original_document|source_manifest)",page):
        raise ValueError("Unresolved report marker")
    if "/Users/malibo" in page or "file:///Users/" in page:
        raise ValueError("Personal absolute path entered the shareable report")
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"index.html").write_text(page)
    (OUT/"WORKFLOW-MVP.md").write_text(docs["WORKFLOW-MVP.md"])
    diagram_dir=OUT/"diagrams";diagram_dir.mkdir(exist_ok=True)
    for key,svg in graphs.items():(diagram_dir/(key+".svg")).write_text(svg)
    output_manifest={"report":"Workflow MVP interactive explainer","source_commit":sha,
                     "built_at":datetime.now().astimezone().isoformat(timespec="seconds"),
                     "chapters":len(sections),"standalone_diagrams":len(graphs),
                     "embedded_source_snippets":len(sources),"inputs":manifest,
                     "html_sha256":hashlib.sha256(page.encode()).hexdigest(),
                     "mode":"offline explanatory simulation; no native tasks or sessions"}
    (OUT/"manifest.json").write_text(json.dumps(output_manifest,ensure_ascii=False,indent=2)+"\n")
    archive=ROOT/"kirocrew-workflow-mvp-report.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():z.write(p,"workflow-mvp-report/"+str(p.relative_to(OUT)))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(json.dumps({"html":str(OUT/"index.html"),"bytes":len(page.encode()),
                      "chapters":len(sections),"diagrams":len(graphs),"source_snippets":len(sources),
                      "zip":str(archive)},ensure_ascii=False))


if __name__=="__main__":
    main()
