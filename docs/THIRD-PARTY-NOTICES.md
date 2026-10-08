# 第三方来源与授权边界

本仓库的 Octopus 框架来自既有本地 PoC；不包含 KiroCrew 上游源码或其打包运行时。
运行时复用以下项目：

- KiroCrew：`kirodotdev/KiroCrew`，本次查阅版本采用 Apache-2.0，
  具体文本见 [来源 S1](SOURCES.md#s1)。
- Claude ACP adapter：`@agentclientprotocol/claude-agent-acp`，版本见 `package-lock.json`。
- Codex ACP adapter：`@agentclientprotocol/codex-acp`，版本见 `package-lock.json`。
- PyYAML：工作流 YAML 解析依赖，版本范围见 `requirements-workflow.txt`。
- Kiro CLI、Claude Code、Codex、OpenCode 由部署者分别安装；工具和模型服务的条款分别适用。

依赖的具体许可证及 NOTICE 以锁定版本实际发布包为准；本仓库不重新声明它们的版权归属，
也不打包 `node_modules`、本机 CLI 二进制或认证。

本次没有为 Octopus 新增代码选择许可证。公开可访问与授予开源 / 商业再分发许可不是同一事项。
“Enterprise”仅用于区分规划中的团队和 Connector 功能，并不表示已确定商业授权条款。
