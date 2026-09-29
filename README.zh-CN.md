# Chrome History Collapse

[English](README.md) | [简体中文](README.zh-CN.md)

供 AI agent 使用的 Chrome 历史记录清理方案：将同一组连续翻页记录压缩为一个保留页面。在本地生成清理计划，显式执行删除，并使用 Chrome 自身的历史记录接口。

支持数字片段（如 `/read/demo#1`、`#2`）和明确指定的分页查询参数（如 `?page=1`、`?page=2`）。每次运行仅处理一个精确匹配的主机名，不合并不同文档路径或不同搜索条件。默认至少有 10 个不同页码才组成清理组。优先保留第 1 页；如果不存在，则保留已有的无页码地址，再其次保留现有页码最小的一页。这里保留的是一个**页面 URL**，该 URL 在不同日期的访问记录仍可能有多条。

## Agent 快速开始

先阅读 [AGENTS.md](AGENTS.md)。环境要求：Python 3.9+、Node.js 20+，以及 Chrome **已经可用的本地 CDP 连接**。浏览器适配代码依赖 Chrome 内部页面方法，升级 Chrome 后需要检查兼容性。

```sh
npm ci --registry=https://registry.npmjs.org
npm test
```

1. 确认目标 Chrome 用户配置及其 `History` 数据库，将一致性 SQLite 备份保存到仓库外的私有目录。能正常打开数据库时，可以使用 SQLite 的标准备份命令。如果 Chrome 持有独占锁，应先安排正常退出浏览器，再备份。不要强制终止 Chrome，也不要使用 `immutable=1` 绕过正在写入的数据库。

   ```sh
   umask 077
   mkdir -p "$HOME/.local/share/chrome-history-collapse"
   sqlite3 "$CHROME_HISTORY" ".backup '$HOME/.local/share/chrome-history-collapse/before.sqlite'"
   ```

   在本地将 `CHROME_HISTORY` 设置为目标用户配置的实际 History 文件路径。备份成功后才能继续，清理完成后也应保留备份。

2. 从备份生成计划。实际主机名只用于本地命令，以下使用虚构域名演示：

   ```sh
   python3 plan.py "$HOME/.local/share/chrome-history-collapse/before.sqlite" \
     --host example.org \
     --output "$HOME/.local/share/chrome-history-collapse/plan.json"
   ```

   查询参数分页可加 `--page-param page`。页码位于 URL 路径中的站点，需要单独定义明确规则，不能把任意数字 ID 都当成页码。在本地检查生成的保留与删除清单，控制台只输出数量。

3. 确认目标浏览器的 CDP 端点。如果 HTTP 发现接口返回 404，但用户配置目录中存在 `DevToolsActivePort`，其第一行是端口，第二行是浏览器 WebSocket 路径。将它们组合为 `ws://127.0.0.1:<port><path>`，在本地设置 `CHROME_CDP`。确认连接对应生成计划时使用的同一个用户配置，不要公开该端点。如果 CDP 不可用，应暂停并安排受支持的本地浏览器连接，不要擅自切换用户配置或重启浏览器。

4. 先进行不删除数据的校验，再在用户授权范围内执行：

   ```sh
   node apply.mjs --plan "$HOME/.local/share/chrome-history-collapse/plan.json"
   node apply.mjs --plan "$HOME/.local/share/chrome-history-collapse/plan.json" \
     --endpoint "$CHROME_CDP" --apply
   ```

   脚本会创建专用的后台历史记录标签页，运行期间应保持它打开，不会复用现有标签页。各批次顺序执行，大量记录可能需要较长时间。增加并发写入无法消除 Chrome 的数据库瓶颈。页面跳转、连接丢失或脚本失败，**不代表** Chrome 已取消提交到后台的删除批次。

5. 完成后重新获取一致性快照，保存为 `after.sqlite`，然后核验：

   ```sh
   python3 plan.py "$HOME/.local/share/chrome-history-collapse/after.sqlite" \
     --verify "$HOME/.local/share/chrome-history-collapse/plan.json"
   ```

   只有目标 URL 残留为零、保留 URL 缺失为零，并且 SQLite 完整性检查通过，才能判断成功。请求中断后，应先检查新快照，再决定是否重试。只重试残留的“URL + 日期”项，不要启动重叠的删除任务。

## 关键注意事项

- **按 URL 和本地日期拆分删除项。** 将同一个 URL 所有日期的时间戳放进一项，可能留下其他日期的访问记录。计划脚本已经按日期拆分；生成计划和执行删除时应使用同一时区。
- **删除前先备份。** 本地 SQLite 备份可用于恢复，但不能撤销已同步到服务器或其他设备的删除。恢复时必须先停止 Chrome，并获得覆盖现有历史记录的明确授权，因为恢复可能覆盖之后新增的访问记录。
- **本机验证不等于远程验证。** 开启历史同步时，Chrome 原生接口可以发出同步删除指令。本工具不会列举仅存在于远程的历史，也不会确认 Google 服务器或其他设备上的删除是否完成。
- **使用一致性快照。** 对正在写入的数据库使用 immutable 读取，可能读到未完成的事务，甚至出现暂时性的损坏报错。本方案不使用这种捷径。
- **不按整个站点一刀切。** 计划脚本只处理明确的分页组，不会合并某个主机名下的全部页面、随意移除片段，或将不同内容的 ID 当成页码。

相关上游行为可参考 Chromium 的 [BrowsingHistoryHandler::RemoveVisits](https://source.chromium.org/chromium/chromium/src/+/main:chrome/browser/ui/webui/history/browsing_history_handler.cc) 和 [BrowsingHistoryService::RemoveVisits](https://source.chromium.org/chromium/chromium/src/+/main:components/history/core/browser/browsing_history_service.cc)。这些内部接口可能随版本变化。

## 隐私

仓库只包含虚构示例。历史数据库、清理计划、访问时间戳、浏览器用户配置、截图、终端输出和执行日志，都应保存在仓库之外。基于允许列表的 `.gitignore` 只是额外防护，不能代替提交前检查。不要将真实浏览 URL 写进 issue、提交记录、CI 任务或 agent 报告。工具没有遥测或上传代码，但 Chrome 自身的同步行为仍然适用。

## 验证

`npm test` 使用内存中的虚构 SQLite 数据，检查主机名和路径隔离、分页筛选、第 1 页保留及跨日期拆分，不会操作真实浏览器。另一次使用临时浏览器用户配置的冒烟测试，已通过虚构页面验证计划生成、预览、原生删除和结果核验的完整流程。脚本不保证兼容所有 Chrome 版本，调整浏览器接口前应先在临时用户配置中验证。

采用 MIT 许可证，详见 [LICENSE](LICENSE)。
