"""Configurable workflows on KiroCrew's existing App -> spawn_run path.

This module versions configuration, prepares App input and projects native
evidence. It never starts a Coding CLI or calls a spawn endpoint itself.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import shlex
import threading
import time
import unicodedata
from urllib.parse import parse_qs, urlsplit, unquote
import uuid

import api
import workflow_library as library
from workflow_files import parse_document
from pipeline import read_json, write_json, route_for, task_identity, require

ROOT = Path(__file__).resolve().parent
DEFINITIONS = ROOT / "workflows"
VERSIONS = ROOT / "state/workflow-versions"
RUNS = ROOT / "state/runs"
PORT = 8917
TOOLS = {
    "kiro": {"label": "Kiro CLI", "agent": "poc-kiro", "backend": "kiro",
             "efforts": ["", "low", "medium", "high", "xhigh", "max"]},
    "claude": {"label": "Claude Code", "agent": "poc-claude", "backend": "claude",
               "efforts": ["", "low", "medium", "high", "xhigh", "max"]},
    "codex": {"label": "Codex", "agent": "poc-codex", "backend": "codex",
              "efforts": ["", "low", "medium", "high", "xhigh", "max"]},
    "opencode": {"label": "OpenCode", "agent": "poc-opencode", "backend": "opencode",
                 "efforts": [""]},
}
MODEL_CACHE = Path.home() / ".kiro/crew/provider_models.json"


def advertised_models(tool):
    namespace = {"kiro": "acp", "claude": "claude_code"}.get(tool, tool)
    values = read_json(MODEL_CACHE, {}).get(namespace, [])
    return list(dict.fromkeys(v for v in values if isinstance(v, str) and v))


def validate_model_selection(steps):
    """An explicit Claude pick must be in that adapter's own published list.

    Crew treats startup pins as inherited and may fall back after rejection.
    A Workflow pick is explicit: refuse it before creating a run / dispatch.
    Saved portable definitions and old run snapshots remain untouched.
    """
    candidates = None
    for step in steps:
        if step["tool"] != "claude" or step["model"] in {"auto", "default"}:
            continue
        if candidates is None:
            candidates = advertised_models("claude")
        require(bool(candidates),
                "还没有 Claude Code 的原生模型候选。请先在 KiroCrew 使用 Claude Code，"
                "再刷新模型候选；或明确选择 auto。")
        require(step["model"] in candidates,
                f"任务「{step['name']}」的模型 {step['model']} 不在 Claude Code 当前公布的候选列表。"
                "请选择该工具列出的模型，或明确选择 auto；本工作流不会静默改用其他模型。")


def app_entry(run):
    manifest = load_run(run)
    return {"url": api.chat_entry_url(manifest["slot"]), "expires_in": 300}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def ident(value):
    require(isinstance(value, str) and bool(re.fullmatch(r"[a-z][a-z0-9-]{0,47}", value)),
            "ID 必须以小写字母开头，最多 48 位小写字母、数字或短横线。")
    return value


def text(value, label, minimum=1, maximum=4000):
    require(isinstance(value, str) and minimum <= len(value.strip()) <= maximum
            and "\x00" not in value, f"{label} 长度应为 {minimum}–{maximum} 字符。")
    return value.strip()


def workflow_name(value):
    value = text(value, "Workflow 名称", maximum=80)
    require(not any(unicodedata.category(c) in {"Cc", "Cf"} and not c.isspace()
                    for c in value), "工作流名称不能包含不可见控制字符。")
    return text(" ".join(unicodedata.normalize("NFKC", value).split()),
                "Workflow 名称", maximum=80)


def name_key(value):
    return workflow_name(value).casefold()


def assert_unique_name(name, workflow_id):
    """Call under VERSIONS/.lock when saving/restoring; deleted names stay reserved."""
    key = name_key(name)
    for definition in library.library()["definitions"]:
        require(definition["id"] == workflow_id or name_key(definition["name"]) != key,
                f"工作流名称「{name}」已被 {definition['id']} 使用（含已删除工作流）。"
                "请换一个名称，或编辑已有工作流。")


def validate(value):
    require(isinstance(value, dict), "Workflow 必须是 JSON 对象。")
    require(set(value) <= {"schema", "id", "name", "revision", "steps"},
            "存在不支持的顶层字段；首版只支持顺序步骤。")
    require(value.get("schema") == 1, "schema 必须为 1。")
    steps = value.get("steps")
    require(isinstance(steps, list) and 1 <= len(steps) <= 8, "首版支持 1–8 个顺序步骤。")
    normalized = []
    for step in steps:
        require(isinstance(step, dict) and set(step) <= {
            "id", "name", "tool", "model", "effort", "prompt"
        }, "步骤字段仅支持 id/name/tool/model/effort/prompt。")
        tool = step.get("tool")
        require(tool in TOOLS, "可用工具：kiro、claude、codex、opencode。")
        model = text(step.get("model", "auto"), "Model", maximum=200)
        require(not re.search(r"[\s\[\]]", model),
                "请填写原生模型 ID；Effort 单独设置，不写进 Model。")
        effort = step.get("effort", "")
        require(effort in TOOLS[tool]["efforts"],
                "此工具不支持该 Effort；当前 OpenCode 路径仅支持后端默认。")
        require(not effort or model not in {"auto", "default"},
                "设置 Effort 时必须选择具体模型，不能使用 auto/default。")
        # The native factory only propagates effort for models it recognizes.
        require(not effort or ("haiku" not in model.lower() and
                               any(word in model.lower() for word in ("opus", "sonnet", "fable", "gpt"))),
                "当前集成无法确认该模型的 Effort 支持；请使用后端默认。")
        normalized.append({
            "id": ident(step.get("id")), "name": text(step.get("name"), "步骤名称", maximum=80),
            "tool": tool, "model": model, "effort": effort,
            "prompt": text(step.get("prompt"), "步骤任务", maximum=4000),
        })
    require(len({s["id"] for s in normalized}) == len(normalized), "步骤 ID 不可重复。")
    return {"schema": 1, "id": ident(value.get("id")),
            "name": workflow_name(value.get("name")), "steps": normalized}


def latest(workflow_id):
    path = VERSIONS / ident(workflow_id)
    revisions = sorted(path.glob("*.json"))
    require(bool(revisions), "Workflow 尚未保存；先执行 save 或在 Web 中保存。")
    return read_json(revisions[-1])


def runtime_features():
    return read_json(ROOT / "state/gateway-runtime.json", {}).get("composition_features", [])


def require_runtime(definition):
    if any(s["tool"] == "codex" and s["effort"] for s in definition["steps"]):
        require("codex_effort_pair_v1" in runtime_features(),
                "当前 Gateway 尚未加载 Codex Effort 桥接修正。请等待空闲后重载 PoC Gateway。")


def save(value, expected_revision):
    """One writer across Web, Chat shell and file import; immutable revisions."""
    normalized = validate(value)
    require(isinstance(expected_revision, int) and not isinstance(expected_revision, bool)
            and expected_revision >= 0, "必须提交 expected_revision。")
    DEFINITIONS.mkdir(parents=True, exist_ok=True)
    VERSIONS.mkdir(parents=True, exist_ok=True)
    with (VERSIONS / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        library.assert_active(normalized["id"])
        assert_unique_name(normalized["name"], normalized["id"])
        directory = VERSIONS / normalized["id"]
        directory.mkdir(exist_ok=True)
        files = sorted(directory.glob("*.json"))
        previous = read_json(files[-1]) if files else None
        current_revision = previous["revision"] if previous else 0
        require(expected_revision == current_revision,
                f"版本冲突：当前为 r{current_revision}，请重新加载后合并修改。")
        if previous and validate(previous) == normalized:
            return previous
        result = {**normalized, "revision": current_revision + 1}
        write_json(directory / f"{result['revision']:06d}.json", result)
        write_json(DEFINITIONS / f"{normalized['id']}.json", result)
        return result


def change(workflow_id, step_id, expected_revision, **fields):
    value = latest(workflow_id)
    require(value["revision"] == expected_revision, "版本冲突；先读取当前版本。")
    step = next((s for s in value["steps"] if s["id"] == step_id), None)
    require(step is not None, "步骤不存在。")
    if fields.get("tool") is not None and fields["tool"] != step["tool"]:
        step.update(model="auto", effort="")
    step.update({k: v for k, v in fields.items() if v is not None})
    return save(value, expected_revision)


def run_path(value):
    path = Path(value)
    if not path.is_absolute():
        path = RUNS / str(value)
    path = path.resolve()
    require(path.parent == RUNS.resolve() and path.name.startswith("workflow-"),
            "运行必须是本 PoC 的 workflow-* 目录。")
    require((path / "workflow-run.json").is_file(), "Workflow 运行不存在。")
    return path


def load_run(run):
    manifest = read_json(run / "workflow-run.json")
    require(fingerprint(manifest["workflow"]) == manifest["workflow_sha256"],
            "运行快照已被修改；停止执行。")
    return manifest


def marker(manifest, step_id):
    return f"[WORKFLOW:{manifest['id']} STEP:{step_id}]"



def capture(run, requirement):
    requirement = text(requirement, "用户需求", minimum=3, maximum=12000)
    path = run / "input.json"
    if path.exists():
        require(read_json(path)["text"] == requirement, "本次需求已冻结；请新建运行。")
    else:
        write_json(path, {"text": requirement, "sha256": fingerprint(requirement)})
        (run / "workspace/REQUEST.md").write_text(requirement + "\n")
    return {"ok": True, "run": str(run), "input": requirement}


def control_prompt(manifest):
    command = f"python3 {shlex.quote(str(ROOT / 'workflow.py'))}"
    run = manifest["run"]
    qrun = shlex.quote(run)
    workflow = manifest["workflow"]
    return f"""本条 KiroCrew App 对话使用用户可配置的 Workflow MVP。
配置源 {DEFINITIONS / (workflow['id'] + '.json')}；本次固定 r{workflow['revision']}。
运行快照 {run}/workflow-run.json；所有子任务 cwd={run}/workspace。
这里的配置优先决定工具和任务顺序，不要套用默认的固定四步骤。
你只协调，使用 KiroCrew 原生 spawn_run；不要自行启动 Coding CLI 或访问 owner token。
需求入口：
如果用户给出开发需求且 input.json 不存在，将原始需求写入 {run}/user-input.txt，
执行 {command} capture {qrun} --input-file {shlex.quote(run + '/user-input.txt')}。
如果已经存在 input.json，继续执行已冻结需求。
执行协议：
1. 运行 {command} next {qrun}。输出 spawn 字段就是下一步原生 spawn_run 的精确参数。
2. 完整传递 task、agent、model、reasoning_effort、cwd 等字段。不要省略或改写模型和 Effort。
3. 调用一次 spawn_run 后结束 turn，等待原生 completion event。不要循环轮询。
4. 完成后运行 {command} accept {qrun} --task-id <真实返回的本次 task-id>。
   accept 根据宿主观察器的原生任务、真实后端和模型核对归属；失败必须报告并停止。
5. accept 成功后再次 next，直到 done=true。最后汇总真实 ID、产物、验证局限与看板地址。
不要宣称模型自身的文字回答能证明后端身份。不要把工具执行结束直接称为质量审查通过。
每一步独立子 Session，以共享工作目录、原始需求和之前的返回结果交接。不注入长期 Memory。
配置对话：
如果用户请求调整工作流，不启动开发任务。先运行 {command} show {workflow['id']}。
单步修改使用 {command} set {workflow['id']} --step <id> --expected-revision <当前版本>
加 --tool kiro|claude|codex|opencode、--model <原生ID>、--effort low|medium|high|xhigh|max（空串为默认）。
批量/增删/排序修改：把新 JSON 写到 {run}/workflow-draft.json，
再运行 {command} save {shlex.quote(run + '/workflow-draft.json')} --expected-revision <当前版本>。
保存成功后报告新版本，并明确只对下次运行生效。不得修改本次 workflow-run.json。
用户无需自己写 Plan.md 或 Tasks；这些是工作者根据需求产生的输出。
当前 PoC 仅在指定工作目录做本地 Web 开发/分析，不安装依赖、不提交、不发布。
权限请求保留在 KiroCrew App；遇到权限拒绝如实报告，不规避。
看板：http://127.0.0.1:{PORT}/?run={manifest['id']}
"""


def prepare(workflow_id, expected_revision):
    library.assert_active(workflow_id)
    definition = latest(workflow_id)
    require(definition["revision"] == expected_revision, "配置已更新；重新加载后再创建运行。")
    validate_model_selection(definition["steps"])
    run_id = time.strftime("workflow-%Y%m%d-%H%M%S-") + uuid.uuid4().hex
    run = RUNS / run_id
    (run / "workspace").mkdir(parents=True)
    (run / "accepted").mkdir()
    manifest = {"schema": 1, "id": run_id, "run": str(run), "slot": run_id,
                "parent": f"dashboard:{run_id}", "created_at": time.time(),
                "workflow": definition, "workflow_sha256": fingerprint(definition)}
    write_json(run / "workflow-run.json", manifest)
    slot = api.request("/api/chat/slots", {
        "name": run_id, "agent": "poc-coordinator", "agent_kind": "template", "model": "auto",
    })
    require(slot.get("key", slot.get("slot")) == run_id, "原生 App slot ID 不匹配。")
    prompt = control_prompt(manifest)
    (run / "app-context.txt").write_text(prompt)
    receipt = api.request(f"/api/chat/slots/{run_id}/context",
                          {"content": prompt, "source": "workflow-mvp", "ephemeral": True})
    require(receipt.get("ok"), "原生 App 未接受 Workflow 上下文。")
    write_json(run / "intake.json", {"status": "prepared", "receipt": receipt})
    return manifest


def submit(manifest, requirement):
    run = run_path(manifest["run"])
    require_runtime(manifest["workflow"])
    validate_model_selection(manifest["workflow"]["steps"])
    capture(run, requirement)
    current = read_json(run / "intake.json")
    require(current["status"] == "prepared", "本次已发送或结果待确认；请查看原生 App。")
    write_json(run / "intake.json", {"status": "sending", "at": time.time()})
    try:
        receipt = api.request("/api/chat?ws=1", {"slot": manifest["slot"], "message": requirement})
        require(receipt.get("ok"), "原生 App 未确认收到输入。")
        current = {"status": "accepted", "receipt": receipt}
    except Exception as exc:
        current = {"status": "uncertain", "error": str(exc),
                   "guidance": "打开 App 确认是否已发送；本服务不会自动重试。"}
    write_json(run / "intake.json", current)
    return current


def next_step(run):
    manifest = load_run(run)
    require_runtime(manifest["workflow"])
    request = read_json(run / "input.json")
    require(request is not None and fingerprint(request["text"]) == request["sha256"],
            "请先登记用户输入。")
    history = []
    receipts = dispatch_receipts(manifest)
    for step in manifest["workflow"]["steps"]:
        completed = read_json(run / "accepted" / f"{step['id']}.json")
        latest_receipt = receipts.get(step["id"])
        if completed and latest_receipt and completed["task_id"] != latest_receipt["task_id"]:
            completed = None
        if completed:
            result_file = run / "workspace" / (step["id"] + "-result.txt")
            if not result_file.exists():
                result_file.write_text(completed["result"] + "\n")
            history.append(
                f"{step['name']} ({completed['task_id']}):\n"
                f"交接 {run / 'workspace' / (step['id'] + '-handoff.md')}\n"
                f"原生完整返回 {result_file}"
            )
            continue
        validate_model_selection([step])
        output = run / "workspace" / (step["id"] + "-handoff.md")
        instructions = (
            f"{marker(manifest, step['id'])}\n"
            f"用户原始需求：\n{request['text']}\n\n"
            f"你的任务：{step['prompt']}\n"
            f"工作目录：{run / 'workspace'}。所有工作限定在此目录，不安装依赖，不发布或提交。"
            "不要派生子任务。需要计划/测试/任务文件时自行生成，不要求用户手写。\n"
            f"前序结果：\n{chr(10).join(history) if history else '无，这是第一步。'}\n"
            f"实际执行完成后，把交接说明写到 {output}，并在最终回答中报告文件和真实验证结果。"
            "如遇阻塞或质量不通过，明确写出 BLOCKED，不得伪造完成。"
        )
        if step["tool"] == "opencode":
            instructions += (
                "\n本机兼容性：KiroCrew 当前 ACP Client 不处理 fs/write_text_file。"
                "请使用 OpenCode 已有的 Bash/Shell 工具，通过 Python 或 Node 在指定工作目录内读写文件。"
                "这是协议能力限制，不是权限授权；如果 Shell 收到权限拒绝，请停止并报告，不能绕过。"
            )
        instruction_file = run / "workspace" / (step["id"] + "-instructions.md")
        instruction_file.write_text(instructions + "\n")
        # Native SPAWN_RUN_SCHEMA caps task at 5,000 characters. The complete
        # specification and previous results travel as files, never truncation.
        prompt = (
            f"{marker(manifest, step['id'])}\n"
            f"这是用户自定义工作流中的 {step['name']} 步骤。\n"
            f"开始前完整阅读 {instruction_file} 与 {run / 'workspace/REQUEST.md'}。"
            "指令文件包含你的完整任务、前序交接及原生完整返回文件路径，必须依次读取相关文件。\n"
            f"用户需求摘要：{request['text'][:800]}\n"
            f"本步任务摘要：{step['prompt'][:800]}\n"
            f"只在 {run / 'workspace'} 操作，不安装依赖、不发布、不提交、不派生子任务。"
            f"实际完成后写交接文件 {output}，最终返回真实执行与验证结果。"
            "若确实阻塞，在单独一行写 BLOCKED 并说明原因。完整需求以文件为准。"
        )
        require(len(prompt) <= 5000, "工作目录路径过长，无法满足原生 task 长度限制。")
        # Emit native MCP field names, not a second orchestration protocol.
        spawn = {"task": prompt, "agent": TOOLS[step["tool"]]["agent"],
                 "model": step["model"], "reasoning_effort": step["effort"],
                 "cwd": str(run / "workspace"), "keep": True, "include_memory": False,
                 "solo_reason": "user_requested",
                 "solo_details": "用户明确要求按自定义 Workflow 逐步调用所选择的 Coding 工具、模型和 Effort。"}
        write_json(run / ("dispatch-" + step["id"] + ".json"),
                   {"step": step["id"], "workflow_sha256": manifest["workflow_sha256"],
                    "spawn": spawn, "created_at": time.time()})
        return {"done": False, "step": step["id"], "spawn": spawn}
    return {"done": True, "run": manifest["id"], "steps": len(history),
            "report": str(run / "workflow-report.json")}


def model_matches(requested, actual):
    if requested in {"auto", "default"}:
        return True
    return requested == re.sub(r"\[(low|medium|high|xhigh|max)\]$", "", actual or "")


def _accept(run, task_id):
    manifest = load_run(run)
    snapshot = read_json(run / "workflow-live.json", {})
    require(snapshot.get("connected") and 0 <= time.time() - snapshot.get("at", 0) < 20,
            "宿主观察器未连接或已过期；启动 workflow.py serve 后重试。")
    active = next_step(run)
    require(not active["done"], "所有步骤已完成。")
    row = next(s for s in snapshot["steps"] if s["id"] == active["step"])
    task = row.get("task") or {}
    require(task.get("id") == task_id and task.get("parent") == manifest["parent"],
            "真实任务不属于当前步骤/父会话。")
    require(task.get("done") and not task.get("error") and not task.get("stopped"),
            "原生任务尚未成功结束。")
    require((task.get("result") or "").strip() not in {"", "_No response._"},
            "后端未返回完成结果；核对产物并在 App 中完成续作。")
    require(task.get("agent") == active["spawn"]["agent"], "原生 Agent 与配置不匹配。")
    require((row.get("route") or {}).get("actual_backend") == TOOLS[row["tool"]]["backend"],
            "真实 ACP 后端与配置不匹配。")
    require(row.get("requested_model") == active["spawn"]["model"], "原生 spawn 请求的模型与配置不一致。")
    native_request = row.get("native_request") or {}
    require(native_request.get("task_id") == task_id, "缺少与任务 ID 对应的原生 spawn 回执。")
    if native_request.get("conversation"):
        require(row["route"].get("crew_session_key") == "subagent:" + native_request["conversation"],
                "续作未复用原生回执指定的 Conversation。")
    require(native_request.get("reasoning_effort", "") == active["spawn"]["reasoning_effort"],
            "原生 spawn 的 Effort 请求与配置不同。")
    require(model_matches(row["model"], row.get("resolved_model")),
            f"实际模型与配置不匹配：请求 {row['model']}，后端报告 {row.get('resolved_model') or '未报告'}。"
            "任务返回不代表参数核对通过；请从本工具的候选列表选择模型并创建下一版运行。")
    observed_effort = row.get("effort_observation", {}).get("value")
    require(not row["effort"] or not observed_effort or row["effort"] == observed_effort,
            "后端报告的 Effort 与配置不同；停止并查看 App。")
    require(not re.search(r"(?im)^\s*(?:[-*]\s*)?(?:状态[：:]\s*)?BLOCKED\b",
                          task.get("result", "")),
            "工作者报告 BLOCKED，请在 App 处理后开启新运行。")
    handoff = run / "workspace" / (row["id"] + "-handoff.md")
    require(handoff.is_file() and handoff.stat().st_size > 0, "工作者缺少交接文件。")
    receipt = {"step": row["id"], "task_id": task_id, "at": time.time(),
               "result": task.get("result", ""), "route": row["route"],
               "requested_model": row.get("requested_model"), "resolved_model": row.get("resolved_model"),
               "native_request": native_request,
               "requested_effort": row["effort"], "effort_observation": row["effort_observation"],
               "handoff_sha256": hashlib.sha256(handoff.read_bytes()).hexdigest(),
               "quality": "原生执行结束且交接文件存在；不是自动质量认证"}
    accepted_path = run / "accepted" / f"{row['id']}.json"
    previous = read_json(accepted_path)
    if previous and previous["task_id"] != task_id:
        (run / "accepted/previous").mkdir(exist_ok=True)
        write_json(run / "accepted/previous" / f"{row['id']}-{previous['task_id']}.json", previous)
    write_json(accepted_path, receipt)
    (run / "workspace" / (row["id"] + "-result.txt")).write_text(receipt["result"] + "\n")
    return {"ok": True, **receipt}


def accept(run, task_id):
    require(bool(re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", task_id)), "Invalid task ID")
    checks = run / "checks"
    checks.mkdir(exist_ok=True)
    try:
        result = _accept(run, task_id)
    except ValueError as exc:
        write_json(checks / f"{task_id}.json",
                   {"task_id": task_id, "passed": False, "error": str(exc), "at": time.time()})
        raise
    write_json(checks / f"{task_id}.json", {"task_id": task_id, "passed": True, "at": time.time()})
    return result


_CODEX_LOGS = {}


def codex_turn_evidence(session_id):
    """Only metadata from the exact native Codex session used by this task."""
    if not isinstance(session_id, str) or not re.fullmatch(r"[a-f0-9-]{36}", session_id):
        return None
    path = _CODEX_LOGS.get(session_id)
    if path is None:
        candidates = list((Path.home() / ".codex/sessions").glob(f"**/*{session_id}.jsonl"))
        if len(candidates) != 1:
            return None
        path = candidates[0]
        _CODEX_LOGS[session_id] = path
    session_matches, turn = False, None
    try:
        for line in path.read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            payload = event.get("payload", {})
            if event.get("type") == "session_meta":
                session_matches = payload.get("id") == session_id
            if event.get("type") == "turn_context" and session_matches:
                turn = {"value": payload.get("effort"), "model": payload.get("model"),
                        "source": "Codex native turn_context", "turn_id": payload.get("turn_id")}
    except OSError:
        return None
    return turn


def dispatch_receipts(manifest):
    """Read this App conversation's native tool events, including queued ACKs."""
    path = Path.home() / ".kiro/crew/sessions" / (manifest["parent"].replace(":", "_") + ".jsonl")
    receipts, by_task, seen = {}, {}, set()
    for line in path.read_text().splitlines() if path.exists() else []:
        try:
            event = json.loads(line)
            meta = event.get("meta", {})
            tool = meta.get("tool_name", "").split("/")[-1]
            if event.get("role") != "tool" or tool not in {"spawn_run", "spawn_continue"}:
                continue
            params = json.loads(meta.get("input", "{}"))
            output = meta.get("output", "")
            event_key = (meta.get("tool_call_id"), output)
            if not output or event_key in seen:
                continue
            seen.add(event_key)
            if tool == "spawn_continue":
                continued = re.search(r"Continued conversation ([a-f0-9]{8,}) as run ([a-f0-9]{8,})\.", output)
                if not continued or continued[1] != params.get("conversation"):
                    continue
                origin = by_task.get(continued[1])
                if origin is None:
                    continue
                step_id, original = origin
                receipt = {
                    **original, "task_id": continued[2],
                    "tool_call_id": meta.get("tool_call_id"),
                    "conversation": continued[1],
                    "origin_task_id": original.get("origin_task_id", original["task_id"]),
                    "agent": params.get("agent") or original["agent"],
                    "model": params.get("model") or original["model"],
                    "source": "native App continuation event; model/effort inherited unless overridden",
                }
                receipts[step_id] = receipt
                by_task[continued[2]] = (step_id, receipt)
                continue
            task_ids = re.findall(r"(?m)^\s*([a-f0-9]{8,}) \(", meta.get("output", ""))
            if not task_ids:
                continue
            for step in manifest["workflow"]["steps"]:
                if marker(manifest, step["id"]) in params.get("task", ""):
                    receipts[step["id"]] = {
                        "task_id": task_ids[0], "tool_call_id": meta.get("tool_call_id"),
                        "agent": params.get("agent"), "model": params.get("model", ""),
                        "reasoning_effort": params.get("reasoning_effort", ""),
                        "cwd": params.get("cwd"), "source": "native App tool event",
                    }
                    by_task[task_ids[0]] = (step["id"], receipts[step["id"]])
        except (ValueError, TypeError):
            continue
    return receipts


def project(run, tasks, parent, approvals):
    manifest = load_run(run)
    receipts = dispatch_receipts(manifest)
    rows = []
    for step in manifest["workflow"]["steps"]:
        receipt = receipts.get(step["id"])
        selected = [task_identity(t) for t in tasks
                    if t.get("parent") == manifest["parent"]
                    and (marker(manifest, step["id"]) in t.get("task", "")
                         or receipt and t.get("id") == receipt["task_id"])]
        task = max(selected, key=lambda t: t.get("started", 0)) if selected else None
        route = route_for(task) if task else None
        stored = read_json(Path.home() / f".kiro/crew/subagents/{task['id']}/state.json", {}) if task else {}
        actual = stored.get("resolved_model", "")
        effort_match = re.search(r"\[(low|medium|high|xhigh|max)\]$", actual)
        effort_observation = {
            "value": effort_match.group(1) if step["tool"] == "codex" and effort_match else None,
            "source": "native resolved_model" if step["tool"] == "codex" and effort_match else "not_reported",
        }
        if step["tool"] == "codex" and route:
            effort_observation = codex_turn_evidence(route.get("native_session_id")) or effort_observation
        accepted = read_json(run / "accepted" / f"{step['id']}.json")
        if accepted and receipt and accepted["task_id"] != receipt["task_id"]:
            accepted = None
        evidence_source = "native live task"
        if accepted and task is None:
            # The Gateway's in-memory completed-task list need not survive a
            # restart. Keep previously verified evidence, labelled as such.
            task = {"id": accepted["task_id"], "parent": manifest["parent"], "done": True,
                    "agent": TOOLS[step["tool"]]["agent"], "result": accepted["result"]}
            route = accepted["route"]
            actual = accepted.get("resolved_model", "")
            stored = {"requested_model": accepted.get("requested_model", "")}
            effort_observation = accepted["effort_observation"]
            receipt = accepted.get("native_request") or receipt
            evidence_source = "persisted verified checkpoint"
        check = read_json(run / "checks" / (task["id"] + ".json"), {}) if task else {}
        state = "accepted" if accepted else (
            "failed" if task and (task.get("error") or task.get("stopped")) else
            "check_failed" if check.get("passed") is False else
            "awaiting_check" if task and task.get("done") else "running" if task else
            "submitted" if receipt else "pending")
        rows.append({**step, "task_uid": f"{manifest['id']}/{step['id']}",
                     "status": state, "task": task, "route": route,
                     "native_request": receipt,
                     "evidence_source": evidence_source,
                     "check_error": check.get("error"),
                     "attempts": [{"id": t["id"], "done": t.get("done"), "error": t.get("error")}
                                  for t in selected],
                     "requested_model": stored.get("requested_model", ""),
                     "resolved_model": actual, "effort_observation": effort_observation,
                     "model_mismatch": bool(actual and not model_matches(step["model"], actual)),
                     "accepted": accepted})
    keys = {manifest["parent"]} | {f"subagent:{r['task']['id']}" for r in rows if r["task"]}
    own_approvals = [a for a in approvals
                     if a.get("session_key", a.get("session", "")) in keys
                     or a.get("slot") == manifest["slot"]]
    # ACP permissions in the App chat are not always included in the global
    # approvals endpoint. Use the native message's resolved flag, not text.
    if parent.get("running"):
        pending = {}
        for message in parent.get("messages", []):
            if message.get("role") != "permission":
                continue
            meta = message.get("meta", {})
            approval_id = meta.get("approval_id")
            if approval_id:
                pending[approval_id] = meta
        known = {a.get("id", a.get("approval_id")) for a in own_approvals}
        own_approvals += [
            {"id": key, "session_key": manifest["parent"],
             "title": meta.get("tool_title", "App 工具授权"),
             "source": "native App permission event"}
            for key, meta in pending.items() if not meta.get("resolved") and key not in known
        ]
    completed = all(r["status"] == "accepted" for r in rows)
    preview = next((name for name in ("web/index.html", "index.html")
                    if (run / "workspace" / name).is_file()), None)
    return {"manifest": manifest, "at": time.time(), "connected": True, "preview": preview,
            "steps": rows, "parent_running": parent.get("running", False),
            "approvals": own_approvals, "input": read_json(run / "input.json", {}),
            "intake": read_json(run / "intake.json", {}),
            "status": "completed" if completed else "awaiting_approval" if own_approvals else
                      "failed" if any(r["status"] == "failed" for r in rows) else
                      "check_failed" if any(r["status"] == "check_failed" for r in rows) else
                      "running" if any(r["task"] or r["native_request"] for r in rows) or parent.get("running") else "ready"}


def observe():
    gateway = api.ReadOnlyGateway()
    while True:
        paths = list(RUNS.glob("workflow-*/workflow-run.json"))
        try:
            payload = gateway.get("/api/spawn")
            tasks = payload.get("agents", []) if isinstance(payload, dict) else payload
            raw_approvals = gateway.get("/api/approvals")
            approvals = raw_approvals.get("approvals", []) if isinstance(raw_approvals, dict) else raw_approvals
            for path in paths:
                run = path.parent
                try:
                    manifest = load_run(run)
                    parent = gateway.get("/api/chat/slots/" + manifest["slot"])
                    snapshot = project(run, tasks, parent, approvals)
                    write_json(run / "workflow-live.json", snapshot)
                    write_json(run / "workflow-report.json", snapshot)
                except Exception as exc:
                    previous = read_json(run / "workflow-live.json", {})
                    write_json(run / "workflow-live.json", {**previous, "connected": False, "error": str(exc)})
        except Exception:
            for path in paths:
                previous = read_json(path.parent / "workflow-live.json", {})
                write_json(path.parent / "workflow-live.json", {**previous, "connected": False,
                           "error": "原生 Gateway 暂时不可达"})
        time.sleep(2)


def catalogue():
    result = copy.deepcopy(TOOLS)
    for tool, value in result.items():
        value["advertised_models"] = advertised_models(tool)
        value["models"] = list(dict.fromkeys(["auto"] + value["advertised_models"]))
        value["observed_models"] = []
        value["catalogue_source"] = "此工具最近一次公布的原生模型候选；不等于当前账号权限保证"
    # Add models actually observed in this PoC, without scanning other chats.
    audit = ROOT / "evidence/provider-routing.jsonl"
    for line in (audit.read_text().splitlines() if audit.exists() else []):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        key = row.get("session_key", "")
        if not key.startswith("subagent:"):
            continue
        state = read_json(Path.home() / f".kiro/crew/subagents/{key.split(':', 1)[1]}/state.json", {})
        model = re.sub(r"\[(low|medium|high|xhigh|max)\]$", "", state.get("resolved_model", ""))
        tool = row.get("actual_backend")
        if tool in result and model and model not in result[tool]["observed_models"]:
            result[tool]["observed_models"].append(model)
            if tool != "claude" and model not in result[tool]["models"]:
                result[tool]["models"].append(model)
    return result


def preview_file(run, relative):
    relative = unquote(relative)
    parts = Path(relative).parts
    require(parts and not Path(relative).is_absolute() and
            not any(p.startswith(".") for p in parts), "Invalid preview path")
    workspace = (run / "workspace").resolve()
    path = (workspace / relative).resolve()
    require(path.is_relative_to(workspace) and path.is_file() and
            path.suffix.lower() in {".html", ".css", ".js", ".mjs", ".json", ".txt", ".md", ".svg", ".png"},
            "Preview file unavailable")
    return path


def serve(port=PORT):
    import os
    write_json(ROOT / "state/workflow-server.json", {"pid": os.getpid(), "port": port})
    threading.Thread(target=observe, daemon=True).start()
    receipts = ROOT / "state/workflow-intake"
    receipts.mkdir(parents=True, exist_ok=True)
    intake_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def respond(self, value, status=200, kind="application/json", preview=False, download=None):
            data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            for k, v in {"Content-Type": kind + "; charset=utf-8", "Content-Length": str(len(data)),
                         "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                         "Content-Security-Policy": (
                             "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                             "style-src 'self' 'unsafe-inline'; connect-src 'none'; "
                             "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
                             if preview else
                             "default-src 'self'; script-src 'self'; style-src 'self'; "
                             "connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
                             "frame-ancestors 'none'"),
                         "Referrer-Policy": "no-referrer"}.items():
                self.send_header(k, v)
            if download:
                self.send_header("Content-Disposition", f'attachment; filename="{download}"')
            self.end_headers()
            self.wfile.write(data)

        def allowed(self, mutation=False):
            return self.headers.get("Host") == f"127.0.0.1:{port}" and (
                not mutation or (self.headers.get("Origin") == f"http://127.0.0.1:{port}"
                                 and self.headers.get("X-Workflow-MVP") == "1"
                                 and self.headers.get("Content-Type", "").split(";")[0] == "application/json"))

        def do_GET(self):
            if self.headers.get("Host") == f"localhost:{port}":
                match = re.fullmatch(r"/p/(workflow-[a-zA-Z0-9-]+)/(.+)", urlsplit(self.path).path)
                if not match:
                    return self.respond({"error": "Preview origin cannot access configuration"}, 403)
                try:
                    path = preview_file(run_path(match[1]), match[2])
                    return self.respond(path.read_bytes(), kind=mimetypes.guess_type(str(path))[0] or "text/plain",
                                        preview=True)
                except (ValueError, OSError):
                    return self.respond({"error": "Preview unavailable"}, 404)
            if not self.allowed():
                return self.respond({"error": "Local workflow origin required"}, 403)
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            try:
                if url.path in {"/", "/workflow.css", "/workflow.js", "/workflow-view.css",
                                "/workflow-view.js", "/workflow-templates.json",
                                "/crew-entry.html", "/crew-entry.js"}:
                    name = "workflow.html" if url.path == "/" else url.path[1:]
                    path = ROOT / "ui" / name
                    return self.respond(path.read_bytes(), kind=mimetypes.guess_type(str(path))[0] or "text/plain")
                if url.path == "/api/config":
                    return self.respond(latest(query.get("id", ["development"])[0]))
                if url.path == "/api/definitions":
                    data = library.library()
                    return self.respond([d for d in data["definitions"] if d["id"] not in data["deleted"]])
                if url.path == "/api/library":
                    return self.respond(library.library())
                if url.path == "/api/design":
                    return self.respond(library.design_status(query.get("id", [""])[0]))
                if url.path.startswith("/docs/") and url.path[6:] in {
                    "DEVELOPMENT-HANDBOOK.md", "RELEASE-NOTES.md", "FEATURES-AND-DECISIONS.md",
                    "OPERATIONS.md"}:
                    return self.respond((ROOT / "docs" / url.path[6:]).read_bytes(), kind="text/plain")
                if url.path == "/api/catalogue":
                    return self.respond(catalogue())
                if url.path == "/api/runtime":
                    return self.respond({"features": runtime_features()})
                if url.path == "/api/runs":
                    runs = [{**load_run(p.parent), "session_meta": library.session_meta(p.parent)}
                            for p in RUNS.glob("workflow-*/workflow-run.json")]
                    return self.respond(sorted(runs, key=lambda r: r["created_at"], reverse=True))
                if url.path == "/api/state":
                    run = run_path(query.get("run", [""])[0])
                    return self.respond(read_json(run / "workflow-live.json",
                                                 {"manifest": load_run(run), "status": "ready", "steps": []}))
                if url.path == "/api/report":
                    run = run_path(query.get("run", [""])[0])
                    return self.respond(read_json(run / "workflow-report.json", {}))
                return self.respond({"error": "Not found"}, 404)
            except Exception as exc:
                return self.respond({"error": str(exc)}, 400)

        def do_POST(self):
            if not self.allowed(True):
                return self.respond({"error": "Local workflow origin required"}, 403)
            try:
                size = int(self.headers.get("Content-Length", 0))
                require(0 < size <= 100000, "请求过大或为空。")
                body = json.loads(self.rfile.read(size))
                path = urlsplit(self.path).path
                if path == "/api/config":
                    return self.respond(save(body["config"], body["expected_revision"]))
                if path == "/api/workflow/lifecycle":
                    return self.respond(library.delete_workflow(
                        body["workflow_id"], body["revision"], body["deleted"]))
                if path == "/api/sessions/archive":
                    return self.respond(library.archive_sessions(body["runs"], body["archived"]))
                if path == "/api/sessions/export":
                    return self.respond(library.export_sessions(body["runs"]),
                                        kind="application/zip", download="kirocrew-sessions.zip")
                if path == "/api/workflow/import":
                    return self.respond(library.import_workflow(body["content"], body["format"]))
                if path == "/api/workflow/export":
                    return self.respond({"content": library.portable(body["config"], body["format"])})
                if path == "/api/design":
                    return self.respond(library.start_design(body["intent"], body["request_id"]))
                if path == "/api/design/app-entry":
                    job = read_json(library.design_path(body["id"]) / "job.json")
                    return self.respond({"url": api.chat_entry_url(job["slot"])})
                if path == "/api/app-entry":
                    return self.respond(app_entry(run_path(body.get("run", ""))))
                if path in {"/api/prepare", "/api/start"}:
                    request_id = body.get("request_id", "")
                    require(bool(re.fullmatch(r"[a-zA-Z0-9-]{8,80}", request_id)), "缺少请求 ID。")
                    if path == "/api/start":
                        text(body.get("input"), "用户需求", minimum=3, maximum=12000)
                    receipt_path = receipts / (request_id + ".json")
                    with intake_lock:
                        previous = read_json(receipt_path)
                        request_hash = fingerprint({"path": path, "body": body})
                        if previous:
                            require(previous["request_hash"] == request_hash, "请求 ID 冲突。")
                            return self.respond(previous)
                        # Refuse deterministic input errors before a run or
                        # intake receipt exists; confirmed retries return above.
                        definition = latest(body["workflow_id"])
                        library.assert_active(body["workflow_id"])
                        require(definition["revision"] == body["revision"], "配置已更新，请重新加载。")
                        validate_model_selection(definition["steps"])
                        if path == "/api/start":
                            require_runtime(latest(body["workflow_id"]))
                        pending = {"request_hash": request_hash, "status": "preparing"}
                        write_json(receipt_path, pending)
                        try:
                            manifest = prepare(body["workflow_id"], body["revision"])
                            pending.update(manifest=manifest, status="prepared",
                                           app_url="http://localhost:5476/chat?sid=" + manifest["slot"])
                            write_json(receipt_path, pending)
                            if path == "/api/start":
                                pending["intake"] = submit(manifest, body["input"])
                                pending["status"] = pending["intake"]["status"]
                        except Exception as exc:
                            pending.update(status="uncertain", error=str(exc))
                        write_json(receipt_path, pending)
                        return self.respond(pending)
                return self.respond({"error": "Not found"}, 404)
            except Exception as exc:
                return self.respond({"error": str(exc)}, 400)

        def log_message(self, *_args):
            pass

    print(f"Workflow MVP: http://127.0.0.1:{port}/", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("serve"); p.add_argument("--port", type=int, default=PORT)
    p = sub.add_parser("show"); p.add_argument("id")
    p = sub.add_parser("save"); p.add_argument("file"); p.add_argument("--expected-revision", type=int, required=True)
    p = sub.add_parser("export"); p.add_argument("id"); p.add_argument("--format", choices=["json", "yaml", "markdown"], default="yaml")
    p = sub.add_parser("import"); p.add_argument("file")
    p = sub.add_parser("set"); p.add_argument("id"); p.add_argument("--step", required=True)
    p.add_argument("--expected-revision", type=int, required=True)
    for field in ("tool", "model", "effort", "prompt", "name"):
        p.add_argument("--" + field)
    p = sub.add_parser("capture"); p.add_argument("run"); p.add_argument("--input-file", required=True)
    p = sub.add_parser("next"); p.add_argument("run")
    p = sub.add_parser("accept"); p.add_argument("run"); p.add_argument("--task-id", required=True)
    p = sub.add_parser("prepare"); p.add_argument("id"); p.add_argument("--revision", type=int, required=True)
    args = parser.parse_args()
    try:
        if args.command == "serve":
            return serve(args.port)
        if args.command == "show":
            result = latest(args.id)
        elif args.command == "export":
            print(library.portable(latest(args.id), args.format), end="")
            return
        elif args.command == "import":
            path = Path(args.file)
            result = library.import_workflow(path.read_text(), path.suffix.lstrip("."))
        elif args.command == "save":
            path = Path(args.file)
            result = save(parse_document(path.read_text(), path.suffix.lstrip(".")), args.expected_revision)
        elif args.command == "set":
            result = change(args.id, args.step, args.expected_revision,
                            **{f: getattr(args, f) for f in ("tool", "model", "effort", "prompt", "name")})
        elif args.command == "prepare":
            result = prepare(args.id, args.revision)
        else:
            run = run_path(args.run)
            if args.command == "capture":
                result = capture(run, Path(args.input_file).read_text())
            elif args.command == "next":
                result = next_step(run)
            else:
                result = accept(run, args.task_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, KeyError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
