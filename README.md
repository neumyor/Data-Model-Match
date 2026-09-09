# DataModelMatch

DataModelMatch 将来源不确定的数据集和深度学习模型转成可审计的标准描述，再判断两者是否可以直接组合、需要哪些转换，或存在哪些确定性阻断。

当前版本支持：

- 搜索并导入 Hugging Face 数据集；
- 搜索并导入 GitHub 模型仓库；
- 导入层次结构不确定的本地数据集或模型目录；
- 静态解析字段、模态、任务、框架、入口、依赖和输入输出契约；
- 使用 `pyarrow` 读取 Parquet schema 与行数元数据，支持常见图像、分类标签、检测标注和分割掩码结构；
- 以卡片、详情和执行轨迹管理本地资源快照；
- 通过真实 LLM API 补充语义字段映射，并生成结构化兼容性报告；
- 从模型目录解析同名健康部署，在网络或协议失败时受控切换并记录实际部署；
- 通过 SSE 持续展示资源导入和兼容性分析进度。

系统不会执行仓库代码、安装仓库依赖或读取模型权重内容。资源快照默认写入被 Git 忽略的 `.datamodelmatch/`，也可以在设置中切换资源工作区。切换只会改变读取位置，不会自动复制或移动数据集和算法代码库；工作区配置保存在被 Git 忽略的 `config.workspace.json` 中。

## 新电脑部署与演示

### 1. 安装前置软件

新电脑需要安装：

- Git；
- Python 3.9 或更高版本；
- Bun。

### 2. 克隆并安装项目

```sh
git clone git@github.com:neumyor/Data-Model-Match.git
cd Data-Model-Match

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

cd web
bun install
```

Windows PowerShell 激活虚拟环境时使用：

```powershell
.venv\Scripts\Activate.ps1
```

### 3. 配置 LLM

在项目根目录新建 `config.llm.json`，填入可用的 OpenAI Chat Completions 兼容服务配置：

```json
{
  "endpoint": "https://llm-center.modelbest.co/v1/chat/completions",
  "apiKey": "<你的 API Key>",
  "model": "glm-5.3-flash",
  "stream": false
}
```

该文件包含凭据，已经被 `.gitignore` 忽略，不能提交到 Git。系统不会从环境变量读取默认 LLM 配置。

### 4. 启动 Web 演示

在项目根目录执行：

```sh
cd web
bun run start
```

`bun run start` 会自动构建前端并启动本地服务。浏览器打开：

```text
http://localhost:3000
```

### 5. 运行资源匹配演示

1. 打开“数据集管理”，点击“添加数据集”。
2. 输入公开 Hugging Face 数据集，例如 `lhoestq/demo1`，搜索后选用并开始解析。
3. 打开“模型管理”，点击“添加模型”。
4. 输入公开 GitHub 模型仓库，例如 `openai/CLIP`，开始解析。
5. 打开“匹配工作台”，选择已经就绪的数据集和模型，点击“开始兼容性分析”。
6. 查看“智能体执行轨迹”和右侧兼容性报告；分析过程会通过 SSE 持续更新。

首次导入需要访问 Hugging Face 或 GitHub。若只想验证本地匹配 CLI，也可以运行下面的演示：

```sh
cd ..
source .venv/bin/activate
PYTHONPATH=src python -m datamodelmatch.cli \
  examples/source_user.json \
  examples/target_customer.json \
  --config config.llm.json \
  --timeout 90
```

该命令会输出结构化字段匹配结果。它同样需要真实 LLM 配置；没有有效 `config.llm.json` 时，命令会明确报错，不会用模拟结果代替。

## 开发命令

开发时可以使用 Bun 的监听模式：

```sh
cd web
bun run dev
```

仅构建前端和服务端产物：

```sh
cd web
bun run build
```

## 用户流程

1. 在“数据集管理”中输入 Hugging Face 仓库、搜索关键词或本地目录，选择来源类型和下载策略并开始解析。
2. 在“模型管理”中输入 GitHub 仓库、搜索关键词或本地目录，系统固定远程 commit 并静态提取模型契约。
3. 在资源详情中检查结构化描述、文件统计、解析证据、警告和完整执行轨迹。
4. 在“匹配工作台”选择一个已就绪数据集和模型，查看流式执行轨迹和兼容性报告。
5. 根据任务、模态、字段、类型、张量形状、预处理、标签、许可证和运行环境维度处理转换建议或阻断项。

详细契约和接口见 [资源系统设计](docs/resource-system-design.md)。

## 验证

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests
cd web && bun run build
```

真实兼容性测试必须使用根目录 `config.llm.json`，不能用 mock 结果冒充真实 API 已通过。外部服务超时或凭据无效时，系统会返回可诊断警告并保留确定性分析结果。

## 兼容接口

早期的两个 JSON 数据模型字段匹配能力仍保留在 `datamodelmatch.cli` 和 `POST /api/match` 中，输入格式见 [旧版数据模型设计](docs/design.md)。新资源系统的主入口为 Web 工作台和 `datamodelmatch.resource_cli`。

开发前请先阅读 [AGENTS.md](AGENTS.md)。`_reference_only/` 中的仓库只允许阅读，不得修改。
