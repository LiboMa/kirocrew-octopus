"""MVP invariants: immutable runs, native parameter contracts and truthful gates."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import socket
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

import workflow as w

EXAMPLE = json.loads((w.ROOT / "workflows/development.json").read_text())


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patchers = [patch.object(w, name, self.root / path) for name, path in (
            ("DEFINITIONS", "definitions"), ("VERSIONS", "versions"), ("RUNS", "runs"))]
        self.patchers.append(patch.object(w, "runtime_features", return_value=["codex_effort_pair_v1"]))
        self.patchers.append(patch.object(w, "MODEL_CACHE", self.root / "provider_models.json"))
        for p in self.patchers:
            p.start()
        w.write_json(w.MODEL_CACHE, {"claude_code": ["global.anthropic.claude-sonnet-4-6",
                                                    "global.anthropic.claude-opus-5"],
                                     "acp": ["kiro-native-model"]})
        self.definition = w.save(copy.deepcopy(EXAMPLE), 0)

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.temp.cleanup()

    def prepare(self):
        calls = []
        def request(path, body):
            calls.append((path, body))
            return {"key": body["name"]} if path == "/api/chat/slots" else {"ok": True}
        with patch.object(w.api, "request", side_effect=request):
            manifest = w.prepare("development", 1)
        self.assertEqual([c[0] for c in calls], [
            "/api/chat/slots", f"/api/chat/slots/{manifest['slot']}/context"])
        return manifest, Path(manifest["run"])

    def test_versions_and_running_snapshot_are_immutable(self):
        manifest, run = self.prepare()
        before = (run / "workflow-run.json").read_bytes()
        changed = w.change("development", "review", 1, effort="low")
        self.assertEqual(changed["revision"], 2)
        self.assertEqual(w.latest("development")["steps"][2]["effort"], "low")
        self.assertEqual((run / "workflow-run.json").read_bytes(), before)
        self.assertEqual(w.load_run(run)["workflow"]["steps"][2]["effort"], "high")
        with self.assertRaisesRegex(ValueError, "版本冲突"):
            w.change("development", "review", 1, effort="max")
        self.assertEqual(len(list((w.VERSIONS / "development").glob("*.json"))), 2)

    def test_model_and_tool_constraints_do_not_silently_drop_effort(self):
        for fields in [{"tool": "gemini"}, {"tool": "opencode", "effort": "high"},
                       {"model": "auto", "effort": "high"},
                       {"model": "claude-haiku-4.5", "effort": "high"},
                       {"model": "model[high]"}]:
            value = copy.deepcopy(EXAMPLE)
            value["steps"][0].update(fields)
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                w.validate(value)

    def test_dispatch_preserves_every_native_parameter_and_user_input(self):
        _, run = self.prepare()
        w.capture(run, "这是用户原始需求。\n第二行。")
        next_call = w.next_step(run)
        self.assertEqual(next_call["spawn"]["agent"], "poc-kiro")
        self.assertEqual(next_call["spawn"]["model"], "auto")
        self.assertEqual(next_call["spawn"]["reasoning_effort"], "")
        self.assertFalse(next_call["spawn"]["include_memory"])
        self.assertIn("这是用户原始需求。\n第二行。", next_call["spawn"]["task"])
        with self.assertRaisesRegex(ValueError, "需求已冻结"):
            w.capture(run, "不要改成本次的另一个需求")

    def test_native_chat_submission_is_exact_and_ambiguous_send_not_retried(self):
        manifest, run = self.prepare()
        with patch.object(w.api, "request", side_effect=TimeoutError("late")) as request:
            self.assertEqual(w.submit(manifest, "用户请求一个计时器。")["status"], "uncertain")
            with self.assertRaises(ValueError):
                w.submit(manifest, "用户请求一个计时器。")
        request.assert_called_once_with("/api/chat?ws=1", {
            "slot": manifest["slot"], "message": "用户请求一个计时器。"})

    def test_snapshot_tampering_is_detected(self):
        manifest, run = self.prepare()
        manifest["workflow"]["steps"][0]["tool"] = "claude"
        w.write_json(run / "workflow-run.json", manifest)
        with self.assertRaisesRegex(ValueError, "快照已被修改"):
            w.load_run(run)

    def test_old_gateway_cannot_silently_run_explicit_codex_effort(self):
        manifest, run = self.prepare()
        w.capture(run, "这个运行要求明确设置 Codex 的 Effort。")
        with patch.object(w, "runtime_features", return_value=[]):
            with self.assertRaisesRegex(ValueError, "尚未加载"):
                w.next_step(run)
            with patch.object(w.api, "request") as request, self.assertRaises(ValueError):
                w.submit(manifest, "这个运行要求明确设置 Codex 的 Effort。")
            request.assert_not_called()

    def test_accept_requires_native_identity_not_agent_self_report(self):
        manifest, run = self.prepare()
        w.capture(run, "验证这次任务的真实后端。")
        step = manifest["workflow"]["steps"][0]
        task = {"id": "abc123", "parent": manifest["parent"], "done": True,
                "agent": "poc-kiro", "result": "我是 Kiro，已完成。状态：无 BLOCKED。"}
        row = {**step, "task": task, "route": {"actual_backend": "claude"},
               "requested_model": "auto", "resolved_model": "",
               "native_request": {"task_id": "abc123", "reasoning_effort": ""},
               "effort_observation": {"value": None, "source": "not_reported"}}
        snapshot = {"connected": True, "at": time.time(), "steps": [row]}
        w.write_json(run / "workflow-live.json", snapshot)
        (run / "workspace/plan-handoff.md").write_text("实际交接")
        with self.assertRaisesRegex(ValueError, "后端"):
            w.accept(run, "abc123")
        row["route"]["actual_backend"] = "kiro"
        task["parent"] = "dashboard:other"
        w.write_json(run / "workflow-live.json", snapshot)
        with self.assertRaisesRegex(ValueError, "父会话"):
            w.accept(run, "abc123")
        task["parent"] = manifest["parent"]
        w.write_json(run / "workflow-live.json", snapshot)
        self.assertTrue(w.accept(run, "abc123")["ok"])
        next_call = w.next_step(run)
        self.assertEqual(next_call["step"], "code")
        self.assertEqual(next_call["spawn"]["reasoning_effort"], "medium")
        self.assertEqual(next_call["spawn"]["model"], "global.anthropic.claude-sonnet-4-6")
        self.assertIn("code-instructions.md", next_call["spawn"]["task"])
        self.assertIn("我是 Kiro，已完成。", (run / "workspace/plan-result.txt").read_text())

    def test_empty_native_response_cannot_be_accepted_as_delivery(self):
        manifest, run = self.prepare()
        w.capture(run, "测试空返回不能变成已完成。")
        step = manifest["workflow"]["steps"][0]
        row = {**step, "task": {"id": "abc123de", "parent": manifest["parent"],
                               "done": True, "result": "_No response._"}}
        w.write_json(run / "workflow-live.json",
                     {"connected": True, "at": time.time(), "steps": [row]})
        (run / "workspace/plan-handoff.md").write_text("文件存在也不足以接受空返回。")
        with self.assertRaisesRegex(ValueError, "未返回完成结果"):
            w.accept(run, "abc123de")

    def test_model_matching_uses_native_id_not_fuzzy_family_match(self):
        self.assertTrue(w.model_matches("openai.gpt-6-astra", "openai.gpt-6-astra[high]"))
        self.assertFalse(w.model_matches("openai.gpt-6-astra", "openai.gpt-6-sol[high]"))
        self.assertFalse(w.model_matches("claude-opus-5", "global.anthropic.claude-opus-5"))

    def test_unknown_claude_model_is_refused_before_session_or_receipt_creation(self):
        definition = copy.deepcopy(EXAMPLE)
        definition["steps"][1]["model"] = "global.anthropic.claude-opus-5-5"
        # Portable definitions can be stored, but this host cannot silently run
        # a requested model it has not seen this adapter advertise.
        w.save(definition, 1)
        with patch.object(w.api, "request") as request:
            with self.assertRaisesRegex(ValueError, "Claude Code 当前公布"):
                w.prepare("development", 2)
            request.assert_not_called()
        self.assertFalse(w.RUNS.exists())

    def test_model_recheck_before_dispatch_preserves_existing_run(self):
        _, run = self.prepare()
        before = (run / "workflow-run.json").read_bytes()
        w.capture(run, "继续已有运行，但模型候选已变化。")
        w.write_json(run / "accepted/plan.json", {"task_id": "plan-1", "result": "计划完成"})
        w.write_json(w.MODEL_CACHE, {"claude_code": ["another-model"]})
        with self.assertRaisesRegex(ValueError, "Claude Code 当前公布"):
            w.next_step(run)
        self.assertEqual((run / "workflow-run.json").read_bytes(), before)
        self.assertFalse((run / "dispatch-code.json").exists())
        w.validate_model_selection([{"tool": "claude", "model": "auto", "name": "默认"}])

    def test_model_candidates_are_scoped_to_the_actual_harness(self):
        self.assertEqual(w.advertised_models("kiro"), ["kiro-native-model"])
        self.assertNotIn("kiro-native-model", w.advertised_models("claude"))
        w.write_json(w.MODEL_CACHE, {})
        with self.assertRaisesRegex(ValueError, "还没有 Claude Code"):
            w.validate_model_selection([{"tool": "claude", "model": "opus", "name": "编码"}])

    def test_model_check_failure_does_not_claim_the_coding_task_failed(self):
        definition = copy.deepcopy(EXAMPLE)
        definition["steps"][0].update(tool="claude", model="global.anthropic.claude-opus-5")
        w.save(definition, 1)
        with patch.object(w.api, "request", side_effect=lambda path, body:
                          {"key": body["name"]} if path == "/api/chat/slots" else {"ok": True}):
            manifest = w.prepare("development", 2)
        run = Path(manifest["run"])
        task = {"id": "model-check", "parent": manifest["parent"], "agent": "poc-claude",
                "done": True, "result": "测试实际通过。", "task": w.marker(manifest, "plan")}
        (run / "checks").mkdir()
        w.write_json(run / "checks/model-check.json",
                     {"passed": False, "error": "实际模型与配置不匹配。"})
        original_read = w.read_json
        def read(path, default=None):
            if str(path).endswith("/subagents/model-check/state.json"):
                return {"resolved_model": "global.anthropic.claude-sonnet-4-6",
                        "requested_model": "global.anthropic.claude-opus-5"}
            return original_read(path, default)
        with patch.object(w, "read_json", side_effect=read), patch.object(
                w, "dispatch_receipts", return_value={}), patch.object(
                w, "route_for", return_value={"actual_backend": "claude"}):
            projected = w.project(run, [task], {"running": False}, [])
        self.assertEqual(projected["status"], "check_failed")
        self.assertEqual(projected["steps"][0]["status"], "check_failed")
        self.assertTrue(projected["steps"][0]["model_mismatch"])
        self.assertTrue(projected["steps"][0]["task"]["done"])
        self.assertFalse((run / "accepted/plan.json").exists())

    def test_app_entry_bootstrap_does_not_change_session_or_persist_token(self):
        manifest, run = self.prepare()
        before = (run / "workflow-run.json").read_bytes()
        with patch.object(w.api, "token", return_value="test-token") as token:
            entry = w.app_entry(run)
        token.assert_called_once_with(5476, ttl="8h")
        self.assertIn("sid=" + manifest["slot"], entry["url"])
        self.assertIn("token=test-token", entry["url"])
        self.assertEqual(entry["expires_in"], 300)
        self.assertEqual((run / "workflow-run.json").read_bytes(), before)
        self.assertNotIn("test-token", (run / "app-context.txt").read_text())

    def test_app_entry_http_requires_same_origin_post_and_existing_run(self):
        manifest, _ = self.prepare()
        (self.root / "state").mkdir()
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        ready = threading.Event()
        holder = {}
        def create(address, handler):
            holder["server"] = ThreadingHTTPServer(address, handler)
            ready.set()
            return holder["server"]
        def call(path, *, method="POST", origin=None, host=None, body=None):
            headers = {"Content-Type": "application/json", "X-Workflow-MVP": "1"}
            if origin:
                headers["Origin"] = origin
            if host:
                headers["Host"] = host
            request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method,
                data=json.dumps(body or {"run": manifest["id"]}).encode() if method == "POST" else None,
                headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=3) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                with error:
                    return error.code, json.load(error)
        with patch.object(w, "ROOT", self.root), patch.object(w, "observe", return_value=None), \
                patch.object(w, "ThreadingHTTPServer", side_effect=create), \
                patch.object(w.api, "chat_entry_url", return_value="native-auth-link") as mint:
            thread = threading.Thread(target=w.serve, args=(port,), daemon=True)
            thread.start()
            self.assertTrue(ready.wait(3))
            try:
                origin = f"http://127.0.0.1:{port}"
                self.assertEqual(call("/api/app-entry")[0], 403)
                self.assertEqual(call("/api/app-entry", origin="http://unrelated.test")[0], 403)
                self.assertEqual(call("/api/app-entry", method="GET")[0], 404)
                self.assertEqual(call("/api/app-entry", origin=origin, host=f"localhost:{port}")[0], 403)
                self.assertEqual(call("/api/app-entry", origin=origin, body={"run": "../outside"})[0], 400)
                mint.assert_not_called()
                self.assertEqual(call("/api/app-entry", origin=origin)[0], 200)
                mint.assert_called_once_with(manifest["slot"])
                w.change("development", "code", 1, model="global.anthropic.claude-opus-5-5")
                body = {"workflow_id": "development", "revision": 2,
                        "request_id": "qa-invalid-model", "input": "不应创建这个任务。"}
                with patch.object(w.api, "request") as dispatch:
                    self.assertEqual(call("/api/start", origin=origin, body=body)[0], 400)
                    dispatch.assert_not_called()
                self.assertFalse((self.root / "state/workflow-intake/qa-invalid-model.json").exists())
                # A confirmed prior request remains retrievable after a newer
                # config is saved; it must never create a second native run.
                body.update(revision=1, request_id="qa-confirmed-retry")
                w.write_json(self.root / "state/workflow-intake/qa-confirmed-retry.json",
                             {"status": "accepted", "request_hash": w.fingerprint({
                                 "path": "/api/start", "body": body})})
                self.assertEqual(call("/api/start", origin=origin, body=body)[1]["status"], "accepted")
            finally:
                holder["server"].shutdown()
                holder["server"].server_close()
                thread.join(3)

    def test_public_config_keeps_model_and_effort_separate(self):
        definition = w.validate(EXAMPLE)
        self.assertEqual(definition["steps"][2]["model"], "openai.gpt-6-astra")
        self.assertEqual(definition["steps"][2]["effort"], "high")

    def test_long_input_and_history_use_files_within_native_task_limit(self):
        _, run = self.prepare()
        requirement = "完整需求" * 2500
        w.capture(run, requirement)
        w.write_json(run / "accepted/plan.json",
                     {"task_id": "native-1", "result": "真实前序结果" * 3000})
        dispatch = w.next_step(run)
        self.assertLessEqual(len(dispatch["spawn"]["task"]), 5000)
        self.assertIn(requirement, (run / "workspace/code-instructions.md").read_text())
        self.assertEqual((run / "workspace/plan-result.txt").read_text(), "真实前序结果" * 3000 + "\n")

    def test_step_ids_are_unique_and_no_shell_or_path_injection(self):
        value = copy.deepcopy(EXAMPLE)
        value["steps"][0]["id"] = "../outside"
        with self.assertRaises(ValueError):
            w.validate(value)
        value["steps"][0]["id"] = value["steps"][1]["id"]
        with self.assertRaisesRegex(ValueError, "不可重复"):
            w.validate(value)

    def test_preview_cannot_escape_or_read_hidden_runtime_files(self):
        _, run = self.prepare()
        workspace = run / "workspace"
        (workspace / "index.html").write_text("42")
        (workspace / ".private.json").write_text("not public")
        (workspace / "link.json").symlink_to(run / "workflow-run.json")
        self.assertEqual(w.preview_file(run, "index.html"), (workspace / "index.html").resolve())
        for path in ("../workflow-run.json", "%2e%2e/workflow-run.json", ".private.json", "link.json"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                w.preview_file(run, path)

    def test_queue_receipt_is_shown_before_native_task_enters_running_list(self):
        manifest, run = self.prepare()
        receipts = {"plan": {"task_id": "abc123", "reasoning_effort": ""}}
        with patch.object(w, "dispatch_receipts", return_value=receipts):
            projected = w.project(run, [], {"running": False}, [])
        self.assertEqual(projected["status"], "running")
        self.assertEqual(projected["steps"][0]["status"], "submitted")
        self.assertIsNone(projected["steps"][0]["task"])
        self.assertIsNone(projected["steps"][0]["route"])

    def test_real_tool_event_extracts_effort_and_task_identity(self):
        manifest, _ = self.prepare()
        event = {"role": "tool", "meta": {"tool_name": "@kirocrew-core/spawn_run",
                 "tool_call_id": "native-call-1", "input": json.dumps({
                     "task": w.marker(manifest, "review"), "agent": "poc-codex",
                     "model": "openai.gpt-6-astra", "reasoning_effort": "high"}),
                 "output": "Spawned 1 subagent(s):\n  abc123de (poc-codex): Review"}}
        with patch.object(Path, "exists", return_value=True), patch.object(
            Path, "read_text", return_value=json.dumps(event)):
            receipts = w.dispatch_receipts(manifest)
        self.assertEqual(receipts["review"]["task_id"], "abc123de")
        self.assertEqual(receipts["review"]["reasoning_effort"], "high")

    def test_chat_permission_is_visible_when_global_approvals_are_empty(self):
        _, run = self.prepare()
        meta = {"approval_id": "native-permission", "tool_title": "Running: spawn_run"}
        parent = {"running": True, "messages": [{"role": "permission", "meta": meta}]}
        with patch.object(w, "dispatch_receipts", return_value={}):
            projected = w.project(run, [], parent, [])
            self.assertEqual(projected["status"], "awaiting_approval")
            self.assertEqual(projected["approvals"][0]["source"], "native App permission event")
            meta["resolved"] = "approved"
            self.assertEqual(w.project(run, [], parent, [])["approvals"], [])
            native = {"id": "1", "source": "subagent", "tool": "Read file",
                      "slot": w.load_run(run)["slot"]}
            other = {**native, "id": "2", "slot": "unrelated-user-conversation"}
            projected = w.project(run, [], {"running": False}, [native, other])
            self.assertEqual(projected["approvals"], [native])
            self.assertEqual(projected["status"], "awaiting_approval")

    def test_verified_evidence_survives_gateway_memory_reset(self):
        manifest, run = self.prepare()
        accepted = {"task_id": "abc123de", "result": "Verified result",
                    "route": {"actual_backend": "kiro", "native_session_id": "native-1"},
                    "requested_model": "auto", "resolved_model": "",
                    "effort_observation": {"value": None, "source": "not_reported"},
                    "native_request": {"task_id": "abc123de", "reasoning_effort": ""}}
        w.write_json(run / "accepted/plan.json", accepted)
        with patch.object(w, "dispatch_receipts", return_value={}):
            row = w.project(run, [], {"running": False}, [])["steps"][0]
        self.assertEqual(row["status"], "accepted")
        self.assertEqual(row["task"]["parent"], manifest["parent"])
        self.assertEqual(row["route"], accepted["route"])
        self.assertEqual(row["evidence_source"], "persisted verified checkpoint")

    def test_continuation_tracks_new_task_without_losing_original_parameters(self):
        manifest, run = self.prepare()
        w.capture(run, "验证续作继承原生请求并单独核对新任务。")
        events = [
            {"role": "tool", "meta": {"tool_name": "spawn_run", "tool_call_id": "first",
             "input": json.dumps({"task": w.marker(manifest, "plan"), "agent": "poc-kiro",
                                  "model": "auto", "reasoning_effort": "", "cwd": str(run / "workspace")}),
             "output": "Spawned 1 subagent(s):\n  abc123de (poc-kiro): plan"}},
            {"role": "tool", "meta": {"tool_name": "spawn_continue", "tool_call_id": "followup",
             "input": json.dumps({"conversation": "abc123de", "task": "补齐交接文件"}),
             "output": "Continued conversation abc123de as run def456ab."}},
        ]
        # Native event persistence may repeat the final tool event.
        events.append(events[-1])
        with patch.object(Path, "exists", return_value=True), patch.object(
                Path, "read_text", return_value="\n".join(map(json.dumps, events))):
            receipts = w.dispatch_receipts(manifest)
        receipt = receipts["plan"]
        self.assertEqual(receipt["task_id"], "def456ab")
        self.assertEqual(receipt["conversation"], "abc123de")
        self.assertEqual(receipt["agent"], "poc-kiro")
        self.assertEqual(receipt["model"], "auto")
        old = {"task_id": "abc123de", "result": "_No response._"}
        w.write_json(run / "accepted/plan.json", old)
        task = {"id": "def456ab", "parent": manifest["parent"], "agent": "poc-kiro",
                "done": True, "result": "实际补齐交接", "task": "补齐交接文件", "started": 2}
        with patch.object(w, "dispatch_receipts", return_value=receipts), patch.object(
                w, "route_for", return_value={"actual_backend": "kiro", "crew_session_key": "subagent:abc123de"}):
            projected = w.project(run, [task], {"running": False}, [])
            self.assertEqual(projected["steps"][0]["task"]["id"], "def456ab")
            self.assertEqual(projected["steps"][0]["status"], "awaiting_check")
            self.assertEqual(w.next_step(run)["step"], "plan")
            projected["steps"][0]["requested_model"] = "auto"
            w.write_json(run / "workflow-live.json", projected)
            (run / "workspace/plan-handoff.md").write_text("新一轮的真实交接。")
            self.assertTrue(w.accept(run, "def456ab")["ok"])
        self.assertEqual(w.read_json(run / "accepted/previous/plan-abc123de.json"), old)


if __name__ == "__main__":
    unittest.main(verbosity=2)
