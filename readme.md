# 知识库查询

基于 LLM 的智能知识库检索工具 —— 从文本文件中精准提取与关键词相关的内容，支持缓存加速与自定义 API。
该插件处于测试阶段,问题可以通过issue提交
## 功能

- 读取指定知识库文件（默认 `knowledge_base/data.txt`）
- 使用 LLM 智能提取与用户关键词相关的信息
- 自动缓存提取结果，避免重复调用 LLM
- 可选使用自定义 API（如 OpenAI 兼容接口）替代内置模型
- 完全可配置：模型类型、详细程度提示词、超时时间等

## 安装

1. 将 `maibot.knowledge-query` 目录放入 MaiBot 的 `plugins/` 目录下。
2. 重启 MaiBot 或执行热重载。

## 第一步：准备知识库

> **在配置和使用之前，您必须手动创建知识库文件。**

插件有关数据的默认使用以下结构：

maibot.knowledge-query/
├── knowledge_base/ # 知识库文件夹（手动创建）
│ └── data.txt # 默认数据文件（需要您手动放入）
├── cache/ # 缓存文件夹（手动创建）
└── config.toml # 配置文件

**操作步骤：**
1. 进入插件目录 `maibot.knowledge-query/`。
2. 创建一个不包含特殊符号的文件夹（比如knowledge_base）。
3. 在 `knowledge_base` 中放入一个纯文本文件或者文本文件(如md.json等)，例如 `data.txt`。
4. 若使用缓存，您也需要手动创建一个不包含特殊符号的`cache` 文件夹用于缓存存放。

> 知识库文件可以是任意 UTF-8 编码的文本，内容越丰富，提取效果越好。

## 配置

编辑 `config.toml` 文件：

```toml
[plugin]
enabled = true                     # 启用插件
config_version = "0.1.0"

[knowledge_base]
folder_path = "knowledge_base"     # 知识库文件夹（相对插件目录）
file_name = "data.txt"             # 要读取的文件名
model = "planner"                  # 使用的 LLM 模型（planner / replyer / utils）
detail_prompt = "请以详细的方式描述"  # 提取内容的细致程度提示词
cache_folder = "cache"             # 缓存文件夹
enable_cache = true                # 是否启用缓存
llm_timeout_seconds = 30           # LLM 调用超时（秒）

[custom_api]
enabled = false                    # 是否使用自定义 API
api_url = ""                       # 自定义 API 地址
api_key = ""                       # 自定义 API 密钥
model = ""                         # 自定义模型名称

配置说明
model：可选 planner、replyer、utils等对应 MaiBot 内置的模型名字。

detail_prompt：直接传给 LLM 的指令，例如“请以简洁的方式描述”或“请列出关键点”。

enable_cache：开启后，每个关键词的提取结果会单独缓存。再次查询相同关键词时会直接返回缓存内容,或者由LLM决定是否直接调用缓存

自定义 API：若启用，需提供完整的 api_url（如 https://api.openai.com/v1/chat/completions）、api_key 和 model（如 gpt-3.5-turbo）。此时将忽略内置 model 设置。

使用步骤

该工具暴露给planner,名字为knowledge-query
planner可以调用该工具并且携带关键词或者关键句
插件会：

读取知识库文件。

检查是否存在该关键词的有效缓存。

若无缓存或缓存不适用，则调用 LLM 从原文中提取相关内容。

返回提取结果，并自动缓存。

缓存智能决策
当存在多个缓存文件时，插件会询问 LLM：“现有缓存是否可以直接回答当前查询？”
若 LLM 判断某缓存合适，则直接返回该缓存内容，无需重新提取。
这一设计在知识库庞大、关键词变体较多时能显著提升响应速度。

示例
知识库文件 data.txt 内容片段：
text
MaiBot 是一个可扩展的聊天机器人框架，支持插件系统。
它基于 Python 开发，提供了 LLM 集成、事件驱动等特性。
插件可以通过 SDK 快速开发，扩展 Bot 的能力。

查询：
text
keyword="MaiBot 的特性"

输出（LLM 提取）：
text
MaiBot 是一个可扩展的聊天机器人框架，基于 Python 开发，支持插件系统、LLM 集成、事件驱动。插件可通过 SDK 快速开发，扩展 Bot 能力。

⚠️ 免责声明

在使用本插件之前，您必须完整阅读并同意以下全部条款。
一、LLM 胡说八道，概不负责
本插件依赖大语言模型从您的知识库中“提取”信息。众所周知，LLM 可能会：

把不相关的内容强行关联

遗漏您认为最重要的信息

对空白文件生成一本正经的废话
若因此导致 Bot 回答出错、群友迷惑、或被吐槽“这 AI 怎么跟没读过书似的”——作者概不负责。

二、缓存决策靠玄学，概不负责
插件会问 LLM：“现有缓存能不能用来回答这个问题？”
LLM 可能认为缓存 “苹果” 可以回答 “iPhone” 的查询，也可能认为 “天气” 无法回答 “今天天气怎么样”。
这种智能（智障？）决策的后果——作者概不负责，建议您定期清理 cache/ 文件夹。

三、自定义 API 乱烧钱，概不负责
如果您启用了自定义 API（例如 OpenAI），请注意：

每一次缓存判断、每一次内容提取都会产生 API 调用。

若您的知识库有几十万字，初次查询时 LLM 会一次性读完整份文件（消耗大量 token）。
钱包缩水、信用卡爆炸——作者概不负责，建议先在小文件上测试。

四、文件编码与路径，崩了概不负责
插件假设知识库文件为 UTF-8 编码。若您使用 GBK、BIG5 或二进制文件：

读取会报错，Bot 会回复“知识库文件不存在或无法读取”。

不会炸掉您的服务器，但您可能会花半小时排查编码问题——作者概不负责。

五、宇宙级免责
本插件按“原样”（AS IS）提供。使用本插件即表示您同意：无论发生什么事——包括但不限于 LLM 提取的内容被群友拿来当真理、因缓存导致信息过时、因模型选择错误导致回复像机器人、因忘记放 data.txt 而查不到任何东西——均与作者无关。

许可证
GPL v3.0 或更高版本。
详见 LICENSE 文件（若未提供，请遵循 GPL-3.0 条款）。

