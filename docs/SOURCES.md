# 架构与计划来源

核对日期：2026-10-08。上游源码使用固定 commit；托管服务文档会继续变化，
实现时需根据目标版本重新核对，不把文档示例等同于本项目已支持的能力。

## S1

KiroCrew 上游：

- [固定版本安装说明](https://github.com/kirodotdev/KiroCrew/blob/6287f540aef70e197657947e6530702ad74233f9/docs/guides/install.md)
- [平台扩展接口](https://github.com/kirodotdev/KiroCrew/blob/6287f540aef70e197657947e6530702ad74233f9/src/kiro_crew/platform/interfaces.py)
- [Apache-2.0 许可证](https://github.com/kirodotdev/KiroCrew/blob/6287f540aef70e197657947e6530702ad74233f9/LICENSE)

用于核对 Linux / 无桌面安装、服务启动、Provider / Identity / Publish 扩展接口及 RESERVED 边界。

## S2

[AWS Systems Manager：启动 Session 与端口转发](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html)

用于设计 `AWS-StartPortForwardingSession` 访问方式；EC2 账号、IAM、网络和预算仍需单独配置。

## S3

[GitHub App：生成 installation access token](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app)

用于设计 installation、仓库与权限限制、凭据刷新。

## S4

[GitHub：验证 Webhook](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)

用于设计原始 body 的 HMAC-SHA256 / `X-Hub-Signature-256` 校验。

## S5

[GitLab：Webhooks](https://docs.gitlab.com/user/project/integrations/webhooks/)

用于设计新版本 signing token、旧版 secret token 的能力差异及事件去重。

## S6

[GitLab：OAuth 身份提供与应用](https://docs.gitlab.com/integration/oauth_provider/)

用于识别用户 / 组 / 实例级应用范围；仓库 API 权限和部署策略须按客户实例核验。
