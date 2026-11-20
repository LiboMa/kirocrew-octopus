# KiroCrew ON 介绍演示（3Blue1Brown 风格）

面向未来用户的单文件 HTML 演示：平台的价值、原理、架构、一次真实会话的完整过程、基本用法、团队治理、真实数据与已知边界。

- `index.html`：直接用浏览器打开，离线可用。→ / 空格逐步前进，← 后退，O 目录，F 全屏；`#12.3` 可直达第 12 页第 3 步。
- `KiroCrew-ON-intro.pdf`：每页完全展开后的截图版，28 页，便于转发（文字不可选）。
- `shots/`：控制台截图（WebP），2026-11-17 从线上实例 `https://kirocrew-on.tinyboat.blog` 截取。

## 内容来源

- 线上平台：MVP 0.2.0rc1，来自 `experiments/kirocrew-on` 仓库的 `feat/mvp-0.2.0` 分支；本仓库是它的前身（见该仓库 `docs/PROVENANCE.md`）。
- 案例会话：`run-44dc0643a7dd400bbce55654877d547e`（时间线与 F1–F5 取自 `GET /v1/runs/<id>/revisions`）。
- 统计数据：管理员视角 `GET /v1/runs?all=1`，2026-11-17 读取，含平台验收用的测试会话。
- “两个入口”页的终端内容：2026-11-17 经本机 kirocrew-on MCP 服务器调用 `octopus_status` / `octopus_observe` 的真实输出，字段为节选。
- 架构、门禁、角色与限制：kirocrew-on 仓库的 `docs/ARCHITECTURE.md`、`docs/MVP-0.1.0.md`、`docs/MVP-0.2.0.md`、`docs/BACKLOG.md` 与 `octopus/gates.py`、`octopus/roles/`。

## 分享前注意

截图与案例包含内部信息：会话标题与需求（含客户场景名称）、用户名、Token 名称、执行环境与 CloudFront 域名。对外发布前请确认可以公开，或替换为脱敏的会话。

## 更新

平台变化后：重新截取 `shots/` 中对应的图（保持原尺寸比例，框选坐标按图片百分比写在 `index.html` 的 `.hl` 上），更新数据页的数字，再按每页 `#N.99` 截图重新生成 PDF。
