# 贡献与迭代

从 [PLAN.md](PLAN.md) 选择一个验收明确的工作项。每次变更说明解决的问题、
影响的原生接口、验证方式与尚未验证的部分。不要把未来架构写成当前能力。

## 本地检查

使用 Python 3.12 / 3.13，创建虚拟环境后安装 `requirements-workflow.txt`：

```bash
python -m unittest test_workflow test_workflow_library test_pipeline test_reload_gateway -q
node --check ui/workflow.js
node --check ui/workflow-view.js
node --check ui/crew-entry.js
node --check ui/live.js
python build_pipeline_kit.py
```

单元测试使用临时目录和模拟原生 API。不要用 `unittest discover` 替代上述列表：
`test_routing.py` 会导入原生 KiroCrew 并准备运行环境，它属于单独的集成检查。
CI 不需要 Coding 工具登录，不启动 Agent，也不使用部署主机的真实 Sessions。
任务向导的浏览器交互回归见 [tests/README.md](tests/README.md)，使用合成 API，
覆盖意图采用与模板填充；需要本机 Playwright 和 Chrome。

## 保留的产品约束

- 以 KiroCrew 原生接口和 ACP 驱动工具；不用新的自制 Agent 协议替代已经可用的接口。
- 工作流版本和运行快照不可变。修改只对下一次运行生效。
- Session 管理保留历史数据；归档 / 删除不能暗中清理原生对话。
- 后端、Model、Effort 必须区分请求和实际报告；未知值明确记录。
- Context 交接有来源与文件证据，不承诺不同工具共用原生模型窗口。
- 完成事件、权限等待、失败和断连都按真实状态展示。

## 发布与依赖

`build_pipeline_kit.py` 使用明确文件白名单生成本地 ZIP，输出不纳入 Git。
源码版本由 Git 管理；本机 `state/`、`evidence/`、Sessions、Memory、认证、缓存、
日志和备份不得随打包或提交带出。示例应使用合成需求，不加入客户原始对话。

上游升级先做原生 factory / session / permission / model 契约检查，
再修改允许版本范围；不以“能 import”代替一次真实执行验证。
在新主机重新配置工具认证，不拷贝开发者整个 HOME。

本项目新增代码尚未明确许可证。外部贡献和再分发前由仓库所有者确定相应条款；
不要把第三方的许可证自动套用到整个项目。
