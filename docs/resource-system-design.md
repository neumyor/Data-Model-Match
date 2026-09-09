# DataModelMatch 资源系统设计

## 1. 目标与边界

系统接收来源不确定的数据集和深度学习模型，将远程或本地原始资源转换为可验证的标准描述，再生成数据集与模型之间的兼容性报告。

首期支持：

- Hugging Face 数据集仓库或搜索关键词；
- GitHub 模型仓库；
- 本地数据集目录；
- 本地模型目录。

首期不执行下载仓库中的代码，不自动训练、推理或安装依赖。资源分析默认是静态的；需要动态探测时必须在后续版本中加入隔离运行环境和用户确认。

## 2. 公共数据契约

### 2.1 ResourceRecord

```json
{
  "id": "dataset_...",
  "kind": "dataset",
  "sourceType": "huggingface",
  "source": "lhoestq/demo1",
  "revision": "main",
  "resolvedRevision": "commit-sha",
  "name": "demo1",
  "status": "ready",
  "localPath": ".datamodelmatch/resources/datasets/dataset_...",
  "profilePath": ".datamodelmatch/profiles/datasets/dataset_....json",
  "fileCount": 3,
  "sizeBytes": 12345,
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601",
  "warnings": []
}
```

`kind` 为 `dataset` 或 `model`。`status` 为：

- `discovering`
- `awaiting_confirmation`
- `downloading`
- `scanning`
- `profiling`
- `needs_review`
- `ready`
- `failed`

同一 `kind + sourceType + 规范化 source` 使用稳定资源 ID。重复导入会原子更新该来源卡片的本地快照、`resolvedRevision` 和 profile，不重复创建资源；如需同时保留多个历史版本，应在后续版本中增加显式版本快照能力。

### 2.2 DatasetProfile

```json
{
  "version": 1,
  "resourceId": "dataset_...",
  "name": "demo1",
  "description": "...",
  "source": {"type": "huggingface", "location": "lhoestq/demo1", "revision": "..."},
  "modalities": ["text"],
  "taskHints": ["text-classification"],
  "splits": [{"name": "train", "rowCount": 1000}],
  "features": [
    {
      "name": "text",
      "dataType": "string",
      "semanticRole": "input",
      "nullable": false,
      "shape": [],
      "description": "..."
    }
  ],
  "formats": ["csv"],
  "sampleCount": 20,
  "license": "unknown",
  "languages": [],
  "evidence": [],
  "warnings": [],
  "trace": [
    {
      "event": "stage",
      "stage": "profiling",
      "status": "completed",
      "message": "生成标准描述：完成"
    }
  ],
  "completeness": 0.8
}
```

`sampleCount` 表示本次静态分析实际覆盖的样本行数，受抽样上限约束；各 split 的
`rowCount` 表示从 Parquet 元数据或 Hugging Face 静态清单读取的资源总行数，两者
语义不同。Parquet schema 由项目依赖 `pyarrow` 读取，不执行数据集脚本。

`trace` 适用于数据集和模型 profile，为导入过程中持久化的可审计事件，包含阶段、进度、证据和警告，不包含凭据、完整请求或模型思维过程。

### 2.3 ModelProfile

```json
{
  "version": 1,
  "resourceId": "model_...",
  "name": "minGPT",
  "description": "...",
  "source": {"type": "github", "location": "karpathy/minGPT", "revision": "..."},
  "frameworks": ["pytorch"],
  "architectures": ["transformer"],
  "tasks": ["text-generation"],
  "inputContract": {
    "modalities": ["text"],
    "fields": [{"name": "text", "dataType": "string", "required": true}],
    "preprocessing": ["tokenize"],
    "constraints": []
  },
  "outputContract": {
    "fields": [{"name": "tokens", "dataType": "integer", "required": true}]
  },
  "entrypoints": [],
  "dependencyFiles": [],
  "license": "unknown",
  "evidence": [],
  "warnings": [],
  "completeness": 0.7
}
```

### 2.4 CompatibilityReport

```json
{
  "datasetResourceId": "dataset_...",
  "modelResourceId": "model_...",
  "status": "adaptable",
  "score": 0.82,
  "summary": "...",
  "dimensions": [
    {
      "name": "modality",
      "status": "compatible",
      "score": 1,
      "reason": "...",
      "evidence": []
    }
  ],
  "fieldMappings": [],
  "transforms": [],
  "blockers": [],
  "warnings": [],
  "meta": {
    "model": "glm-5.3-flash",
    "deployment": "GLM_...",
    "attemptCount": 2
  }
}
```

报告状态为 `compatible`、`adaptable`、`blocked` 或 `unknown`。维度至少覆盖任务、模态、输入字段、数据类型、shape、预处理、标签、许可和运行环境。

`model` 为 `config.llm.json` 中的逻辑模型名。客户端从同一 endpoint 的 `/v1/models` 目录解析启用且支持 OpenAI Chat 的同名部署；部署发生读取超时、无效响应或应用协议校验失败时，可在总超时预算内切换其他同名部署。最终使用的部署和累计尝试次数必须通过 `deployment`、`attemptCount` 显式返回，配置文件不得被改写。

## 3. 服务接口

### 3.1 搜索

- `GET /api/search/datasets?q=...`
- `GET /api/search/models?q=...`

返回轻量候选项，不下载资源。

### 3.2 资源

- `GET /api/resources?kind=dataset|model`
- `GET /api/resources/:id`
- `POST /api/resources/import`
- `DELETE /api/resources/:id`

资源记录和 profile 默认位于项目根目录的 `.datamodelmatch/`。服务端也支持通过资源工作区切换读取根目录：

- `GET /api/workspace`
- `PUT /api/workspace`

工作区返回当前根目录，以及根目录下的 `resources/datasets` 数据集目录和
`resources/models` 算法代码库目录。切换工作区只更新读取路径，不复制、不移动已有数据；
目标路径不存在时不会预填旧资源，目标路径为空时两类资源列表均为空。工作区路径配置保存在
项目根目录的 `config.workspace.json`，该文件必须保持 Git ignored。

导入请求：

```json
{
  "kind": "dataset",
  "sourceType": "huggingface",
  "source": "lhoestq/demo1",
  "revision": "main",
  "downloadMode": "sample"
}
```

`downloadMode` 为 `metadata`、`sample` 或 `full`。默认 `sample`，单资源默认下载上限为 50 MB。

导入响应为 SSE。事件类型：

- `stage`：阶段开始或完成；
- `progress`：文件、字节和百分比；
- `evidence`：发现的结构化证据；
- `warning`：非致命问题；
- `result`：最终 `ResourceRecord` 与 profile；
- `error`：错误码和可诊断消息；
- `end`：`completed`、`failed` 或 `cancelled`。

### 3.3 兼容性分析

- `POST /api/compatibility`

请求包含 `datasetResourceId`、`modelResourceId` 和可选 `timeoutMs`，响应为 SSE，最终返回 `CompatibilityReport`。

## 4. 安全与资源控制

- 远程来源只允许 HTTPS；
- 首期远程域名只允许 `huggingface.co`、GitHub 和已验证的官方内容分发域名，包括 Hugging Face 的 `*.cdn.hf.co`、Xet 内容域名以及 GitHub `codeload.github.com`；
- GitHub 只执行固定 revision 的浅克隆或归档下载；
- GitHub 抽样模式优先通过官方 Tree/Blob API 拉取固定 commit 的少量高价值源码文件；
- 不执行资源代码、不安装依赖、不反序列化模型权重；
- 扫描时拒绝越界软链接；
- 忽略 `.git`、权重和超过限制的二进制文件；
- 下载前后检查累计字节数；
- 错误和事件不得包含凭据；
- 产品资源写入 `.datamodelmatch/`，该目录必须由 Git 忽略；
- 本地导入拒绝项目根目录、用户主目录、`.git`、`_reference_only` 和 `.datamodelmatch` 子树；
- 本地导入跳过 `config.llm.json`、`.env*`、`credentials.json` 和 `secrets.json`；
- `_reference_only` 保持只读，不作为产品资源目录。

## 5. 验收

可用版本必须完成：

1. 真实 Hugging Face 数据集搜索、拉取、扫描和描述生成；
2. 真实 GitHub 模型仓库拉取、扫描和描述生成；
3. 本地不规则目录的对应流程；
4. 资源卡片、详情、状态和执行轨迹；
5. 选取已就绪数据集与模型运行真实 LLM 兼容性分析；
6. 正常、输入错误、网络错误、超时和不兼容路径测试；
7. 桌面与移动端正式渲染检查；
8. `config.llm.json`、`.datamodelmatch/` 和 `_reference_only/` 保持 ignored。
