# Session 进度与阶段重试

基线：`ui-optimize`，commit `200a261821d67af8296e39172503ddb137e80cbc`。
按 task-1 REQUIREMENTS 的 AC-A/B/C 实现。左侧 Session 属于 Workflow Studio：
实际入口为 `workflow.py` 和 `ui/workflow.*`。旧 `pipeline.py`、`ui/live.*`、
`/state.json` 及四工具兼容性工作流未改动。

## 使用

- 左侧环形数值和总览共用 `round(accepted / total * 100)`；无阶段内部进度推测。
  环的可访问名称包含百分比和“按阶段完成度估算”。仅 running 态闪烁；
  断连、完成、失败、待执行及减少动态效果设置下静止。
- 在任务详情选择失败、交接未通过或已交接阶段，点击“重试此阶段”或“优化重试”。
  下游已完成结论同时失效，旧回执和交接保留。快照过期、权限等待或存在在途任务时拒绝重试。
- 点击“复制续作指令”，在此 Session 的原 KiroCrew 对话中继续执行。
  工作台只登记重试；真实派发仍由原生协调者执行，不能将按钮响应视为执行成功。
  本期优化指按冻结需求重新执行已完成阶段。需求、工具或模型变更仍通过下一版工作流创建新 Session。

## 重试契约和证据

`POST /api/retry`：
`{"run":"<run-id>","stage":"<step-id>","request_id":"<8–80 位字母数字短横线>"}`
要求同源 Origin、`X-Workflow-MVP: 1`、JSON Content-Type，响应包含
`ok/run/stage/request_id/invalidated/next_hint`。同一请求 ID 原样返回首次结果；
同一 ID 换阶段报错。不同 ID 的重复请求由 pending 状态门槛拒绝。

- 运行级文件锁串行化重试、next、accept 和观察器发布。
- `retry-state.json` 是单次原子失效记录，包含各阶段旧 Task 排除集合和幂等响应。
  使用一个文件替代逐阶段写 `retry-<stage>.json`，避免下游只失效一部分的可见窗口。
- 旧 accepted 回执保存在 `accepted/previous/<stage>-<request_id>.json`；
  旧交接与返回保存在 `retry-history/<request_id>/<stage>/`。
  原始 Session、源码、原生返回和工作流快照均保留。
- `next` 仍提供兼容的 `spawn` 参数，额外提供 `tool`。
  原请求和属主后端证据可对应时输出 `tool=spawn_continue`、
  `continue={conversation,task}`；否则输出 `tool=spawn_run`。
  续接继承固定模型/Effort，重建参数仍拆分 `model` 与 `reasoning_effort`。
  已有新原生回执时输出 `wait=true/task_id`，协调者不得重复派发。
- 仅在原生明确拒绝续接、且确认未派发时，可使用同一 `spawn` 参数重建；
  超时或结果不明确时先核实，不自动重发。
- 新 Task 必须经过既有 `accept` 检查：父会话、属主工具、实际后端、模型、
  Effort、原生回执、返回内容和交接文件。旧候选、被更新回执替代的 Task、
  旧交接文件不能通过。accepted 只表示原生执行与交接检查通过，不是自动质量认证。
- 下游重新执行并独立通过检查后才恢复 accepted；不会自动恢复旧审查结论。

## 三阶段配置

新增 `workflows/ui-optimize-three-stage.json`，顺序为 kiro → codex → claude，
三个阶段均为 `model=auto`、`effort=""`。保留原兼容性样例。
启动器会按现有工作流加载机制读取该定义；已启动的实例可先保存：

```bash
source .venv/bin/activate
python workflow.py save workflows/ui-optimize-three-stage.json --expected-revision 0
```

该命令用于首次保存；已有版本须读取当前版本号后按既有版本冲突规则保存。
Claude 阶段 prompt 保留用户原文“Fabel 5.1”，明确说明原生 ID 和可用性未核实。
本步未读取真实账户模型缓存，没有将其冒充为可用 ID。`auto` 仅选择工具默认模型，
不保证使用该偏好；实际值以原生观察器为准。不能把空格或 `[effort]` 写入 model。

## 改动文件

| 文件 | 目的 |
|---|---|
| `workflow.py` | 同源重试端点、失效日志与归档、原生续作参数、新候选检查、状态投影 |
| `ui/workflow-progress.js` | 共享百分比计算和可访问 SVG 环 |
| `ui/workflow.js` | Session 环、重试按钮状态、HTTP 请求、续作指令 |
| `ui/workflow.css` | 状态颜色、仅运行态脉冲和 reduced-motion 降级 |
| `ui/workflow.html` | 引入进度模块和两项任务操作 |
| `workflows/ui-optimize-three-stage.json` | 用户要求的三阶段可移植定义 |
| `test_workflow.py` | 计算、状态、归档、HTTP、幂等/并发、候选隔离、配置回归 |
| `build_pipeline_kit.py` | 打包新模块、配置与本说明 |
| `README.md` | 更新能力和使用入口 |

## 验证与限制

执行本步要求的虚拟环境和依赖安装命令，未新增运行依赖。
执行指定四模块 unittest 与三个原有 JS 文件的语法检查，
另检查新进度模块；实际输出保存在本次交接证据中。

浏览器验收使用缓存 Chromium、临时浏览器配置、真实 Workflow HTTP 服务及隔离原生任务夹具。
检查整数百分比与 aria-label、running-only 动画、减少动态效果、重试禁用、
失败重试、优化导致下游失效、HTTP 幂等、归档文件和 390px 手机侧栏。
原生浏览器工具因宿主沙箱初始化失败，获准后以独立 CDP 脚本和
Chromium `--no-sandbox` 完成上述本地夹具验证。没有访问个人浏览器配置。

这些结果不代表已调用真实 `spawn_continue`/`spawn_run` 或完成真实模型 E2E。
三阶段 prepare/参数流使用模拟原生 API 验证。下一步由测试验证阶段复查当前候选，
在原生环境中核验新 Task ID、实际模型/Effort 和 accept 结果；模型偏好仍待核实。
没有提交、推送、部署或发布。
