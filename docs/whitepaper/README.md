# KiroCrew ON 白皮书

面向开发者、Team 与平台管理员的完整项目介绍：产品定义、核心概念、系统架构、端到端使用流程（附截图）、适用场景、真实案例、管理与治理、部署形态、运行数据、当前限制与路线图。

- `index.html`：网页版，左侧目录、右侧正文，直接用浏览器打开；打印时按 A4 自动分页。
- `KiroCrew-ON-白皮书.pdf`：PDF 版（37 页，文字可选）。
- `img/`：截图（WebP），来自线上实例 https://kirocrew-on.tinyboat.blog，2026-11-17 与 11-19 截取。

## 内容依据

- 控制台截图与 API 返回：`/v1/runs?all=1`（运行数据）、`/v1/runs/<id>/revisions`（案例时间线）。
- MCP 工具 `octopus_workflows`、`octopus_teams` 的返回（2026-11-19）。
- kirocrew-on 仓库 `feat/mvp-0.2.0` 分支的 README、docs/MVP-0.1.0.md、docs/MVP-0.2.0.md、docs/ARCHITECTURE.md、docs/CONNECT.md、docs/BACKLOG.md，以及 octopus/gates.py、octopus/roles/、octopus/phases.py。

## 分享前注意

截图包含内部信息：会话标题与需求、用户名、Token 名称、执行环境名称。对外发布前请确认可以公开。

## 重新生成 PDF

用 Chrome 打开 `index.html`，打印为 PDF（A4、启用背景图形）。为了减小体积，生成本目录的 PDF 时临时把截图换成了 JPEG。
