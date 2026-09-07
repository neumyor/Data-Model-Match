# DataModelMatch 最小版本设计

## 目标

DataModelMatch 接收两个版本化数据模型文档，通过真实的 OpenAI-compatible LLM endpoint 生成源模型到目标模型的候选字段匹配结果。

最小版本关注模型理解和结果协议，不负责自动迁移数据库、生成可执行转换代码、写回业务系统或提供生产级可靠性保障。

## 输入模型

模型文档使用以下结构：

```json
{
  "version": 1,
  "id": "crm",
  "name": "CRM",
  "description": "客户关系模型",
  "entities": [
    {
      "id": "customer",
      "name": "Customer",
      "description": "客户主数据",
      "fields": [
        {
          "id": "customer_id",
          "name": "customerId",
          "dataType": "string",
          "nullable": false,
          "description": "客户唯一标识"
        }
      ]
    }
  ]
}
```

`version` 当前必须为 `1`。模型、实体和字段的 `id` 在各自的作用域内必须唯一；`entities` 和每个实体的 `fields` 不得为空。`dataType` 保留为字符串，避免在最小版本绑定具体数据库方言。

## 匹配接口

核心匹配接口接收已经校验过的模型文档和 LLM client：

```python
match_models(source_model, target_model, client) -> MatchResult
```

匹配方向固定为 `source -> target`。每个源字段最多匹配一个目标字段，每个目标字段最多被匹配一次。

LLM 只负责返回候选 `matches`：

```json
{
  "matches": [
    {
      "source": {"entityId": "customer", "fieldId": "customer_id"},
      "target": {"entityId": "account", "fieldId": "account_id"},
      "kind": "semantic",
      "confidence": 0.98,
      "reason": "两者均表示客户主键"
    }
  ]
}
```

本地代码负责校验字段引用、重复匹配、`kind` 枚举和置信度范围，并根据输入字段全集确定性计算未匹配字段。

## 输出结果

```json
{
  "sourceModelId": "crm",
  "targetModelId": "billing",
  "matches": [],
  "unmatchedSourceFields": [],
  "unmatchedTargetFields": [],
  "meta": {
    "model": "glm-5.3-flash",
    "attemptCount": 1
  }
}
```

`kind` 只能是：

- `exact`：名称、标识或类型高度一致；
- `semantic`：语义相同但名称或表示方式不同；
- `transform`：需要转换才能对应，只提供解释，不生成转换代码。

## LLM 配置和调用

LLM 配置唯一默认来源是项目根目录的 `config.llm.json`，包含 `endpoint`、`apiKey`、`model` 和 `stream`。最小版本使用同步、非流式 Chat Completions 请求。

本版本明确不实现：

- 生产级重试和退避；
- 取消传播；
- 多供应商路由；
- 上下文切分和大模型输入压缩；
- 自动脱敏和提示词注入防护。

## 验收

验收至少覆盖：

1. 版本化多实体模型可以被读取并校验；
2. 本地结果校验可以拒绝未知字段、重复映射、非法 `kind` 和非法置信度；
3. 服务端可以确定性推导未匹配字段；
4. CLI 可以读取两个模型并输出结构化结果；
5. 使用根目录 `config.llm.json` 完成一次真实 endpoint 端到端匹配。
