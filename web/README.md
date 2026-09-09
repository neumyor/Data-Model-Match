# DataModelMatch Web

前端使用原生 HTML/CSS/JavaScript，Bun 负责构建静态资源和运行本地 API 服务。

```sh
bun install
bun run build
bun run start
```

`bun run start` 会先构建再启动，默认地址为 `http://localhost:3000`。开发时使用 `bun run dev`。`PORT` 只控制监听端口，不参与 LLM 配置。

## 页面

- 数据集管理：搜索、导入、查看和删除 Hugging Face 或本地数据集。
- 模型管理：搜索、导入、查看和删除 GitHub 或本地模型。
- 匹配工作台：选择已就绪资源，通过 SSE 查看执行轨迹和兼容性报告。
- 设置抽屉：查看脱敏后的 `config.llm.json` 配置状态，以及当前资源工作区、数据集目录和算法代码库目录。

资源工作区可以切换到任意非受保护目录。切换只改变读取路径，不会复制或移动原有资源；目标目录为空时，数据集和算法库都会显示为空。

复杂下载策略、固定版本和超时设置位于折叠的高级设置中。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/config-status` | 返回脱敏后的 LLM 配置状态 |
| `GET` | `/api/workspace` | 返回当前资源工作区及数据集、算法代码库目录 |
| `PUT` | `/api/workspace` | 切换资源工作区读取路径 |
| `GET` | `/api/search/datasets?q=` | 搜索 Hugging Face 数据集候选 |
| `GET` | `/api/search/models?q=` | 搜索 GitHub 模型候选 |
| `GET` | `/api/resources?kind=` | 返回资源记录及完整 profile |
| `GET` | `/api/resources/:id` | 返回单个资源详情 |
| `POST` | `/api/resources/import` | 导入资源，响应为 SSE |
| `DELETE` | `/api/resources/:id` | 删除资源快照和 profile |
| `POST` | `/api/compatibility` | 分析数据集与模型兼容性，响应为 SSE |
| `POST` | `/api/match` | 兼容旧版 JSON 数据模型字段匹配 |

导入请求：

```json
{
  "kind": "dataset",
  "sourceType": "huggingface",
  "source": "lhoestq/demo1",
  "revision": "main",
  "downloadMode": "sample",
  "maxBytes": 52428800
}
```

兼容性请求：

```json
{
  "datasetResourceId": "dataset_...",
  "modelResourceId": "model_...",
  "timeoutMs": 90000
}
```

SSE 事件包括 `stage`、`progress`、`evidence`、`warning`、`result`、`error` 和 `end`。事件只包含可审计的阶段、进度和结构化结果，不暴露 API Key、完整请求或模型思维过程。

兼容性报告的 `meta` 同时包含 `model`、`deployment` 和 `attemptCount`。`model` 始终是 `config.llm.json` 中的逻辑模型；`deployment` 是从同一 endpoint 的模型目录中解析并实际调用的同名部署。部署读取超时或输出协议不合格时，客户端会在总超时预算内切换同名部署，不会改写配置文件。

## 安全边界

- 服务端只从项目根目录 `config.llm.json` 读取 LLM 凭据。
- 本地导入拒绝项目根目录、用户主目录、`.git`、`_reference_only` 和 `.datamodelmatch`。
- 导入时跳过符号链接、常见凭据文件、模型权重和超限文件。
- GitHub 抽样模式通过官方 Tree/Blob API 拉取固定 commit 的少量源码；完整模式使用固定 commit 归档。
- 远程或本地仓库代码都不会被执行。
