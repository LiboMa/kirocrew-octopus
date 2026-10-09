# 任务向导浏览器回归

`workflow-wizard.browser.js` 是 Playwright `run-code` 入口函数，使用独立的无界面
Chrome 与内存浏览器上下文。页面资源来自本仓库，所有 `/api/` 调用均拦截为合成响应；
不会访问用户的浏览器存储、原生 Sessions、认证或 Coding Agent。

仓库根目录启动只读静态服务：

```bash
python3 -m http.server 8920 --bind 127.0.0.1 --directory ui
```

使用已安装的 Playwright CLI 执行：

```bash
playwright-cli run-code --filename=tests/workflow-wizard.browser.js
```

也可通过 Playwright MCP 的 `browser_run_code_unsafe` 加载同一个文件。
执行环境需已有 Playwright 浏览器连接和 Chrome；无须安装或登录 Coding 工具。
默认只返回测试结果。自定义运行器可用第二个参数
`{artifactRoot: "/绝对路径/evidence/workflow-wizard"}` 启用截图；目录由调用方指定，
测试源码不固定开发者本机路径。

覆盖采用意图、生成中改写意图、名称去重、Chat 输入模式切换、轮询、旧 Session
背景下刷新恢复草稿、确认与开始的请求一致性、全部模板、示例切换、保护手写目标、
搜索、分类和窄屏。这里模拟的开始请求仅用于验证前端数据传递，不是原生执行证明。
