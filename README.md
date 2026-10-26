# SweepMate Agent · 扫地机器人问答与使用报告

[简体中文](README.md) | [English](README.en.md)

一个围绕扫地机器人场景的 LangGraph Agent：回答已入库知识中的问题，也能切换报告模式，查询用户清扫记录并整理为中文使用报告。

仓库提供两条路径：**离线固定演示**检查图、工具和数据链路，无需 Key；**Streamlit 在线模式**使用实际聊天与嵌入服务，支持自然语言问答。知识和清扫记录均带合成示例，便于区分演示数据与真实设备数据。

[离线跑一次](#先运行无需密钥的固定演示) · [在线问答](#启用在线问答) · [输出与数据](#输出与数据位置) · [Agent 原理](#react-智能体怎样工作)

## 先运行无需密钥的固定演示

准备 Python 3.11+，Windows PowerShell：

```powershell
git clone https://github.com/kayaduster607-jpg/sweepmate-agent.git
cd sweepmate-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 tools/offline_demo.py
```

不需要输入问题。脚本预先安排“切换报告模式 → 查询用户 1001、月份 2025-01 → 输出报告”的步骤，运行真实图与工具，模型响应由演示适配器提供。

完成时终端会出现工具事件及以“合成演示报告”为标题的最终文本。**它不会生成文件，也不能用来测试任意问题的模型理解能力。**

## 启用在线问答

### 配置服务与模型

检查 [config/rag.yml](config/rag.yml) 的 base_url、聊天模型和嵌入模型，必须与自己账号的服务一致。当前默认采用 SiliconFlow 兼容接口，变量叫 OPENAI_API_KEY 并不意味着任意 OpenAI Key 都适用。

在同一 PowerShell 终端中隐藏输入对应服务的 Key：

```powershell
$providerKey = Read-Host "Provider API key" -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new("", $providerKey).Password
```

### 入库，然后启动网页

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/ingest.py
.\.venv\Scripts\python.exe -X utf8 -m streamlit run app.py
```

先确认入库摘要中的新增、跳过、失败文件和分片数量；失败退出码为 1。入库调用嵌入服务，在线回答可能同时调用聊天与嵌入服务。默认模型名只是配置值，运行前确认服务端可用性与额度。

### 完成两种任务

打开 [http://127.0.0.1:8501](http://127.0.0.1:8501)：

| 在输入框发送 | 观察什么 | 得到什么 |
| --- | --- | --- |
| “根据示例知识库，漏扫场景应先检查哪些信息？” | 检索工具与页面执行状态 | 基于已入库资料的中文回答 |
| “为用户1001生成2025-01的合成演示报告。” | 报告模式切换、记录查询的 ID 与月份 | 包含合成标签的使用报告 |

工具执行区用于查看调用过程，外部回答区展示最终结果。未入库时只启动网页，不能视为知识问答准备完成；查不到指定月份的记录，也不应由模型编造统计。

## 输出与数据位置

| 内容 | 保存位置 | 是否自动生成下载文件 |
| --- | --- | --- |
| 离线演示 | 终端输出 | 否 |
| 网页回答与 Markdown 报告 | 当前会话内存 | 否，可手动复制保存 |
| 向量索引与去重状态 | `chroma_db/`、`md5.text` | 本机运行数据 |
| 示例知识与 120 条合成记录 | `data/knowledge/`、`data/external/records.example.csv` | 已随仓库提供 |

当前没有 Word / PDF 报告下载按钮，应用重启后不保留会话历史。天气、身份、城市和默认月份是模拟工具，不代表连接真实设备或实时服务。


## ReAct 智能体怎样工作

### 一个可见的状态循环

```text
START
  -> agent: choose an answer or tool calls
  -> tools: execute selected tools
  -> agent: inspect results and continue
  -> END: answer without further tool calls
```

`AgentState`包含两个字段：

| 字段 | 规则 | 用途 |
| --- | --- | --- |
| `messages` | 使用operator.add追加消息 | 保留用户消息、AI工具请求及ToolMessage结果 |
| `is_report_mode` | 普通布尔状态 | 决定下一轮加载客服提示词还是报告提示词 |

`_call_model()`读取模式，构造一条最新SystemMessage，再拼接非System历史消息，调用已绑定七个工具的模型。`_should_continue()`检查最后一条消息是否有tool_calls；有则进入工具节点，没有则结束。

`_execute_tools()`通过ToolNode执行。工具结果作为ToolMessage进入历史，模型能在下一轮看到结果；发生节点级异常时，代码为待完成的调用补上带相同ID的错误ToolMessage，避免仅返回空消息后留下未回答的工具请求。

### 事件类型与界面显示

```json
{"type":"thought","content":"Checking the demonstration records."}
```

| 事件 | 产生条件 | 界面位置 |
| --- | --- | --- |
| `thought` | 带工具调用的AI消息中存在行动说明 | 折叠执行区 |
| `log` | 工具节点返回ToolMessage | 折叠执行区，按状态显示成功或失败 |
| `answer` | 不再请求工具的AI消息 | 折叠区外的答案占位符 |
| `error` | 图执行异常被捕获 | 明确显示错误，不追加虚构答案 |

这里的thought是保留的事件名称，表示**模型公开输出的简短行动说明**，不是读取模型内部推理。提示词要求只给行动说明与回答。当前使用 `stream_mode="updates"` 接收节点完成后的更新，模型节点调用的是invoke，因此不把它描述为逐token流式输出。[LangGraph流模式说明](https://docs.langchain.com/oss/python/langgraph/streaming)

### 会话与循环边界

每个ReactAgent实例有自己的MemorySaver。默认thread_id为 `default_thread`，程序调用者可以显式提供不同thread_id；回归已验证不同线程历史分离。Streamlit将Agent保存在各自的session_state中，但这不等同于已经实现账号认证和持久化用户隔离。

```python
events = agent.execute_stream("Demo question", thread_id="demo-session")
for event in events:
    print(event["type"], event["content"])
```

一次调用从普通模式开始；同一线程的消息仍会保留。检查点只在内存，服务重启后消失。显式图递归上限为25步，它限制图执行步骤，不能当成25次工具调用或固定模型费用上限。[LangGraph检查点说明](https://docs.langchain.com/oss/python/langgraph/persistence)


## 知识库如何构建与检索

### 入库路径

```text
data/knowledge/*.txt or *.pdf
  -> load documents
  -> check file MD5
  -> detect FAQ or ordinary prose
  -> create chunks with source metadata
  -> request embeddings
  -> persist in local Chroma collection
  -> append successful file hash
```

程序只处理配置目录的直接子文件，不递归扫描下层知识目录。TXT按UTF-8读取；PDF通过PyPDFLoader提取已有文本。当前没有OCR，扫描图片PDF可能没有可用文本，不能由“支持PDF扩展名”推导出“能识别所有扫描件”。

FAQ检测要求同一文本中至少出现5处“行首数字、点、空格”。识别为FAQ后按编号边界切分，保留原文档的source/page元数据；其他文本使用RecursiveCharacterTextSplitter。默认参数如下：

| 项目 | 当前值 | 意义 |
| --- | --- | --- |
| 普通文本chunk_size | `300` | 按字符长度计算，非token数量 |
| 普通文本chunk_overlap | `150` | 相邻普通分片的重叠字符数 |
| 检索k | `3` | 取最多3条相似度结果 |
| collection | `agent` | Chroma集合名称 |
| 本地持久目录 | `chroma_db` | 相对项目根目录解析 |

FAQ按问答结构切分，不额外保证每段小于300字符。配置里的separators默认按普通分隔符处理；其中类似正则的字符串也不会自动成为正则规则，FAQ识别才使用单独的正则表达式。

### 查询路径

`rag_summarize(query)`先调用retriever取片段，按参考资料编号组合正文和元数据，再把query与context放进RAG提示词，经模型总结后返回字符串。外层Agent读到这个工具结果后，继续组织最终答案。

```text
User question
  -> agent model requests rag_summarize
  -> query embedding + Chroma retrieval
  -> RAG summarization model
  -> ToolMessage
  -> agent model writes the final answer
```

所以常见的一次RAG工具往返可能包含三次聊天模型调用：工具前的决策、RAG内部总结、工具后的回答，另有查询嵌入请求。实际次数取决于工具选择与循环，不能把整轮都算成一次API调用。

嵌入适配设置 `check_embedding_ctx_length=False`，向兼容服务发送文本，避免套用OpenAI专用token编号预处理；这不意味着取消了服务商自己的长度限制。没有实现重排模型、混合检索、相关性阈值或强制逐条引用；提示词中的“只依据资料”也不等于已经证明不会产生幻觉。

### 去重能做什么，不能做什么

文件向量成功写入后才记录MD5，因此正常重复入库会跳过已处理文件。但Chroma与文本哈希记录不是同一事务：进程崩溃可能留下部分写入。更改文件后会新增分片，当前没有删除旧版本分片；删除文件也不会自动删除旧向量。

如果更换嵌入模型、集合或分片规则，应重建对应索引，并使用匹配的去重记录。只删除数据库而保留旧 `md5.text` 会让程序误以为文件已经入库；只删除哈希记录可能重复加入旧内容。重建前应备份自己需要保留的数据，不要把这两个文件当成互不相关的缓存。


## 工具能力与演示边界

| 工具 | 当前输入与输出 | 实现状态 |
| --- | --- | --- |
| `rag_summarize` | query -> 依据检索资料生成的字符串 | 真实RAG调用链；在线使用需模型服务 |
| `get_weather` | city -> 固定天气文本 | 演示值，非实时天气API |
| `get_user_location` | 无参数 -> 三个预设城市之一 | 随机演示，不是定位 |
| `get_user_id` | 无参数 -> 1001至1010中的一个ID | 随机合成身份，不是登录用户 |
| `get_current_month` | 无参数 -> 2025年的一个月份 | 随机演示月份，不是当前日期 |
| `fetch_external_data` | user_id、month -> JSON文本或空字符串 | 读取配置CSV；发布数据均为合成 |
| `fill_context_for_report` | 无参数 -> 标记工具返回值 | 成功后由工具节点设置报告模式 |

这些工具没有设备远程控制能力。报告工具也不会自动给其他工具注入隐藏参数；“获取ID、月份、查记录”等步骤依赖模型遵守提示词，不是一个已经强制验证所有业务顺序的工作流。


## 报告模式如何切换

```text
Report request
  -> keep explicit user ID and month, or choose demo values
  -> call fill_context_for_report
  -> successful ToolMessage sets is_report_mode = true
  -> next agent node loads report_prompt.txt
  -> call fetch_external_data
  -> produce a Markdown demonstration report
```

模式切换发生在图节点逻辑，当前运行路径不依赖一套额外middleware装饰器。节点只在报告工具成功时更新标记；失败不会伪装成已经切换。

CSV字段契约如下，示例中不包含真实用户或设备数据：

```csv
user_id,feature,efficiency,consumables,comparison,month
1001,synthetic usage,synthetic duration,synthetic status,synthetic comparison,2025-01
```

文件通过csv.DictReader解析，带引号的逗号不会被误拆列；缺少必需字段会报告错误。首次查询将记录读入内存缓存，因此修改CSV后应重启应用。重复的同用户同月份记录以文件中后出现的条目为准。

发布示例覆盖10个合成ID与2025年的12个月，共120条记录，确保演示工具的随机组合能查到示例。数据只包含特征、效率、耗材和对比字符串，没有真实清扫轨迹、传感器数据或身份信息。


## 提示词怎样组织

| 模板 | 用途 | 输入 |
| --- | --- | --- |
| `main_prompt.txt` | 普通客服、工具说明和演示边界 | 作为系统消息与历史一起发送 |
| `rag_summarize.txt` | 根据参考资料总结问题 | `input`、`context` |
| `report_prompt.txt` | 使用记录的报告组织方式 | 从历史与工具结果读取数据 |

客服和报告模板在相应模型节点加载，RAG模板在RAG服务构造时加载；修改RAG模板后应重启服务。公开版本明确区分合成与真实信息，保留“资料不足时说明”的要求。它没有将提示词当成身份认证或数据访问控制。


## 配置与数据位置

| 文件或位置 | 内容 | 是否进入仓库 |
| --- | --- | --- |
| `config/rag.yml` | base_url、聊天和嵌入模型名 | 是，不含Key |
| `config/chroma.yml` | 分片、k、集合、持久目录与去重路径 | 是 |
| `config/agent.yml` | CSV数据路径 | 是，默认指向合成示例 |
| `config/prompts.yml` | 三类提示词路径 | 是 |
| `data/knowledge/demo_*.txt` | 新编写的两份示例知识 | 是 |
| `data/external/records.example.csv` | 120条合成记录 | 是 |
| `chroma_db/`、`md5.text` | 本机生成的索引与去重状态 | 否 |
| `logs/` | 按日期保存的日志 | 否 |
| `.streamlit/config.toml` | 127.0.0.1:8501与关闭使用统计 | 是 |

配置在模块导入时读取，修改模型或路径后应重启应用。默认日志不再打印完整RAG提示词，但异常日志仍可能包含上下文或路径，公开故障材料前需要脱敏。


## 常见问题

| 表现 | 优先检查 |
| --- | --- |
| 启动提示缺少API Key | 在启动该应用的同一终端设置OPENAI_API_KEY；离线验证无需真实Key |
| Key有值但模型返回401或403 | Key是否属于base_url对应服务，账号权限是否正常 |
| 模型返回404或不支持工具调用 | 核对服务商模型ID与tool calling支持，不只检查客户端包版本 |
| 资料检索为空 | 是否先运行入库，知识目录是否含可提取文本，索引与哈希记录是否匹配 |
| PDF没内容 | 扫描件可能需要另做OCR，当前加载器不提供该能力 |
| 改嵌入模型后出现维度错误 | 新旧索引维度可能不同，需要一致地重建集合与去重状态 |
| 报告的身份或月份看起来随机 | 当前默认工具本来就是演示；明确提供ID和月份，或接入自己的认证与日期服务 |
| 网页历史重启后消失 | MemorySaver与Streamlit session_state都不提供长期会话存储 |
| 调用多次工具后报递归限制 | 检查工具是否连续失败、模型是否满足退出条件；不要仅盲目调大上限 |
| Windows终端中文显示异常 | 使用示例中的 `-X utf8`；文件和README按UTF-8保存 |

当前按可信本机学习环境运行，没有账号鉴权、知识访问权限、配额、限流或生产审计系统。共享部署前需要单独设计这些能力，并评估检索内容发送给模型服务的范围。



## 验证与源码入口

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/verify.py
```

离线检查用于验证确定性图与工具流程，不证明真实服务模型可用。图入口在 `agent/react_agent.py`，演示在 `tools/offline_demo.py`，入库在 `tools/ingest.py`；修改提示词、模型或配置后应重启应用。日志可能包含路径或上下文，分享错误时先脱敏。
