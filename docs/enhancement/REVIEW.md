# Codex 安全与回归审查

当前有效结论：**ROUND-2 PASS**，F1 已修复；新候选与本轮原始输出见文末 ROUND-2。
以下 ROUND-1 内容保留为历史证据，其 FAIL 不再作为修复候选的裁决。

结论：**FAIL**。日期：2026-10-09。存在 1 个 P1 实现缺陷，两个独立回归用例均复现。
指定 65 项回归通过，不覆盖该缺陷；不能据此判定重试安全。实现必须由 task-2 属主修复，
主协调者安排修复候选复审。候选变化后，本报告不作为新候选的通过证明。

## 候选与审查范围

- 实际分支：`ui-optimize`；HEAD：`200a261821d67af8296e39172503ddb137e80cbc`，task-2 改动未提交。
- task-2 候选 SHA256：`27953dd0910b235675f9a7573e59fdece147aec116629c1689a71ba4a6224080`。
- 完整 diff SHA256：`c0ad3ae9b16566bf07699b8e5064cfcd9094c4d2f5e33f62fd83cfa50693b68f`。
- 对 10 个候选文件重新计算 SHA256，全部匹配。逐文件从 HEAD 重建 unified diff，与
  `/Users/malibo/MyDev/Kiro-Family-Spaces/experiments/kirocrew-app-poc/state/runs/workflow-20261009-113022-695cf81c237e46a79b14e425acc2ef5b/workspace/project/evidence/task-2/candidate.diff`
  全文相同。不是对另一个 checkout 或仅对交接描述作审查。
- 已依次读取本步指令、REQUEST、project.json、task-1/task-2 交接及原生返回文件、task-1 规格、
  CONTRIBUTING、README、BASELINE、增强说明、实际 diff、涉及源码与前序浏览器夹具。
- 本步只新增审查报告及回归测试，未修改上述 10 个候选文件。按当前任务调度约束，由本审查者分别
  完成 Standards / Spec 两轴检查，未自行派生其他 Agent。

源码行号索引（下文 W/J/C/P/T/V/R 均指本候选中的实际文件）：

| 索引 | 绝对路径 |
|---|---|
| W | `/Users/malibo/MyDev/Kiro-Family-Spaces/experiments/kirocrew-app-poc/state/runs/workflow-20261009-113022-695cf81c237e46a79b14e425acc2ef5b/workspace/project/workflow.py` |
| J | `/Users/malibo/MyDev/Kiro-Family-Spaces/experiments/kirocrew-app-poc/state/runs/workflow-20261009-113022-695cf81c237e46a79b14e425acc2ef5b/workspace/project/ui/workflow.js` |
| C | `/Users/malibo/MyDev/Kiro-Family-Spaces/experiments/kirocrew-app-poc/state/runs/workflow-20261009-113022-695cf81c237e46a79b14e425acc2ef5b/workspace/project/ui/workflow.css` |
| P | `/Users/malibo/MyDev/Kiro-Family-Spaces/experiments/kirocrew-app-poc/state/runs/workflow-20261009-113022-695cf81c237e46a79b14e425acc2ef5b/workspace/project/ui/workflow-progress.js` |
| T | `/Users/malibo/MyDev/Kiro-Family-Spaces/experiments/kirocrew-app-poc/state/runs/workflow-20261009-113022-695cf81c237e46a79b14e425acc2ef5b/workspace/project/test_workflow.py` |
| V | `/Users/malibo/MyDev/Kiro-Family-Spaces/experiments/kirocrew-app-poc/state/runs/workflow-20261009-113022-695cf81c237e46a79b14e425acc2ef5b/workspace/project/workflows/ui-optimize-three-stage.json` |
| R | `/Users/malibo/MyDev/Kiro-Family-Spaces/experiments/kirocrew-app-poc/state/runs/workflow-20261009-113022-695cf81c237e46a79b14e425acc2ef5b/workspace/project/test_workflow_review.py` |

## Standards

**FAIL，1 项硬约束问题：F1。** 项目贡献规范第 32 行要求“完成事件、权限等待、失败和断连都按真实状态展示”。
F1 中原生任务仍在执行，显示状态却使新增重试入口放行。两种复现为同一根因，未重复计数。
其余所查改动保留原生协议、固定工作流快照、旧交接与 Session 历史，未知模型明确标注；
未发现需要单独列出的代码异味问题。依赖未变更。Python 版本验证范围见下文。

## Spec

**FAIL，1 个 P1 实现问题 F1；另有真实环境验证缺口 C1。**

### F1 [P1] 重试门槛遗漏原生在途状态，允许与旧任务并发

定位：`/Users/malibo/MyDev/Kiro-Family-Spaces/experiments/kirocrew-app-poc/state/runs/workflow-20261009-113022-695cf81c237e46a79b14e425acc2ef5b/workspace/project/workflow.py:262`
至 269；前端同类门槛 J 170–173。相关投影 W 759–771，失败 checkpoint 写入 W 620–622。
违反规格 B.4“正在执行……会与在途任务冲突”及 AC-B5 的拒绝要求。

1. 原生任务 `done=False`，协调者提前执行 accept，得到“原生任务尚未成功结束”并保存失败检查。
   下一次真实 project 投影优先使用该检查，生成 `status=check_failed`；父协调者等待子任务时可为
   `parent_running=False`。retry 只检查显示 status，未检查 task.done，成功失效旧候选并允许新派发。
2. 同一阶段存在较旧的未完成 attempt，而最新 attempt 已失败。project 的 attempts 保留旧任务
   `done=False`，主 row 显示最新失败；retry 同样忽略 attempts 内的在途任务，成功登记。

首次隔离复现原始输出：

```text
premature accept: 原生任务尚未成功结束。
derived state: check_failed native done: False
retry ok: True dispatch tool: spawn_continue wait: False
native writes: 0
```

影响：旧工作者未终止，交接文件已经被归档/移除，next 又允许续作或重建。若协调者执行该派发，
可产生并发写入与重复模型调用。此处证明的是错误授权派发的路径，没有执行真实收费操作，
也没有证明原生服务一定接受并发续作。

建议 task-2 属主：重试前根据原生 task 和所有已知 attempts 的终态判断是否还有在途工作，
权限等待也应纳入；不能仅依赖 UI 派生状态。协调修正状态投影和前端门槛，保持既有 checkpoint。
修复后 R 38–62 的两项测试应通过，并增加对应 HTTP/前端验证。

### C1 [CONCERNS] 原生续作及真实账户 prepare 尚无执行证据

W 296–307、528–533 的续接参数与 W 548–606 的完整 checkpoint 已静态核对；
T 中使用模拟回执验证了新 ID、旧候选拒绝、重新写交接及上游/下游顺序。
前序浏览器报告明确 `native: fixtures only`，本步同样未创建真实 Agent。
因此 AC-B6 的真实同属主续作和 AC-C5 明确要求的真实账户 prepare 仍未验证。
V 29 明确“Fabel 5.1”原生 ID/可用性未核实，使用 auto 且 effort 为空，符合允许的占位规则。
不能承诺实际使用了该偏好模型。此缺口不冒充已验证通过，也不重复计为 F1。

## 逐项验收矩阵

PASS 表示本步静态检查/指定隔离测试支持该条；浏览器证据为读取 task-2 产物，未在本步重跑。

| 验收 | 结论 | 文件行号与证据 |
|---|---|---|
| AC-A1 | PASS | P 3–6、J 86–93；accepted/total 四舍五入，SVG 中显示整数百分比；T 的计算测试通过。 |
| AC-A2 | PASS | C 10、13–15；仅 running 选择器启用脉冲；其他状态静止，断连关闭。 |
| AC-A3 | PASS | C 1、7–9；灰色默认、蓝色运行/完成、红色失败、黄色授权。 |
| AC-A4 | PASS | P 11–13、C 15；role、aria-label、估算文本及 reduced-motion；前序浏览器证据支持。 |
| AC-A5 | PASS | J 47、86、153；侧栏和总览使用同一个 calculate，done/total 与百分比同源。 |
| AC-A6 | PASS | P 为原生 DOM/SVG；没有新增轮询/第三方依赖；静态资源由 W 933–938 同源提供。 |
| AC-B1 | 部分 / F1 | J 170–173；三种目标状态显示按钮，但原生在途工作被 check_failed 掩盖时也会放行。 |
| AC-B2 | PASS | W 309–320、336–341；旧 accepted 和交接归档后移除；指定回归验证实物。 |
| AC-B3 | PASS | W 285–345；目标及下游失效，上游保留；invalidated 列出有旧 accepted 的下游。 |
| AC-B4 | PASS | W 466–537；返回被重试阶段的原生派发字段，已有新回执时 wait。 |
| AC-B5 | FAIL / F1 | W 262–269；普通 running/pending/授权快照被拒绝，但两种仍在途组合未拒绝。 |
| AC-B6 | 部分 / C1 | W 296–307、528–533、548–606；原生续接优先与检查口径有代码/夹具证据，真实执行未验证。 |
| AC-B7 | PASS | W 247–253、333–336；同 ID 同阶段回放、换阶段冲突；同 ID 并发测试通过。 |
| AC-C1 | PASS | V 三个步骤；指定回归通过 validate、保存及模拟 prepare。 |
| AC-C2 | PASS | V 10、18、26；kiro → codex → claude。 |
| AC-C3 | PASS | V 27、29；auto 与未核实偏好说明，没有虚构模型 ID。 |
| AC-C4 | PASS | V 28；auto 的 effort 为空。 |
| AC-C5 | 未验证 / C1 | T 450–471 为模拟原生 API；真实账户 prepare 未执行。 |

原子 retry-state 替代逐阶段文件是可接受的实现差异；读者通过排除旧 Task ID 保持逻辑失效。
未改旧 Pipeline、旧轮询端点和固定四阶段配置。进度轮询仍为 2 秒，列表刷新仍为 10 秒（J 459）。

## 安全与健壮性核查

- HTTP 28 个反例通过：非法 JSON 值类型、缺字段、run 越界/不存在/指向外部的符号链接、
  stage 越界/未知/注入字符串、request_id 越界/类型/注入，以及 Origin/Host/自定义头/Content-Type。
  返回预期 400/403；原 accepted 和 workspace 文件 hash 未变；原生写调用为零。
- W 208–216 resolve 后限制 run 的父目录；W 244–246 限制 stage/request_id；W 911–915 同源门槛复用。
  注入字符串没有进入 Shell，next_hint 的本地命令参数使用 shlex.quote。
- W 226–231 的运行锁串行化 retry/next/accept 和成功的观察器发布；指定并发幂等测试通过。
  该锁不覆盖 KiroCrew 原生派发，不能视作原生 exactly-once 保证；F1 为已复现的在途判断缺口。
- 旧候选排除、新回执匹配、父会话/工具/后端/模型/Effort、BLOCKED 和新交接检查仍存在。
  在所测路径中没有通过 HTTP 直接写入成功 checkpoint 的入口；HTTP 200 仅表示登记重试。
- 本步未调用真实 spawn_run/spawn_continue、未读取个人模型会话日志、未发送模型任务或修改配置。

## 实际命令与输出

在项目 cwd 使用既有虚拟环境：Python 3.14.7、Node v25.4.0。声明依赖已安装，无需新增依赖。
贡献指南列出的 Python 3.12/3.13 未在本步验证；不将本机结果等同于支持版本矩阵通过。

```text
$ source .venv/bin/activate
$ python -m unittest test_workflow test_workflow_library test_pipeline test_reload_gateway -q
Workflow MVP: http://127.0.0.1:53939/
----------------------------------------------------------------------
Ran 65 tests in 1.272s

OK
exit=0

$ node --check ui/*.js
exit=0
$ node --check ui/crew-entry.js
exit=0
$ node --check ui/live.js
exit=0
$ node --check ui/workflow-progress.js
exit=0
$ node --check ui/workflow-view.js
exit=0
$ node --check ui/workflow.js
exit=0
$ git diff --check
exit=0
```

新增审查测试命令及真实输出（保留失败，不使用 expectedFailure 隐藏）：

```text
$ source .venv/bin/activate
$ python -m unittest test_workflow_review -v
test_http_retry_rejects_untrusted_origins_and_malformed_identifiers (test_workflow_review.RetryReviewTests.test_http_retry_rejects_untrusted_origins_and_malformed_identifiers) ... Workflow MVP: http://127.0.0.1:56231/
ok
test_running_older_attempt_prevents_retry_of_latest_failure (test_workflow_review.RetryReviewTests.test_running_older_attempt_prevents_retry_of_latest_failure) ... FAIL
test_running_task_remains_non_retryable_after_early_checkpoint (test_workflow_review.RetryReviewTests.test_running_task_remains_non_retryable_after_early_checkpoint) ... FAIL

======================================================================
FAIL: test_running_older_attempt_prevents_retry_of_latest_failure (test_workflow_review.RetryReviewTests.test_running_older_attempt_prevents_retry_of_latest_failure)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/malibo/MyDev/Kiro-Family-Spaces/experiments/kirocrew-app-poc/state/runs/workflow-20261009-113022-695cf81c237e46a79b14e425acc2ef5b/workspace/project/test_workflow_review.py", line 62, in test_running_older_attempt_prevents_retry_of_latest_failure
    self.assert_retry_rejected(run, "review-older-attempt")
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/malibo/MyDev/Kiro-Family-Spaces/experiments/kirocrew-app-poc/state/runs/workflow-20261009-113022-695cf81c237e46a79b14e425acc2ef5b/workspace/project/test_workflow_review.py", line 32, in assert_retry_rejected
    with self.assertRaises(ValueError, msg="retry accepted while native work is still running"):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: ValueError not raised : retry accepted while native work is still running

======================================================================
FAIL: test_running_task_remains_non_retryable_after_early_checkpoint (test_workflow_review.RetryReviewTests.test_running_task_remains_non_retryable_after_early_checkpoint)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/malibo/MyDev/Kiro-Family-Spaces/experiments/kirocrew-app-poc/state/runs/workflow-20261009-113022-695cf81c237e46a79b14e425acc2ef5b/workspace/project/test_workflow_review.py", line 49, in test_running_task_remains_non_retryable_after_early_checkpoint
    self.assert_retry_rejected(run, "review-early-checkpoint")
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/malibo/MyDev/Kiro-Family-Spaces/experiments/kirocrew-app-poc/state/runs/workflow-20261009-113022-695cf81c237e46a79b14e425acc2ef5b/workspace/project/test_workflow_review.py", line 32, in assert_retry_rejected
    with self.assertRaises(ValueError, msg="retry accepted while native work is still running"):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: ValueError not raised : retry accepted while native work is still running

----------------------------------------------------------------------
Ran 3 tests in 0.752s

FAILED (failures=2)
HTTP retry rejection cases: 28; native writes: 0
exit=1
```

隔离复制打包白名单后执行构建，原检出未生成 ZIP；临时构建目录随验证退出清理：

```text
candidate_files_still_match: True
candidate_sha256: 27953dd0910b235675f9a7573e59fdece147aec116629c1689a71ba4a6224080
candidate_diff_matches_actual_baseline_to_worktree: True
$ python build_pipeline_kit.py [isolated allowlist copy]
/Users/malibo/.kiro/crew/scratch/runtime-91b2869e/octopus-review-package-woyolyrk/kirocrew-octopus-kit.zip · 492657 bytes
exit=0
package_file_bytes_match: 91
review_test_sha256: a54b08336904846b7168bb96fed2a058cd3ddd57450010c95439e90bbf169302
review_test_lines: 142
```

最初只读命令因 `sandbox_apply: Operation not permitted` 退出 71，按工具审批流程重试后成功。
所有测试服务均在 finally 中关闭；未提交、推送、创建 PR、部署或发布。

## 交回协调者

由 task-2 实现属主修复 F1，保留此审查与失败测试；不要由 review worker 修改核心实现。
修复候选需重新记录 hash，重跑指定 65 项及新增 3 项测试、JS 检查和相关 UI 验证，再复审。
真实原生续接、任务新 ID/同属主会话/模型/Effort/checkpoint 和真实账户 prepare 由后续验证阶段补齐。
当前审查任务已完成，不是环境阻塞；FAIL 是对上述固定候选的缺陷裁决。

## ROUND-2 复审 — 2026-10-09

**PASS。** F1 两条错误放行路径均已封闭；本轮未发现新增阻断问题。此结论是修复代码的安全与回归复审，
不代表真实原生 Agent E2E、真实账户 prepare 或 Fabel 5.1 可用性通过；ROUND-1 的 C1 验证边界保留。

### 新候选锚点

- 分支仍为 ui-optimize；HEAD 仍为 200a261821d67af8296e39172503ddb137e80cbc。
- task-2 FIX-ROUND-1 输入候选（12 文件）SHA256：5da9b270de303c7b8bc1ea0e5a7eed9911af822a81ff108097c137ae40cf4980。
- 输入候选完整 diff SHA256：337364b3fb5d2ca9543c0d6634a3cac3b79027427825350c195644acdd2553ca。
- 与 ROUND-1 相同的 10 文件口径：旧候选 27953dd0910b235675f9a7573e59fdece147aec116629c1689a71ba4a6224080；
  新实现候选 **3b47ded3aaff028920a0016a083dd9ef8e7a3bd1c43786c373e888a7ddd3af0d**。
- 12 个输入文件及其从 HEAD 重建的 diff 全部匹配属主证据。12 文件集合含上一版审查报告，
  故该输入 hash 描述复审开始时的快照；本轮追加报告后仍以固定 10 文件的新实现 hash 锚定代码。
- 唯一实现变化为 W 262–268 新增 7 行。W 的 SHA256 从
  d233b9d223121c4c895bbf8f67935081cdf10907806da780b483017c97f063fc 变为
  **fcd9e6566d7f421a658b85493ff14fe7e169966987f73cc3a4713b0bfed90a13**。
  从现文件移除该 7 行后，其 hash 精确等于旧值，其余 9 个原候选文件 hash 不变。
- 审查测试 R 未改动，SHA256 仍为 a54b08336904846b7168bb96fed2a058cd3ddd57450010c95439e90bbf169302。

### 修复逻辑与验收影响

- W 262–268 在运行锁内遍历所有阶段，原生 task 及所有 attempts 必须明确 done is True。
  因此提前 checkpoint 产生 check_failed 不能掩盖 done=False，最新失败也不能掩盖旧 attempt 在途。
- W 265 的合并仅限相同 ID；字典顺序使 attempt 自身的显式 done=False/None 覆盖 task 的值。
  不同 ID 的缺失终态不会借用当前 task 的完成证据，数值 1 也不被当作布尔 True。
  独立检查 8 个边界用例全部通过；拒绝时未写重试日志，原交接保持不变。
- 同源校验、run 路径约束、幂等回放、运行锁、原生回执校验、上下游失效和 checkpoint 均未修改。
  28 个 HTTP 拒绝用例与原并发/幂等/归档/重新 checkpoint 回归仍通过；未触发原生写调用。
- AC-B5 更新为 PASS。AC-B1 的前端显示规则未改，check_failed 按钮可能仍显示，但原生未结束时
  后端拒绝请求并返回错误，不再允许登记重试。前端提前置灰不是本次新增能力。
- AC-B2/B3/B4/B7 仍成立；AC-A1–A6、AC-C1–C4 按未变更的文件沿用上轮核查。
  AC-B6 的真实原生续作与 AC-C5 的真实账户 prepare 仍未验证。本轮未重跑浏览器或打包。

### 本轮真实执行输出

```text
$ source .venv/bin/activate && python -m unittest test_workflow_review -v
test_http_retry_rejects_untrusted_origins_and_malformed_identifiers (test_workflow_review.RetryReviewTests.test_http_retry_rejects_untrusted_origins_and_malformed_identifiers) ... Workflow MVP: http://127.0.0.1:55096/
ok
test_running_older_attempt_prevents_retry_of_latest_failure (test_workflow_review.RetryReviewTests.test_running_older_attempt_prevents_retry_of_latest_failure) ... ok
test_running_task_remains_non_retryable_after_early_checkpoint (test_workflow_review.RetryReviewTests.test_running_task_remains_non_retryable_after_early_checkpoint) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.673s

OK
HTTP retry rejection cases: 28; native writes: 0
exit=0
$ source .venv/bin/activate && python -m unittest test_workflow test_workflow_library test_pipeline test_reload_gateway -q
Workflow MVP: http://127.0.0.1:55144/
----------------------------------------------------------------------
Ran 65 tests in 1.255s

OK
exit=0
$ node --check ui/*.js
exit=0
$ for script in ui/*.js; do node --check "$script" || exit; done
exit=0
$ git diff --check
exit=0
```

额外的 ID-match 隔离断言输出（调用实际 retry_stage，未修改或扩充 R）：

```text
same-id-only: allowed (expected)
different-id-only: rejected (expected)
same-id-false: rejected (expected)
same-id-null: rejected (expected)
same-id-number-one: rejected (expected)
same-id-true: allowed (expected)
different-id-true: allowed (expected)
task-false-attempt-true: rejected (expected)
ID-match guard: 8/8 passed; native writes: 0
exit=0
```

本轮仅更新本审查报告与交接；实现和测试文件保持属主修复后的内容。F1 关闭，可进入后续验证阶段。
