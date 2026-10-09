/* Run with Playwright's run-code tool; see tests/README.md.
 * All API calls are mocked. This never creates a native task or reads user state.
 */
async (page, {artifactRoot} = {}) => {
  const browser = await page.context().browser().browserType().launch({headless:true,channel:"chrome"});
  const context = await browser.newContext({viewport:{width:1440,height:1050},reducedMotion:"reduce"});
  const p = await context.newPage();
  const errors=[], calls=[], results=[];
  const capture=async name=>{
    await p.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    if(artifactRoot)await p.screenshot({path:`${artifactRoot}/${name}.png`,animations:"disabled"});
  };
  const assert=(ok,message)=>{if(!ok)throw Error(message);};
  const equal=(a,b,message)=>assert(a===b,`${message}: ${JSON.stringify(a)} !== ${JSON.stringify(b)}`);
  const storage="kirocrew.workflow.workbench.v2";
  const step={id:"code",name:"实现",tool:"claude",model:"auto",effort:"",prompt:"按目标完成实现与验证。"};
  const baseline={schema:1,id:"development",revision:1,name:"发布说明工作台",steps:[step]};
  const definitions=[baseline];
  const oldRun={id:"workflow-fixture-old",slot:"workflow-fixture-old",created_at:1700000000,
    workflow:baseline,session_meta:{archived:false}};
  const runs=[oldRun];
  const jobs=new Map();
  let ready=false;
  p.on("pageerror",e=>errors.push(String(e)));
  await context.route("**/api/**",async route=>{
    const request=route.request(),url=new URL(request.url()),path=url.pathname;
    const body=request.method()==="POST"?request.postDataJSON():null;
    if(body)calls.push({path,body});
    let data;
    if(path==="/api/catalogue")data=Object.fromEntries(["kiro","claude","codex","opencode"].map(tool=>[
      tool,{models:["auto"],advertised_models:[],observed_models:[],efforts:[""]}]));
    else if(path==="/api/runtime")data={features:["codex_effort_pair_v1"]};
    else if(path==="/api/library")data={definitions,deleted:{}};
    else if(path==="/api/runs")data=runs;
    else if(path==="/api/config"&&!body)data=definitions.find(d=>d.id===url.searchParams.get("id"));
    else if(path==="/api/config"&&body){
      data={...body.config,revision:body.expected_revision+1};definitions.push(data);
    }else if(path==="/api/state"){
      const manifest=runs.find(r=>r.id===url.searchParams.get("run"));
      data={manifest,status:"ready",at:Date.now()/1000,connected:true,approvals:[],
        input:{text:manifest.input||"已有 Session 的需求"},steps:manifest.workflow.steps.map(s=>({...s,status:"pending"}))};
    }else if(path==="/api/design"&&body){
      const id="design-"+body.request_id.replaceAll("-","");
      data={id,request_id:body.request_id,intent:body.intent,status:"submitted"};
      jobs.set(id,data);
    }else if(path==="/api/design"){
      const job=jobs.get(url.searchParams.get("id"));
      data={...job,status:ready?"ready":"running"};
      if(ready)data.config={...baseline,id:"flow-generated-fixture",revision:0,
        steps:[step,{...step,id:"review",name:"独立审查",tool:"codex"}]};
    }else if(path==="/api/start"){
      const manifest={id:"workflow-fixture-new",slot:"workflow-fixture-new",created_at:Date.now()/1000,
        workflow:definitions.find(d=>d.id===body.workflow_id),input:body.input,session_meta:{}};
      runs.unshift(manifest);data={status:"accepted",manifest};
    }else{
      errors.push(`Unexpected API call: ${request.method()} ${path}`);
      return route.fulfill({status:500,json:{error:"Unexpected test request"}});
    }
    await route.fulfill({json:data});
  });
  const value=id=>p.locator("#"+id).inputValue();
  const saved=()=>p.evaluate(key=>JSON.parse(localStorage.getItem(key)),storage);
  const checkNoAutoRun=()=>equal(calls.filter(c=>["/api/start","/api/prepare"].includes(c.path)).length,0,"adoption cannot execute");
  const templates=await (await context.request.get("http://127.0.0.1:8920/workflow-templates.json")).json();
  async function selectTemplate(id){
    await p.locator("#template-picker").evaluate(n=>n.open=true);
    await p.locator("#template-search").fill("");
    await p.locator('[data-category="all"]').click();
    await p.locator(`[data-template="${id}"]`).click();
  }
  try{
    await p.goto("http://127.0.0.1:8920/workflow.html");
    await p.locator("#workflow-builder[open]").waitFor();
    equal(await p.locator(".template-card").count(),3,"quick templates shown initially");
    await p.locator("#template-picker").evaluate(n=>n.open=false);
    await p.locator("#requirements").fill("上一份需求，不应误用于新草稿");
    await p.locator("#chat-entry").check();
    const intent="制作发布说明工作台：支持分类、预览与 Markdown 导出。Claude 编码，Codex 审查。";
    await p.locator("#workflow-intent").fill(intent);
    await p.locator("#generate-workflow").click();
    await p.waitForFunction(()=>document.querySelector("#generation-status").textContent.includes("正在分析"));
    await p.locator("#workflow-intent").fill("等待期间编辑的新意图，不属于刚才的生成请求");
    ready=true;
    await p.evaluate(()=>refreshGeneration());
    await p.locator("#apply-generated").click();
    equal(await value("workflow-name"),"发布说明工作台 (2)","generated name and collision suffix");
    equal(await value("requirements"),intent,"frozen intent fills goal");
    assert(!await p.locator("#chat-entry").isChecked(),"filled goal is used instead of empty Chat input");
    assert(await p.locator("#wizard-0").isVisible(),"adoption shows name and goal");
    equal((await saved()).build.stage,0,"goal stage persisted");
    checkNoAutoRun();
    results.push("采用意图：名称去重、完整原始意图填入、返回目标页、不会自动执行");

    const customName="编辑后的发布说明工具",customInput=intent+"\n增加复制按钮。";
    await p.locator("#workflow-name").fill(customName);
    await p.locator("#requirements").fill(customInput);
    await p.evaluate(()=>Promise.all([refreshGeneration(),refreshSessions()]));
    equal(await value("requirements"),customInput,"polling cannot overwrite manual changes");
    await p.reload();
    await p.waitForFunction(()=>document.querySelector("#session-title").textContent.includes("已有 Session"));
    await p.locator("#resume-builder").click();
    equal(await value("workflow-name"),customName,"old Session cannot replace selected draft on reload");
    equal(await value("requirements"),customInput,"goal survives reload");
    equal((await saved()).build.workflow_id,"flow-generated-fixture","draft identity survives reload");
    await p.locator("#wizard-next").click();
    equal(await p.locator("#draft-steps .draft-step").count(),2,"generated tasks preserved");
    await p.locator("#wizard-next").click();
    equal(await p.locator("#review-name").textContent(),customName,"confirmation name");
    equal(await p.locator("#review-input").textContent(),customInput,"confirmation goal");
    checkNoAutoRun();
    await p.locator("#start").click();
    await p.waitForFunction(()=>!document.querySelector("#workflow-builder").open);
    const start=calls.find(c=>c.path==="/api/start");
    equal(start.body.input,customInput,"submitted run receives edited goal");
    equal(start.body.workflow_id,"flow-generated-fixture","submitted run uses adopted workflow");
    results.push("轮询与刷新保留手写修改；确认页与最终提交名称、目标和工作流一致");

    await p.locator("#new-task").click();
    await selectTemplate("kiro-quickstart");
    equal(await value("requirements"),templates.find(t=>t.id==="kiro-quickstart").input,"template fills goal");
    await selectTemplate("coding-smoke");
    equal(await value("requirements"),templates.find(t=>t.id==="coding-smoke").input,"switch replaces previous example");
    await p.reload();
    await p.waitForFunction(()=>document.querySelector("#builder-resume-name").textContent.includes("编码与审查"));
    await p.locator("#resume-builder").click();
    await selectTemplate("idea-validation");
    equal(await value("requirements"),templates.find(t=>t.id==="idea-validation").input,"example provenance survives reload");
    await p.locator("#requirements").fill("我自己的目标，请保留所有细节。");
    await selectTemplate("team-kanban");
    equal(await value("requirements"),"我自己的目标，请保留所有细节。","template preserves manual goal");
    await selectTemplate("team-kanban");
    equal(await value("workflow-name"),"团队任务看板 (2)","repeated template name is unique");
    results.push("模板切换更新示例目标，刷新保留来源，手写目标不覆盖，同名自动加后缀");

    await p.locator("#requirements").fill("");
    for(const t of templates){
      await selectTemplate(t.id);
      const state=await saved(),draft=state.drafts[state.build.workflow_id];
      equal(state.build.input,t.input,`${t.id}: input`);
      equal(draft.steps.length,t.steps.length,`${t.id}: tasks`);
      equal(JSON.stringify(draft.steps),JSON.stringify(t.steps),`${t.id}: tool/model/effort/prompt`);
      equal(draft.revision,0,`${t.id}: independent new draft`);
    }
    results.push("全部 12 个模板使用现有工作流格式，目标与任务/Agent/Model/Effort 完整填入");

    await p.locator("#template-picker").evaluate(n=>n.open=true);
    await p.locator("#template-search").fill("CSV");
    equal(await p.locator(".template-card").count(),1,"search across categories");
    await p.locator("#template-search").fill("不应存在的模板关键词");
    equal(await p.locator(".template-card").count(),0,"empty search");
    assert((await p.locator("#template-count").textContent()).includes("没有匹配"),"empty state explanation");
    await p.locator("#template-search").fill("");
    await p.locator('[data-category="quick"]').click();
    await p.locator("#workflow-builder .drawer-scroll").evaluate(n=>n.scrollTop=0);
    assert(await p.evaluate(()=>document.querySelector(".template-footnote").getBoundingClientRect().top>document.querySelector("#workflow-templates").getBoundingClientRect().bottom),"template footnote does not overlap cards");
    await capture("templates-desktop");
    await p.setViewportSize({width:390,height:844});
    await capture("templates-mobile");
    assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),"no page horizontal overflow");
    assert(await p.locator("#workflow-builder").evaluate(n=>n.scrollWidth<=n.clientWidth+1),"no dialog horizontal overflow");
    await selectTemplate("kiro-quickstart");
    await p.locator("#workflow-builder .drawer-scroll").evaluate(n=>n.scrollTop=0);
    await capture("filled-goal-mobile");
    equal(errors.length,0,"browser and API errors");
    results.push("分类、搜索、无结果提示及桌面/390px 窄屏均通过；无浏览器错误");
    return {ok:true,results,apiWrites:calls.map(c=>c.path),nativeCalls:0,templates:templates.length};
  }catch(e){
    await capture("failure");
    throw Error(e.message+"\nBrowser errors: "+JSON.stringify(errors));
  }finally{
    await browser.close();
  }
}
