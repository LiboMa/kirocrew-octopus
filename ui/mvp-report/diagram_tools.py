"""Small, deterministic SVG primitives for the offline MVP explainer."""
from html import escape

PALETTE = {
    "blue": ("#edf4ff", "#185adb"),
    "green": ("#eaf8f1", "#117d58"),
    "amber": ("#fff4df", "#9d6100"),
    "red": ("#fff0f2", "#bc304b"),
    "purple": ("#f2edff", "#7052b7"),
    "gray": ("#f2f5fa", "#516581"),
    "teal": ("#e7f8fa", "#007a88"),
}


def text(x, y, lines, size=17, color="#18304f", anchor="middle", weight=500):
    if isinstance(lines, str):
        lines = lines.split("\n")
    return "".join(
        f'<text x="{x}" y="{y+i*(size+8)}" text-anchor="{anchor}" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}">{escape(line)}</text>'
        for i, line in enumerate(lines)
    )


def box(x, y, w, h, title, sub="", tone="blue", key=None):
    fill, color = PALETTE[tone]
    attr = f' data-node="{escape(key)}"' if key else ""
    result = f'<g{attr}><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{color}" stroke-opacity=".36"/>'
    result += f'<path d="M{x+1} {y+20}v{max(8,h-40)}" stroke="{color}" stroke-width="3"/>'
    result += text(x+w/2, y+29, title, 18, color, weight=650)
    if sub:
        result += text(x+w/2, y+55, sub, 14, "#516581")
    return result+"</g>"


def line(x1, y1, x2, y2, label="", dashed=False, color="#748aad", bend=None):
    path = f"M{x1} {y1}L{x2} {y2}" if bend is None else f"M{x1} {y1}L{bend} {y1}L{bend} {y2}L{x2} {y2}"
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    result = f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2"{dash} marker-end="url(#arrow)"/>'
    if label:
        result += text((x1+x2)/2, (y1+y2)/2-9, label, 13, "#516581")
    return result


def canvas(name, width, height, body, desc):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{escape(name)}" style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,PingFang SC,Microsoft YaHei,sans-serif">'
        f'<title>{escape(name)}</title><desc>{escape(desc)}</desc>'
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#748aad"/></marker></defs>'
        f'<rect width="{width}" height="{height}" fill="white"/>{body}</svg>'
    )


def flow(name, rows, notes=""):
    """Each row contains (title, subtitle, tone); edges follow rows."""
    width = 1100
    max_cols = max(len(row) for row in rows)
    gap, pad = 24, 30
    cell = (width - pad*2 - (max_cols-1)*gap) / max_cols
    result = ""
    coords = []
    for r, row in enumerate(rows):
        offset = (width - (len(row)*cell+(len(row)-1)*gap))/2
        coords.append([])
        for c, (title, sub, tone) in enumerate(row):
            x, y = offset+c*(cell+gap), 32+r*150
            coords[-1].append((x,y,cell,98))
            result += box(x,y,cell,98,title,sub,tone)
            if c:
                result += line(x-gap,y+49,x,y+49)
        if r:
            old = coords[r-1][-1]
            new = coords[r][0]
            result += f'<path d="M{old[0]+old[2]/2} {old[1]+old[3]}V{y-23}H{new[0]+new[2]/2}V{y}" fill="none" stroke="#748aad" stroke-width="2" marker-end="url(#arrow)"/>'
    height = 32+len(rows)*150
    if notes:
        result += text(30,height-12,notes,15,"#516581","start")
    return canvas(name,width,height,result,notes)


def sequence(name, actors, events, notes=""):
    width = max(1100,len(actors)*170)
    left, right = 95,width-95
    positions = [left+(right-left)*i/(len(actors)-1) for i in range(len(actors))]
    bottom = 120+len(events)*74
    result = ""
    for i, actor in enumerate(actors):
        x = positions[i]
        result += box(x-78,18,156,66,actor,"","blue")
        result += f'<path d="M{x} 86V{bottom}" stroke="#cbd7e8" stroke-dasharray="5 6" stroke-width="1.5"/>'
    for i,event in enumerate(events):
        a,b,label,*rest = event
        tone = rest[0] if rest else "blue"
        color = PALETTE[tone][1]
        y = 132+i*74
        result += f'<g data-event="{i}">'
        result += f'<rect class="event-highlight" x="7" y="{y-37}" width="{width-14}" height="64" rx="8" fill="#edf4ff" opacity="0"/>'
        result += f'<circle cx="20" cy="{y-11}" r="12" fill="#edf4ff"/>'
        result += text(20,y-7,str(i+1),12,"#185adb")
        if a==b:
            x = positions[a]
            direction = -1 if x > width*.62 else 1
            result += f'<path d="M{x} {y-22}h{48*direction}v30h{-48*direction}" fill="none" stroke="{color}" stroke-width="2" marker-end="url(#arrow)"/>'
            result += text(x+59*direction,y-6,label,14,color,"end" if direction < 0 else "start")
        else:
            result += line(positions[a],y,positions[b],y,color=color,dashed=b<a)
            result += text((positions[a]+positions[b])/2,y-14,label,15,color)
        result += "</g>"
    if notes:
        result+=text(30,bottom+28,notes,15,"#516581","start")
    return canvas(name,width,bottom+55,result,notes)


def diagrams():
    output={}
    body=""
    body+=text(35,33,"配置与观察：Octopus 提供",17,"#185adb","start",650)
    for x,t,s,k in [(35,"三种入口","Web · 文件 · Chat","entry"),(395,"定义 / 版本 / 快照","workflow.py / library / files","config"),(755,"任务状态与证据","观察器 · accept · Web 预览","observer")]:
        body+=box(x,55,310,95,t,s,"blue",k)
    body+=line(345,103,395,103)
    body+='<path d="M550 150V172H190V218" fill="none" stroke="#748aad" stroke-width="2" marker-end="url(#arrow)"/>'
    body+=text(555,177,"固定版本与原始需求",13,"#516581","start")
    body+=text(35,199,"执行与生命周期：KiroCrew 原生能力",17,"#117d58","start",650)
    for x,t,s,k in [(35,"原生父 Session","需求 · next · 完成后 accept","parent"),(395,"Gateway / SubagentManager","原生 MCP spawn_run · 权限 · 完成","gateway"),(755,"ProviderRegistry","Octopus 在已有 factory 接口选路","registry")]:
        body+=box(x,218,310,95,t,s,"green",k)
    body+=line(345,267,395,267,"MCP")
    body+=line(705,267,755,267)
    body+=line(910,218,910,150,"路由证据",True)
    body+=line(705,250,755,104,dashed=True,bend=730)
    body+=text(740,204,"原生任务 / 权限",12,"#516581","start")
    body+=line(910,313,910,350)
    body+=box(35,350,1030,73,"原生 AcpProvider / AcpRuntime / AcpClient","能力协商 → 创建或恢复工具 Session → 配置 → Prompt → Update / Permission / Completion","teal","acp")
    tools=[("Kiro CLI","kiro-cli acp","purple"),("Claude Code","claude-agent-acp","amber"),("Codex","codex-acp → App Server","blue"),("OpenCode","原生 OpenCode ACP","teal")]
    for i,(title,sub,tone) in enumerate(tools):
        x=35+i*264
        body+=line(x+119,423,x+119,471)
        body+=box(x,471,238,93,title,sub,tone,title.lower())
    body+=box(35,603,1030,78,"每个工具使用自己的模型服务认证、工具配置和原生 Session","同一 Run 工作区交接文件；不把四个工具拼成同一个模型上下文窗口","gray","context")
    for i in range(4):body+=line(154+i*264,564,154+i*264,603,dashed=True)
    output["architecture"]=canvas("MVP 分层架构",1100,710,body,"蓝色为配置和观察，绿色为原生执行；ProviderRegistry 是扩展组合点。")
    output["journey"]=flow("从需求到开发状态",[
        [("目标与需求","模板或用户意图","blue"),("任务与 Agent","先任务，再工具 / Model / Effort","blue"),("确认 / 保存","保存才进入版本库","blue")],
        [("准备 Run","固定 revision 与配置 hash","purple"),("原生 App 父 Session","Web 提交或转 Chat 输入","green"),("开发状态","Tasks · 参数证据 · 产物","teal")],
    ],"收起向导保留浏览器草稿；已有运行始终读取自己的固定版本。")
    body=box(385,20,330,88,"Workflow：可复用定义","例如：从需求到 Web 交付","blue")
    for x,rev in [(120,"r1"),(660,"r2")]:
        body+=line(550,108,x+160,153)
        body+=box(x,153,320,85,f"不可变版本 {rev}","独立 JSON + 配置 SHA-256","purple")
    for x,t,s in [(25,"Run / Session A","固定 r1"),(390,"Run / Session B","固定 r1"),(755,"Run / Session C","固定 r2")]:
        body+=box(x,290,320,84,t,s,"blue")
    body+=line(280,238,185,290);body+=line(280,238,550,290);body+=line(820,238,915,290)
    body+=line(185,374,185,420)
    body+=box(25,420,320,84,"逻辑步骤：code","完整标识：Session A / code","amber")
    body+=line(345,462,390,462)
    body+=box(390,420,320,84,"原生执行 Task ID","首次执行与续作是不同尝试","green")
    body+=line(710,462,755,462)
    body+=box(755,420,320,84,"Crew 子 Session","例如 subagent:conversation-A","green")
    body+=line(915,504,915,550)
    body+=box(755,550,320,86,"工具原生 Session ID","Claude / Codex 等自己的身份","teal")
    body+=text(28,590,["Workflow ID ≠ Run ID ≠ 执行 Task ID ≠ 工具 Session ID","上层关联让它们可追溯；它们不是同一个对象。"],18,"#516581","start")
    output["identity"]=canvas("Workflow、Run、Task、Session 的包含与关联",1100,670,body,"所有 ID 为机制示意，不包含实际会话。")
    output["dispatch"]=sequence("一次完整运行的交互",["用户 / Studio","配置层","父 Session","原生调度","ACP 工具","观察器"],[
        (0,1,"保存 + expected_revision"),(1,0,"返回 rN"),(0,1,"需求 + 开始"),
        (1,2,"slot / context / chat：固定 Run"),
        (2,1,"workflow.py next"),(1,2,"精确 spawn_run 参数"),
        (2,3,"原生 MCP spawn_run"),(3,2,"Task ID：可能仍在排队"),
        (3,4,"factory → ACP Session → Prompt"),
        (4,3,"权限请求 / Update / 结果","amber"),
        (3,2,"原生 completion event","green"),
        (5,3,"读取任务状态、回执、模型"),(5,0,"更新进度与真实证据"),
        (2,1,"accept(task-id)"),(1,2,"核对通过 / 明确失败","green"),
        (2,1,"下一步 next；全部完成则结束"),
    ],"每次 spawn 后父 Agent 结束当前 turn，等待原生完成事件；观察器刷新不是执行循环。")
    output["acp"]=flow("ACP 会话生命周期",[
        [("选 factory","agent 模板 → backend","blue"),("启动 / 连接","原生 Provider 管理工具进程","green"),("initialize","协议与能力协商","teal")],
        [("session/new 或 load","按支持能力创建 / 恢复","teal"),("会话配置","Model / Effort 按后端能力设置","purple"),("session/prompt","传入本步任务","blue")],
        [("原生 Agent 循环","推理 · 工具 · 权限请求","amber"),("状态与完成","session/update 等原生事件","green"),("回到父 Session","结果与交接核对","blue")],
    ],"这是概念顺序；Kiro 与其他后端的实际 Runtime 路径、可用方法和配置能力并不完全相同。")
    output["context"]=flow("Context 如何跨工具传递",[
        [("用户原始需求","input.json / REQUEST.md","blue"),("固定 Workflow","步骤 · 工具 · 参数 · hash","purple"),("本步完整指令","step-instructions.md","blue")],
        [("短分派文本 ≤ 5,000 字符","摘要 + 完整文件路径","amber"),("目标工具读取文件","共享本次 cwd，不共享私有历史","green"),("实际执行","代码 · diff · tests · handoff","teal")],
        [("原生完整返回","step-result.txt","green"),("accept 收据","Task / backend / 参数 / hash","green"),("下一步获得来源","前序 handoff 与结果文件路径","blue")],
    ],"文件传递仍有读取成本与缺失风险；include_memory=false，不把长期 Memory 当成本次任务依赖。")
    output["model"]=flow("Codex Model / Effort 的封装边界",[
        [("工作流配置","model=明确 ID · effort=low","blue"),("公开 spawn_run","model / reasoning_effort 分开","green"),("原生 schema 校验","公开 model 禁止方括号","green")],
        [("Registry 工厂边界","内部 model_override=ID[low]","purple"),("原生 ACP 客户端","拆分 model 与 effort 配置","teal"),("原生观察与核对","请求值 / 实际值 / 未报告","amber")],
    ],"这是当前版本的兼容性桥接，不修改 MCP schema；接受请求不等于模型实际采纳。")
    output["auth"]=sequence("工作台进入原生 KiroCrew 对话",["浏览器","crew-entry","Studio 服务","原生 Gateway"],[
        (0,1,"无凭据入口，只携带 run ID"),
        (1,2,"同源 POST /api/app-entry"),
        (2,2,"校验 Host / Origin / Header / Run"),
        (2,3,"/api/token/local + 本机认证头","amber"),
        (3,2,"原生 Token（仅内存处理）","amber"),
        (2,1,"本次响应中的原生登录地址"),
        (1,3,"导航到固定父 Session"),
        (3,0,"原生 HttpOnly Cookie 与对话","green"),
    ],"Token 不写入本报告、工作流配置、运行快照或工作台 localStorage。")
    body=box(35,30,310,88,"浏览器草稿","localStorage：向导 / 布局","gray")
    body+=box(395,30,310,88,"显式 save","校验 · 唯一名称 · 文件锁","blue")
    body+=box(755,30,310,88,"定义 / 版本库","最新定义 + 不可变版本 JSON","purple")
    body+=line(345,74,395,74);body+=line(705,74,755,74)
    body+=box(395,206,310,94,"Run 固定快照","workflow-run.json + 配置 hash","purple")
    body+=line(910,118,550,206,"prepare：固定选定版本")
    body+=box(35,206,310,94,"工作台管理标记","归档 / 删除，可恢复","gray")
    body+=box(755,206,310,94,"原生 Crew / 工具状态","各自管理 Session 与私有数据","teal")
    body+=line(345,253,395,253,"标记",True)
    body+=line(705,253,755,253,"关联",True)
    body+=box(215,365,670,98,"Run 工作区与观察证据","需求 / 指令 / 代码 / handoff / live / checks / accepted","green")
    body+=line(550,300,550,365)
    body+=line(910,300,810,365,"原生观察",True)
    body+=box(35,526,490,92,"Session 导出","原生 Layer A + 固定配置 + 报告 / 开发文档","blue")
    body+=box(575,526,490,92,"完整备份另行规划","工作目录 / 原生数据库 / 允许保存的工具状态","amber")
    body+=line(360,463,280,526)
    body+=line(910,300,1067,572,dashed=True,bend=1080)
    body+=text(32,657,"定义、Run、管理标记与原生数据分别保存。Session ZIP 不等于完整运行环境备份。",15,"#516581","start")
    output["storage"]=canvas("保存、冻结与运行证据",1100,683,body,"实线表示保存与产物流程，虚线表示管理关联或原生数据来源；归档不替换 Run 或原生 Session。")
    output["generate"]=sequence("用户意图如何生成工作流草稿",["用户 / Web","Library","KiroCrew Chat","Kiro CLI"],[
        (0,1,"意图 + 唯一 request_id"),
        (1,2,"创建独立生成 slot"),
        (1,2,"发送纯文本设计请求"),
        (2,3,"poc-kiro：输出工作流 JSON"),
        (3,2,"结构化文本回复","green"),
        (1,2,"读取完成后的原生回复"),
        (1,1,"parse_document + validate"),
        (1,0,"可编辑草稿；非法输出显示原因"),
        (0,1,"用户采用并显式保存","green"),
    ],"生成对话只设计流程；保存之前是草稿；生成完成不会自动执行开发。")
    output["continue"]=sequence("续作：复用工具会话，但执行 Task ID 改变",["父 Session","原生 Gateway","工具 Session","观察 / accept"],[
        (0,1,"spawn_run：首次 Task A"),(1,2,"创建工具 Session S"),
        (2,1,"结果缺交接 / 空返回","amber"),(3,0,"首次核对未通过","red"),
        (0,1,"spawn_continue：新的 Task B"),(1,2,"按原生 Conversation 复用 S"),
        (2,1,"补齐实际结果与 handoff","green"),(3,1,"读取续作回执与 Conversation"),
        (3,3,"核对 Task B / S 的归属"),
        (3,0,"保留旧记录，接受新尝试","green"),
    ],"复用范围是同一工具的原生会话；不是把 Claude 的 Session 交给 Codex。")
    output["boundaries"]=flow("当前 MVP 的信任边界",[
        [("工作台源","127.0.0.1:8917","blue"),("本机 owner 认证","主机侧访问 Gateway","amber"),("原生 Gateway","5476：会话 / 权限 / 工具","green")],
        [("交付预览源","localhost:8917","gray"),("受限预览路由","路径、文件类型、CSP","gray"),("项目操作限制","指定 cwd · 原生权限","amber")],
    ],"两个主机名形成不同浏览器 Origin；这仍是可信本机 PoC，不是多租户隔离或 Enterprise SSO。")
    output["handoff"]=flow("交接核对的证据链",[
        [("观察快照有效","connected 且 age < 20 秒","blue"),("身份正确","当前步骤 / 父会话 / Task / Agent","blue"),("原生执行结束","非 error / stopped / 空响应","green")],
        [("后端与模型","route + 请求模型 + 实际模型","purple"),("Effort 与续作","请求对应 Task；实际值按报告核对","purple"),("真实交接存在","非 BLOCKED · 非空 handoff","green")],
        [("保存 accepted 收据","结果与 handoff SHA-256","green"),("已交接进度增加","接受数 / 总任务数","teal"),("独立质量责任","仍要核对真实 diff / 测试 / review","amber")],
    ],"当前仅哈希 handoff 文件，未自动绑定全部候选代码与审查结论；已交接不是自动质量认证。")
    return output
