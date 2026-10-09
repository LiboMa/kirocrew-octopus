# Workflow MVP 离线交互报告

直接打开 `index.html`。这是自包含的 HTML，不需要服务器、CDN、模型调用或登录。
复制这一个文件即可离线阅读；`diagrams/` 另提供 13 张可独立使用的 SVG。

内容：17 个章节、15 个分步执行事件、正常 / 模型不匹配 / 待授权 / 断连四个场景、
版本冻结实验、四后端路由拆解、参数核对、Context、持久化与模块浏览、
20 个真实函数 / 类源码快照，以及完整 WORKFLOW-MVP.md 附录。

原始文档中的 4 个 Mermaid 图已转换为 SVG，所以页面共有 17 处图表展示，
对应 13 个独立图表文件。动画、Task / Session 标识均为机制示意，不是实时执行证据。

操作：

- 目录搜索机制或关键词；`/` 聚焦搜索。
- “投屏模式”逐章阅读，左右方向键切换；再次点击回到连续全文。
- 图表“放大”后可以缩放、下载 SVG；源码按钮打开构建时真实代码和行号。
- “打印 / PDF”使用浏览器打印，展开完整原文附录。
- 尊重系统减少动态效果，自动播放只由用户启动；手动分步始终可用。

重新生成（在仓库根目录）：

```bash
python3 build_mvp_report.py
node --check ui/mvp-report/report.js
```

生成器只读取白名单文档和源码。输入哈希与 HTML 哈希在 `manifest.json` 中，
同时生成仓库根目录的 `kirocrew-workflow-mvp-report.zip`。
`ui/mvp-report/` 保存正文、样式、交互和 SVG 生成逻辑；不修改现有工作台的运行行为。

没有读取原生 Sessions、Memory、认证或运行日志。本报告制作不验证新的 Coding Agent 执行、
EC2 部署或 Enterprise 能力，相关事实仍以原生任务证据和后续实际验收为准。
