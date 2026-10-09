(() => {
  "use strict";
  const data = JSON.parse(document.getElementById("report-data").textContent);
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const escape = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const chapters = $$(".chapter");
  let active = chapters.find(c => c.id === location.hash.slice(1))?.id || "overview";
  let presenting = false, toastTimer, currentDiagram, sourceText = "";
  const toast = text => {
    $("#toast").textContent = text; $("#toast").hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => $("#toast").hidden = true, 2600);
  };
  const copy = async text => {
    try {
      if (!navigator.clipboard?.writeText) throw Error("Clipboard unavailable");
      await navigator.clipboard.writeText(text); toast("已复制");
    } catch {
      const area = document.createElement("textarea");
      area.value = text; area.style.cssText = "position:fixed;left:-10000px";
      document.body.append(area); area.select();
      const ok = document.execCommand("copy"); area.remove();
      toast(ok ? "已复制" : "浏览器未允许复制，请在内容区域手动选择。");
    }
  };
  const download = (name, content, type) => {
    const url = URL.createObjectURL(new Blob([content], {type}));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = name; document.body.append(anchor); anchor.click(); anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  };
  function updateNavigation(id) {
    active = id;
    const index = chapters.findIndex(c => c.id === id);
    chapters.forEach(c => c.classList.toggle("current", c.id === id));
    $$("[data-chapter-link]").forEach(a => {
      const current = a.dataset.chapterLink === id;
      a.classList.toggle("active", current);
      if (current) a.setAttribute("aria-current", "location"); else a.removeAttribute("aria-current");
    });
    $("#reader-label").textContent = `${String(index + 1).padStart(2, "0")} / ${chapters.length} · ${chapters[index].dataset.title}`;
    $("#reading-progress").style.width = `${(index + 1) / chapters.length * 100}%`;
    $("#chapter-prev").disabled = index === 0;
    $("#chapter-next").disabled = index === chapters.length - 1;
  }
  function navigate(id, scroll = true) {
    if (!chapters.some(c => c.id === id)) return;
    stopSimulation();
    updateNavigation(id);
    try { history.replaceState(null, "", "#" + id); } catch { location.hash = id; }
    document.body.classList.remove("nav-open"); $("#nav-scrim").hidden = true;
    if (scroll) {
      if (presenting) window.scrollTo({top:0, behavior:"instant"});
      else document.getElementById(id).scrollIntoView({behavior:reduced.matches ? "instant" : "smooth", block:"start"});
    }
  }
  function moveChapter(direction) {
    const index = chapters.findIndex(c => c.id === active);
    navigate(chapters[Math.max(0, Math.min(chapters.length - 1, index + direction))].id);
  }
  $("#chapter-prev").addEventListener("click", () => moveChapter(-1));
  $("#chapter-next").addEventListener("click", () => moveChapter(1));
  document.addEventListener("click", e => {
    const link = e.target.closest('a[href^="#"]');
    if (link && chapters.some(c => "#" + c.id === link.getAttribute("href"))) {
      e.preventDefault(); navigate(link.getAttribute("href").slice(1));
    }
  });
  window.addEventListener("hashchange", () => navigate(location.hash.slice(1)));
  let scrollFrame = false;
  window.addEventListener("scroll", () => {
    if (presenting || scrollFrame) return;
    scrollFrame = true;
    requestAnimationFrame(() => {
      if (presenting) { scrollFrame = false; return; }
      const id = [...chapters].reverse().find(c => c.getBoundingClientRect().top <= 180)?.id || "overview";
      updateNavigation(id); scrollFrame = false;
    });
  }, {passive:true});
  $("#present-toggle").addEventListener("click", () => {
    stopSimulation(); presenting = !presenting;
    document.body.classList.toggle("present", presenting);
    $("#present-toggle").setAttribute("aria-pressed", String(presenting));
    $("#present-toggle span").textContent = presenting ? "连续阅读" : "投屏模式";
    updateNavigation(active);
    if (presenting) window.scrollTo({top:0, behavior:"instant"});
    else document.getElementById(active).scrollIntoView({behavior:"instant"});
  });
  $("#nav-toggle").addEventListener("click", () => {
    const mobile = matchMedia("(max-width:1000px)").matches;
    const cls = mobile ? "nav-open" : "nav-collapsed";
    document.body.classList.toggle(cls);
    const expanded = mobile ? document.body.classList.contains(cls) : !document.body.classList.contains(cls);
    $("#nav-toggle").setAttribute("aria-expanded", String(expanded));
    $("#nav-scrim").hidden = !mobile || !expanded;
  });
  $("#nav-scrim").addEventListener("click", () => {
    document.body.classList.remove("nav-open"); $("#nav-scrim").hidden = true;
    $("#nav-toggle").setAttribute("aria-expanded", "false");
  });
  $("#chapter-search").addEventListener("input", e => {
    const query = e.target.value.trim().toLocaleLowerCase();
    let count = 0;
    $$("[data-chapter-link]").forEach(a => {
      const chapter = document.getElementById(a.dataset.chapterLink);
      const match = !query || chapter.textContent.toLocaleLowerCase().includes(query);
      a.hidden = !match; if (match) count++;
    });
    $$(".nav-group").forEach(g => g.hidden = ![...g.querySelectorAll("a")].some(a => !a.hidden));
    $("#search-count").textContent = query ? `${count} 个匹配章节${count ? "" : "；请换个关键词"}` : `${chapters.length} 个章节 · 可连续阅读`;
  });
  document.addEventListener("keydown", e => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName) || e.target.isContentEditable || $("dialog[open]")) return;
    if (e.key === "/") { e.preventDefault(); $("#chapter-search").focus(); if (matchMedia("(max-width:1000px)").matches) { document.body.classList.add("nav-open"); $("#nav-scrim").hidden = false; } }
    if (presenting && e.key === "ArrowRight") { e.preventDefault(); moveChapter(1); }
    if (presenting && e.key === "ArrowLeft") { e.preventDefault(); moveChapter(-1); }
    if (e.key === "Escape") { document.body.classList.remove("nav-open"); $("#nav-scrim").hidden = true; stopSimulation(); }
  });
  const diagramDialog = $("#diagram-dialog"), sourceDialog = $("#source-dialog");
  function resizeDiagram() {
    const zoom = Number($("#diagram-zoom").value);
    const svg = $("#diagram-viewport svg");
    if (svg) svg.style.width = Math.max(700, diagramDialog.clientWidth - 60) * zoom / 100 + "px";
    $("#zoom-label").textContent = zoom + "%";
  }
  function openDiagram(key) {
    stopSimulation(); currentDiagram = key;
    const svg = data.diagrams[key];
    $("#diagram-title").textContent = new DOMParser().parseFromString(svg, "image/svg+xml").querySelector("title").textContent;
    $("#diagram-viewport").innerHTML = svg;
    $("#diagram-zoom").value = "100"; diagramDialog.showModal(); resizeDiagram();
  }
  $("#diagram-zoom").addEventListener("input", resizeDiagram);
  $("#diagram-download").addEventListener("click", () => download(currentDiagram + ".svg", data.diagrams[currentDiagram], "image/svg+xml;charset=utf-8"));
  function openSource(key, doc = false) {
    stopSimulation();
    const source = doc ? {file:key, code:data.docs[key], line:1, symbol:"完整文档",
      sha256:data.manifest.find(m => m.path === key)?.sha256 || ""} : data.sources[key];
    if (!source) return;
    sourceText = source.code;
    $("#source-title").textContent = `${source.file} · ${source.symbol}`;
    $("#source-provenance").textContent = `构建时工作区快照 · 起始行 ${source.line} · 源文件 SHA-256 ${source.sha256}`;
    $("#source-content").innerHTML = source.code.split("\n").map((line, i) =>
      `<span class="source-line"><span class="line-no" aria-hidden="true">${source.line + i}</span>${escape(line) || " "}</span>`).join("");
    sourceDialog.showModal();
  }
  document.addEventListener("click", e => {
    const zoom = e.target.closest("[data-zoom-diagram]");
    const svgDownload = e.target.closest("[data-download-diagram]");
    const source = e.target.closest("[data-source]");
    const doc = e.target.closest("[data-doc]");
    const close = e.target.closest("[data-close-dialog]");
    const code = e.target.closest(".copy-code");
    if (zoom) openDiagram(zoom.dataset.zoomDiagram);
    if (svgDownload) download(svgDownload.dataset.downloadDiagram + ".svg", data.diagrams[svgDownload.dataset.downloadDiagram], "image/svg+xml;charset=utf-8");
    if (source) openSource(source.dataset.source);
    if (doc) openSource(doc.dataset.doc, true);
    if (close) close.closest("dialog").close();
    if (code) copy(code.closest(".code-box").querySelector("code").textContent);
  });
  [diagramDialog, sourceDialog].forEach(dialog => dialog.addEventListener("click", e => { if (e.target === dialog) { const r = dialog.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close(); } }));
  $("#source-copy").addEventListener("click", () => copy(sourceText));
  $("#download-markdown").addEventListener("click", () => download("WORKFLOW-MVP.md", data.docs["WORKFLOW-MVP.md"], "text/markdown;charset=utf-8"));
  $("#expand-appendix").addEventListener("click", () => $("#original-appendix").open = !$("#original-appendix").open);
  $(".copy-brief").addEventListener("click", () => copy($(".example-brief blockquote").textContent));
  let printState;
  window.addEventListener("beforeprint", () => { stopSimulation(); printState = $("#original-appendix").open; $("#original-appendix").open = true; });
  window.addEventListener("afterprint", () => { $("#original-appendix").open = Boolean(printState); });
  $("#print-report").addEventListener("click", () => window.print());

  const anatomy = {
    wizard:"编辑向导把任务和 Agent 配置放在一起。收起时保留浏览器草稿；只有显式保存才产生服务端版本。",
    session:"Session 操作集中处理本次开发的导出、归档和 ID 复制。归档只改变工作台标记，不删除原生对话或停止任务。",
    status:"进度来自已接受交接的任务数量。原生返回、待核对、失败、断连是不同状态，不能用动画掩盖证据缺失。",
    task:"逻辑 Task 是 Run / step；原生执行 Task ID 标识一次尝试；工具自己的 Session ID 另行显示。"
  };
  $$("[data-anatomy]").forEach(b => b.addEventListener("click", () => $("#anatomy-note").textContent = anatomy[b.dataset.anatomy]));
  const versions = {revision:1, effort:"high", session:null};
  function versionRender(message) {
    $("#version-definition").textContent = `当前已保存 r${versions.revision} · ${versions.effort}`;
    $("#version-next").textContent = versions.session
      ? `Session B 已冻结 r${versions.session.revision} · ${versions.session.effort}；后续保存不改变它。`
      : "尚未创建；将使用已保存版本。";
    $("#version-create").textContent = versions.session ? "重新创建示意 Session B" : "新建示意 Session";
    $("#version-message").textContent = message;
  }
  $("#version-save").addEventListener("click", () => {
    const effort = $("#version-effort").value;
    if (effort === versions.effort) return versionRender("内容没有变化，实际 save 会返回已有版本；Session A 始终保持 r1 / high。");
    versions.effort = effort; versions.revision++;
    versionRender(`已保存 r${versions.revision}。Session A 仍是 r1 / high，${versions.session ? "已经创建的 B 也不变；" : ""}下一次新运行才使用新配置。`);
  });
  $("#version-create").addEventListener("click", () => {
    versions.session = {revision:versions.revision, effort:versions.effort};
    versionRender("新 Session B 从已保存定义取得快照。下拉框里尚未保存的修改不进入运行。");
  });
  $("#version-reset").addEventListener("click", () => { Object.assign(versions, {revision:1, effort:"high", session:null}); $("#version-effort").value = "high"; versionRender("版本示意已重置。没有修改真实配置。"); });

  const steps = [
    ["需求","用户输入需求","工作台接收需求与选择的工作流。此时没有真实子任务，也没有调用任何 Coding 工具。","用户 → Workflow Studio",0,-1],
    ["冻结","保存版本，准备独立 Run","校验 revision 与可用配置，保存完整 workflow-run.json 和 SHA-256。","save → prepare → 固定 rN",0,-1],
    ["父会话","创建 KiroCrew App 父 Session","通过原生 slot / context / chat 接口绑定协调上下文并发送需求。","/api/chat/slots → context → /api/chat?ws=1",0,-1],
    ["参数","父 Agent 取得规划步骤参数","next 生成完整指令文件与短分派文本，只返回精确 spawn 参数。","workflow.py next → agent=poc-kiro",0,-1],
    ["执行","Kiro CLI 开始规划","父 Agent 经原生 MCP 调用 spawn_run，Registry 选 Kiro factory，再由原生 ACP 执行。","spawn_run → Gateway → Registry → Kiro ACP",0,0],
    ["返回","规划工具返回；仍待核对","原生完成事件回到父会话。拿到返回还没有增加已交接进度。","completion event → 待 accept",0,0],
    ["交接","规划交接核对通过","身份、参数、返回与非空 handoff 通过检查，保存第一份 accepted 收据。","accept(plan-task) → 已交接 1 / 4",1,-1],
    ["执行","Claude Code 读取计划并编码","新工具会话读取 REQUEST.md、完整指令和规划交接，共享的是本次工作目录。","spawn_run(agent=poc-claude) → claude-agent-acp",1,1],
    ["返回","编码返回，等待参数与交接核对","即使代码测试通过，也要检查实际 backend / model、原生请求和 handoff。","completion → 实际模型与配置比较",1,1],
    ["执行","编码已交接，Codex 独立审查","接受编码交接后，Codex 读取真实 diff、代码与测试；实际工具权限仍由 KiroCrew 管理。","accept(code-task) → spawn_run(agent=poc-codex)",2,2],
    ["返回","Codex 返回审查结果","审查结果必须说明实际检查范围与测试证据；BLOCKED 不能被包装成完成。","Codex result + review.md → 待核对",2,2],
    ["交接","审查交接核对通过","第三份 accepted 收据保存。现有核对仍不能自动证明所有候选代码已绑定审查结论。","accept(review-task) → 已交接 3 / 4",3,-1],
    ["执行","OpenCode 整理 Web 交付","读取前置交接，完成页面与说明；如果改动已审查核心，需要重新验证候选。","spawn_run(agent=poc-opencode) → OpenCode ACP",3,3],
    ["返回","前端交付返回","原生工具执行结束。观察器展示结果，父会话继续执行最后一次 accept。","delivery + handoff → completion event",3,3],
    ["完成","四步交接完成，查看实际交付物","进度达到 4 / 4。这代表示意流程的交接完成，不等于已经发布或通过生产安全验收。","accept(deliver-task) → report / preview / export",4,-1]
  ];
  const simulation = {index:0, scenario:"happy", resolved:false, timer:null};
  function stopSimulation() {
    if (simulation.timer) clearInterval(simulation.timer);
    simulation.timer = null;
    $(".execution-lab").classList.remove("playing");
    $("#sim-play").textContent = "播放";
  }
  function blocked() {
    return simulation.scenario === "mismatch" && simulation.index >= 8 ||
      simulation.scenario === "permission" && simulation.index >= 9 && !simulation.resolved ||
      simulation.scenario === "offline" && simulation.index >= 7 && !simulation.resolved;
  }
  function renderSimulation() {
    let [phase,title,description,command,accepted,activeTool] = steps[simulation.index];
    const isBlocked = blocked();
    let tone = "blue", specific = "", observer = "观察器：示意连接";
    if (isBlocked) {
      stopSimulation();
      if (simulation.scenario === "mismatch") {
        phase = "交接未通过"; title = "Claude 已返回，但实际模型不匹配";
        description = "不能用测试通过覆盖模型约定。保存失败检查记录，保留原生返回与历史快照，调整配置后应新建运行；Codex 尚未被分派。";
        command = "resolved_model ≠ 明确 model → accept 拒绝"; tone = "red"; specific = "blocked";
      } else if (simulation.scenario === "permission") {
        phase = "待授权"; title = "Codex 请求工具权限";
        description = "待处理不等于执行失败。真实权限应在 KiroCrew 原生对话处理。下面的按钮只模拟本报告中的允许结果。";
        command = "原生 permission request → 等待用户"; tone = "amber"; specific = "waiting";
      } else {
        phase = "观察断连"; title = "看板失去实时证据，停止运行动画";
        description = "保留最后快照和 25% 已交接进度，不能由此判断原生工具已经停止。模拟恢复后才继续展示后续事件。";
        command = "connected=false → 保留快照 / 暂停动画"; tone = "amber"; specific = "waiting"; observer = "观察器：断连示意";
      }
    }
    const pendingReturn = [5,8,10,13].includes(simulation.index);
    const callPhase = [0,0,1,2,3,5,5,4,5,4,5,5,4,5,5][simulation.index];
    $$("[data-call-phase]").forEach(n => n.classList.toggle("current", Number(n.dataset.callPhase) === callPhase));
    const sequenceEvent = [0,1,3,5,6,10,14,8,10,8,10,14,8,10,15][simulation.index];
    $$('#dispatch figure[data-diagram="dispatch"] [data-event]').forEach(n =>
      n.classList.toggle("event-active", Number(n.dataset.event) === sequenceEvent));
    $$("#sim-pipeline > div").forEach((card,i) => {
      card.className = "";
      let status = "待执行";
      if (i < accepted) {card.classList.add("done");status="已交接";}
      else if (i === activeTool) {
        card.classList.add(specific || (pendingReturn ? "waiting" : "running"));
        status = specific === "blocked" ? "交接未通过" : specific ? "待处理" : pendingReturn ? "待核对" : "执行中";
      }
      card.querySelector("span").textContent = status;
    });
    $("#sim-stage").className = "tag " + tone; $("#sim-stage").textContent = phase;
    $("#sim-title").textContent = title; $("#sim-description").textContent = description; $("#sim-command").textContent = command;
    $("#sim-meter-label").textContent = `已交接 ${accepted} / 4 · ${accepted * 25}%`;
    $("#sim-meter").setAttribute("aria-valuenow", String(accepted * 25)); $("#sim-meter i").style.width = accepted * 25 + "%";
    $("#sim-observer").textContent = observer; $("#sim-range").value = String(simulation.index);
    $("#sim-position").textContent = `${simulation.index + 1} / ${steps.length}`;
    $("#sim-next").disabled = isBlocked || simulation.index === steps.length - 1;
    $("#sim-play").disabled = isBlocked;
    $("#sim-resolve").hidden = !isBlocked || simulation.scenario === "mismatch";
    $("#sim-resolve").textContent = simulation.scenario === "permission" ? "模拟允许本次操作" : "模拟恢复连接";
    $("#sim-log").innerHTML = steps.slice(0, simulation.index+1).map((s,i) =>
      `<li class="${i===simulation.index?"current":""}">${escape(i===simulation.index?title:s[1])}</li>`).join("");
    if (simulation.index === steps.length - 1) stopSimulation();
  }
  function clampSimulation(index) {
    let cap = 14;
    if (simulation.scenario === "mismatch") cap = 8;
    if (!simulation.resolved && simulation.scenario === "permission") cap = 9;
    if (!simulation.resolved && simulation.scenario === "offline") cap = 7;
    return Math.min(index, cap);
  }
  function advanceSimulation() {simulation.index = clampSimulation(simulation.index + 1);renderSimulation();}
  $("#sim-next").addEventListener("click", advanceSimulation);
  $("#sim-reset").addEventListener("click", () => {stopSimulation();simulation.index=0;simulation.resolved=false;renderSimulation();});
  $("#sim-scenario").addEventListener("change", e => {stopSimulation();simulation.scenario=e.target.value;simulation.index=0;simulation.resolved=false;renderSimulation();});
  $("#sim-range").addEventListener("input", e => {stopSimulation();simulation.index=clampSimulation(Number(e.target.value));renderSimulation();});
  $("#sim-play").addEventListener("click", () => {
    if (simulation.timer) return stopSimulation();
    if (reduced.matches) return toast("已开启减少动态效果，请使用“下一步”逐步阅读。");
    if (simulation.index === 14) {simulation.index=0;renderSimulation();}
    $(".execution-lab").classList.add("playing");$("#sim-play").textContent="暂停";
    simulation.timer=setInterval(advanceSimulation,1600);
  });
  $("#sim-resolve").addEventListener("click", () => {simulation.resolved=true;renderSimulation();toast("已改变示意状态；没有处理任何真实权限或连接。");});
  new IntersectionObserver(entries => {if (!entries[0].isIntersecting) stopSimulation();},{threshold:0}).observe($(".execution-lab"));
  document.addEventListener("visibilitychange", () => {if (document.hidden) stopSimulation();});
  reduced.addEventListener("change", () => {if (reduced.matches) stopSimulation();});

  const routes = {
    kiro:{title:"Kiro 原生 ACP 路径",note:"poc-kiro 选择原生 Kiro factory，由 KiroCrew Runtime 驱动 kiro-cli ACP。模型与权限继续沿 Kiro 自身配置和原生会话处理。"},
    claude:{title:"claude-agent-acp → Claude Code",note:"poc-claude 选择 Claude factory。ACP adapter 经 Agent SDK 使用 Claude Code；工具自己的登录、settings 与 cwd 继续参与加载。"},
    codex:{title:"codex-acp → Codex App Server",note:"poc-codex 选择 Codex factory。明确 Model / Effort 在 factory 内按当前版本做兼容桥接，再由原生 ACP 配置处理。"},
    opencode:{title:"OpenCode 原生 ACP",note:"poc-opencode 选择 OpenCode factory。当前集成只允许默认 Effort；已知文件方法不兼容时使用有权限的原生 Shell 路径，不绕过授权。"}
  };
  function renderRoute(tool) {
    $$("[data-route]").forEach(b => {const selected=b.dataset.route===tool;b.classList.toggle("active",selected);b.setAttribute("aria-pressed",String(selected));});
    $("#route-tool").textContent=`tool: ${tool}`;$("#route-agent").textContent=`agent: poc-${tool}`;$("#route-backend").textContent=`backend: ${tool}`;
    $("#route-command").textContent=routes[tool].title;$("#route-note").textContent=routes[tool].note;
  }
  $$("[data-route]").forEach(b => b.addEventListener("click", () => renderRoute(b.dataset.route)));
  function renderGate() {
    const kind=$("#gate-case").value;
    const rows=[
      ["模型 ID","model-A",kind==="model"?"model-B":"model-A"],
      ["Effort","low",kind==="effort"?"high":kind==="unknown"?"未报告":"low"],
      ["观察快照","connected / age < 20s",kind==="stale"?"age = 30s":"connected / age = 2s"],
      ["原生回执","与 Task 关联",kind==="receipt"?"缺失":"已关联"],
      ["handoff","存在且非空",kind==="handoff"?"缺失":"存在且非空"]
    ];
    $("#gate-evidence").innerHTML=rows.map(r=>`<tr><td>${escape(r[0])}</td><td><code>${escape(r[1])}</code></td><td><code>${escape(r[2])}</code></td></tr>`).join("");
    const messages={
      match:["pass","参数示意通过。真实 accept 仍需检查父会话、步骤、Agent、后端、结果与 BLOCKED 等其余条件。"],
      model:["fail","交接未通过：明确模型 ID 不匹配。原生任务可以已成功返回，但不能接受为符合约定的交接。"],
      effort:["fail","交接未通过：后端已经报告实际 Effort，且它与请求不同。"],
      unknown:["warn","当前实现不会仅因 Effort 未报告而拒绝；必须保留“实际值未知”，不能声称 low 已生效。"],
      stale:["fail","交接未通过：观察快照过期。页面的历史结果不能替代有效原生证据。"],
      handoff:["fail","交接未通过：没有非空 handoff 文件，即使代码和测试看起来成功，也缺少要求的交接。"],
      receipt:["fail","交接未通过：缺少与该 Task ID 对应的原生请求回执，不能仅凭计划参数文件证明执行。"]
    };
    $("#gate-result").className="lab-result "+messages[kind][0];$("#gate-result").textContent=messages[kind][1];
  }
  $("#gate-case").addEventListener("change",renderGate);
  const contexts={
    run:["Run 共享资料","固定 Workflow、REQUEST.md、实际代码、diff、tests、review 和 handoff 位于本次 Run 工作区。各工具按任务读取，不代表它们共享所有历史对话。","共享范围：这次开发的明确资料。"],
    task:["本步完整指令","next_step 生成 step-instructions.md，包含完整需求、本步约束和前置交接 / 原生返回文件路径。短 Prompt 引导目标工具读取完整文件。","完整输入不依赖被截断的摘要，但仍要实际读取。"],
    private:["工具原生 Session","Claude、Codex、Kiro、OpenCode 各自管理原生会话。spawn_continue 可复用同工具 Conversation；跨工具不会自动翻译私有聊天历史或共享 KV Cache。","工具认证与私有状态也不自动共享。"],
    memory:["长期 Memory","本 MVP 的子任务明确 include_memory=false。原有 Memory 保留；没有把跨工具交接实现为长期记忆召回，也没有新增团队 Memory 同步。","keep=true 仍受原生保留策略约束。"]
  };
  function renderContext(key) {
    $$("[data-context]").forEach(b=>{const selected=b.dataset.context===key;b.classList.toggle("active",selected);b.setAttribute("aria-pressed",String(selected));});
    const c=contexts[key];$("#context-detail").innerHTML=`<h4>${c[0]}</h4><p>${c[1]}</p><strong>${c[2]}</strong>`;
  }
  $$("[data-context]").forEach(b=>b.addEventListener("click",()=>renderContext(b.dataset.context)));
  const files={
    definitions:["定义与版本","workflows/*.json 保存最新定义；state/workflow-versions/&lt;id&gt;/000001.json 等文件保存不可变版本。","显式 save 使用文件锁、名称唯一检查与 expected_revision；文件修改不会被后台自动导入。"],
    manifest:["固定 Run 快照","workflow-run.json 包含 Run、父 slot、Workflow 完整定义与配置 SHA-256。","之后编辑最新定义，不会改写已有 Run 的版本。准备 Run 时已经冻结。"],
    workspace:["给工作者读取和产出的文件","REQUEST.md、完整指令、前置返回、handoff 以及任务要求的代码、diff、测试、review、web。","本步和下游按文件交接；完整候选目录不在默认 Session 导出包中。"],
    evidence:["从期望到实际的证据","dispatch 文件是期望；原生回执与路由是执行证据；live/report 是观察；accepted/checks 是核对结果。","只拥有 dispatch 文件不能证明真实 Task 已运行。"],
    native:["KiroCrew 与工具自己的状态","原生对话、子 Session、工具 Session、认证和可能的 Memory 由各自组件管理。","工作台归档不删除这些数据。迁移时必须逐项核对允许备份的范围和恢复能力。"],
    export:["Session 证据与开发文档包","原生 Layer A、冻结 Workflow、report、conversation、development-manual、release-notes、features。","这是可追溯文档包，不是所有私有上下文、完整工程目录或认证的备份。"]
  };
  function renderFile(key) {
    $$("[data-file]").forEach(b=>{const selected=b.dataset.file===key;b.classList.toggle("active",selected);b.setAttribute("aria-pressed",String(selected));});
    const f=files[key];$("#file-description").innerHTML=`<span class="tag blue">持久化说明</span><h4>${f[0]}</h4><p>${f[1]}</p><p><strong>关键边界：</strong>${f[2]}</p>`;
  }
  $$("[data-file]").forEach(b=>b.addEventListener("click",()=>renderFile(b.dataset.file)));
  const modules={
    workflow:{title:"workflow.py：配置与运行约定",input:"用户配置、expected_revision、需求、原生观察证据",output:"版本、Run 快照、spawn 参数、交接收据与状态投影",boundary:"不自行调用 Coding CLI 或 spawn HTTP endpoint；父 Agent 经原生 MCP 分派。",links:[["save","保存"],["prepare","准备 Run"],["next_step","下一步"],["accept","核对"]]},
    registry:{title:"poc.py：已有 Provider 接口的组合",input:"原生 cfg、Agent 模板、Session key、model/effort override",output:"对应后端的原生 Provider 与实际选路日志",boundary:"继承原生会话与权限；未知 poc-* 明确拒绝。关闭跨后端 session sharing 与 warm pool。",links:[["registry","Registry 代码"]]},
    library:{title:"workflow_library.py：复用与生命周期",input:"工作流、Session 选择、生成意图、原生导出",output:"独立草稿、可恢复管理标记、Session 开发文档",boundary:"归档不删除原生数据；生成对话只设计，用户采用后才保存。",links:[["generate","生成"],["archive","归档"],["export","导出"]]},
    files:{title:"workflow_files.py：文档数据边界",input:"≤100 KB 的 JSON / YAML / Markdown 文本",output:"经过解析的工作流数据，或可移植文档",boundary:"不执行数据中的代码；拒绝重复字段、危险 YAML 类型与锚点引用。",links:[["parse","安全解析"]]},
    api:{title:"api.py：主机侧原生访问",input:"已绑定 Run、原生接口路径与主机认证",output:"原生状态、登录入口、会话导出",boundary:"本机 owner Token 留在主机 / 原生登录流程，不构成 Enterprise 用户授权体系。",links:[["auth","登录地址"],["observer","只读观察入口"]]},
    ui:{title:"ui/workflow*：让配置和证据可理解",input:"工作台 API 数据、用户草稿与显示偏好",output:"向导、Workflow / Sessions / Tasks、动态状态与产物入口",boundary:"动画不制造进度；浏览器草稿不等于已保存版本。代码执行仍由 KiroCrew 负责。",links:[]},
    launch:{title:"启动器与 reload_gateway.py",input:"当前端口、所属进程标记、原生忙闲状态",output:"受控启动 / 空闲重载和观察器服务",boundary:"保留其他服务与历史 Sessions；当前 macOS 启动器不是可直接用于 EC2 的 headless 服务。",links:[["reload","空闲重载条件"]]}
  };
  function renderModule(key) {
    $$("[data-module]").forEach(b=>{const selected=b.dataset.module===key;b.classList.toggle("active",selected);b.setAttribute("aria-pressed",String(selected));});
    const m=modules[key];
    $("#module-detail").innerHTML=`<span class="tag blue">模块职责</span><h4>${m.title}</h4><dl><dt>输入</dt><dd>${m.input}</dd><dt>输出</dt><dd>${m.output}</dd><dt>边界</dt><dd>${m.boundary}</dd></dl><div>${m.links.map(([id,label])=>`<button class="source-button" data-source="${id}">${label} · 查看源码</button>`).join("")}</div>`;
  }
  $$("[data-module]").forEach(b=>b.addEventListener("click",()=>renderModule(b.dataset.module)));
  renderSimulation();renderRoute("kiro");renderGate();renderContext("run");renderFile("definitions");renderModule("workflow");updateNavigation(active);
  if (location.hash && active !== "overview") requestAnimationFrame(()=>document.getElementById(active).scrollIntoView({behavior:"instant"}));
})();
