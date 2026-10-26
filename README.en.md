# SweepMate Agent · Robot Vacuum Q&A and Usage Reports

[简体中文](README.md) | [English](README.en.md)

A LangGraph agent for robot-vacuum scenarios: answer questions using ingested knowledge, or switch to report mode, query cleaning records, and organize a Chinese usage report.

Two paths are provided: a **fixed offline demonstration** checks graph, tools, and data without a key; **online Streamlit mode** uses real chat and embedding services for natural-language Q&A. Both knowledge and cleaning records include synthetic examples, keeping demo data distinct from real device data.

[Offline demo](#run-the-fixed-key-free-demo-first) · [Online Q&A](#enable-online-qa) · [Outputs](#outputs-and-data-locations) · [Agent design](#how-the-react-agent-works)

## Run the fixed key-free demo first

Prepare Python 3.11+. In Windows PowerShell:

```powershell
git clone https://github.com/kayaduster607-jpg/sweepmate-agent.git
cd sweepmate-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 tools/offline_demo.py
```

No question input is needed. The script prearranges “switch to report mode → query user 1001 and month 2025-01 → produce report,” running the real graph and tools with a demonstration model adapter.

The terminal shows tool events and final text titled “合成演示报告” (synthetic demo report). **It creates no file and does not test model understanding of arbitrary questions.**

## Enable online Q&A

### Configure service and models

Check base_url, chat model, and embedding model in [config/rag.yml](config/rag.yml) against your provider account. Defaults use a SiliconFlow-compatible endpoint; the name OPENAI_API_KEY does not mean every OpenAI key works there.

Enter that provider's key through a hidden prompt in the same PowerShell terminal:

```powershell
$providerKey = Read-Host "Provider API key" -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new("", $providerKey).Password
```

### Ingest, then start the interface

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/ingest.py
.\.venv\Scripts\python.exe -X utf8 -m streamlit run app.py
```

Check added, skipped, and failed file counts and chunk totals in the ingestion summary; failure exits with code 1. Ingestion calls embeddings, and online answering may call both chat and embeddings. Default model names are configuration values, so verify provider availability and quota first.

### Complete both tasks

Open [http://127.0.0.1:8501](http://127.0.0.1:8501):

| Send in the input box | Observe | Result |
| --- | --- | --- |
| “根据示例知识库，漏扫场景应先检查哪些信息？” (what should be checked first for missed cleaning?) | Retrieval tools and execution state | Chinese answer grounded in ingested materials |
| “为用户1001生成2025-01的合成演示报告。” (generate a synthetic report for user 1001, 2025-01) | Report-mode switch, queried ID and month | Usage report labeled synthetic |

The execution area shows calls; the external answer area shows the final result. Starting the page without ingestion does not prepare knowledge Q&A. Missing monthly records must not be replaced with invented statistics.

## Outputs and data locations

| Content | Location | Automatic downloadable file? |
| --- | --- | --- |
| Offline demo | Terminal | No |
| Web answers and Markdown reports | Current session memory | No; copy manually |
| Vector index and deduplication state | `chroma_db/`, `md5.text` | Local runtime data |
| Sample knowledge and 120 synthetic records | `data/knowledge/`, `data/external/records.example.csv` | Included in repository |

There is no Word / PDF download button, and restart loses chat history. Weather, identity, city, and default-month tools are simulations, not real device connections or live services.

## How the ReAct agent works

### A visible state loop

```text
START
  -> agent: choose an answer or tool calls
  -> tools: execute selected tools
  -> agent: inspect results and continue
  -> END: answer without further tool calls
```

`AgentState` has two fields:

| Field | Rule | Purpose |
| --- | --- | --- |
| `messages` | Append with operator.add | User messages, AI tool requests, and ToolMessage results |
| `is_report_mode` | Boolean state | Choose customer-service or report prompt next round |

`_call_model()` reads the mode, constructs a current SystemMessage, appends non-System history, and invokes the model bound to seven tools. `_should_continue()` checks the last message's tool_calls: go to the tool node if present, otherwise finish.

`_execute_tools()` uses ToolNode. ToolMessage results enter history for the next model round. On node-level exceptions, pending calls receive error ToolMessages with matching IDs so an empty response does not leave unanswered tool requests.

### Events and interface

```json
{"type":"thought","content":"Checking the demonstration records."}
```

| Event | Trigger | Interface location |
| --- | --- | --- |
| `thought` | Public action explanation in an AI message with tool calls | Collapsible execution area |
| `log` | Tool node returns a ToolMessage | Collapsible area with success / failure state |
| `answer` | AI message requests no further tools | Answer placeholder outside the collapsed area |
| `error` | Graph exception is caught | Explicit error, without a fabricated answer |

`thought` is the retained event name for a **brief action explanation publicly output by the model**, not access to hidden reasoning. Prompts request action explanations and answers only. `stream_mode="updates"` receives completed node updates, while model nodes call invoke; this is not token-by-token streaming. See [LangGraph streaming](https://docs.langchain.com/oss/python/langgraph/streaming).

### Sessions and loop limits

Each ReactAgent instance owns a MemorySaver. The default thread_id is `default_thread`; callers can supply distinct values, and regression tests verify separate histories. Streamlit keeps an Agent in each session_state, which is not account authentication or persistent user isolation.

```python
events = agent.execute_stream("Demo question", thread_id="demo-session")
for event in events:
    print(event["type"], event["content"])
```

Each invocation begins in normal mode while same-thread messages remain. Checkpoints exist only in memory and disappear on restart. The explicit recursion limit is 25 graph steps, not 25 tool calls or a fixed model-cost cap. See [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence).

## Knowledge ingestion and retrieval

### Ingestion

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

Only direct child files of the configured directory are processed, without recursive knowledge-folder traversal. TXT uses UTF-8; PyPDFLoader extracts existing PDF text. There is no OCR, so accepting PDF extensions does not imply support for every scan.

FAQ detection requires at least 5 occurrences of line-start digits followed by a dot and space in the same text. Recognized FAQs split at numbered boundaries and retain source/page metadata. Other content uses RecursiveCharacterTextSplitter:

| Setting | Value | Meaning |
| --- | --- | --- |
| Ordinary chunk_size | `300` | Characters, not tokens |
| Ordinary chunk_overlap | `150` | Overlap characters |
| Retrieval k | `3` | Up to 3 similarity results |
| collection | `agent` | Chroma collection |
| Local persistence | `chroma_db` | Resolved relative to project root |

FAQ splitting follows question structure and does not guarantee chunks under 300 characters. Configured separators are ordinary separators by default; regex-looking strings do not automatically become regex rules. FAQ recognition uses its own regex.

### Queries

`rag_summarize(query)` retrieves passages, assembles numbered reference text and metadata, fills query / context into the RAG prompt, and returns a model-generated summary string. The outer agent then uses that tool result to organize the final answer.

```text
User question
  -> agent model requests rag_summarize
  -> query embedding + Chroma retrieval
  -> RAG summarization model
  -> ToolMessage
  -> agent model writes the final answer
```

A common RAG tool round trip can therefore involve three chat calls—decision, internal RAG summary, and final answer—plus query embedding. Actual counts depend on tool choices and loops; the whole round is not necessarily one API call.

The embedding adapter sets `check_embedding_ctx_length=False` to send text to compatible services instead of OpenAI-specific token-ID preprocessing. Provider length limits still apply. Reranking, hybrid retrieval, relevance thresholds, and enforced per-item citations are not implemented; a “use only the material” prompt does not establish freedom from hallucination.

### Deduplication limits

MD5 is recorded only after vectors are successfully written, allowing ordinary repeat ingestion to skip processed files. Chroma and the text hash record are not one transaction, so crashes can leave partial writes. Changed files add chunks without deleting old versions; deleted files do not automatically remove old vectors.

Changing embedding model, collection, or chunking rules requires rebuilding the corresponding index and matching deduplication state. Deleting only the database while keeping `md5.text` can falsely mark files ingested; deleting only hashes can duplicate old content. Back up needed data before rebuilding and treat both as related state.

## Tools and demo boundaries

| Tool | Input → output | Status |
| --- | --- | --- |
| `rag_summarize` | query → summary string grounded in retrieved material | Real RAG chain; online mode needs model services |
| `get_weather` | city → fixed weather text | Demo, not live weather |
| `get_user_location` | No arguments → one of three preset cities | Random demo, not geolocation |
| `get_user_id` | No arguments → ID from 1001–1010 | Synthetic random identity, not signed-in user |
| `get_current_month` | No arguments → a month in 2025 | Random demo month, not current date |
| `fetch_external_data` | user_id, month → JSON text or empty string | Reads configured CSV; published data is synthetic |
| `fill_context_for_report` | No arguments → marker result | Tool node enables report mode after success |

Tools cannot remotely control devices. The report tool does not secretly inject parameters into other tools. Obtaining IDs, months, and records relies on model adherence to prompts, not a workflow that enforces every business step.

## Switching report mode

```text
Report request
  -> keep explicit user ID and month, or choose demo values
  -> call fill_context_for_report
  -> successful ToolMessage sets is_report_mode = true
  -> next agent node loads report_prompt.txt
  -> call fetch_external_data
  -> produce a Markdown demonstration report
```

Mode switches in graph-node logic; the current path does not depend on extra middleware decorators. The flag changes only after the report tool succeeds, never pretending a failed switch worked.

CSV field contract, with no real user or device data:

```csv
user_id,feature,efficiency,consumables,comparison,month
1001,synthetic usage,synthetic duration,synthetic status,synthetic comparison,2025-01
```

csv.DictReader preserves quoted commas; missing required fields produce errors. Records are cached on first query, so restart after changing CSV. For duplicate user / month rows, the later file entry wins.

The published example covers 10 synthetic IDs × 12 months in 2025 = 120 records, ensuring random demo combinations find records. Fields contain feature, efficiency, consumable, and comparison strings, not real cleaning trajectories, sensor data, or identity information.

## Prompt organization

| Template | Purpose | Input |
| --- | --- | --- |
| `main_prompt.txt` | Customer service, tools, demo boundaries | System message plus history |
| `rag_summarize.txt` | Summarize from reference material | `input`, `context` |
| `report_prompt.txt` | Organize a usage report | History and tool results |

Customer-service and report templates load in their respective model nodes; the RAG template loads when its service is constructed, so restart after editing it. The public version distinguishes synthetic and real information and requires disclosure of insufficient material. Prompts are not authentication or data-access controls.

## Configuration and storage

| File / location | Contents | Committed? |
| --- | --- | --- |
| `config/rag.yml` | base_url and chat / embedding model names | Yes, without key |
| `config/chroma.yml` | Chunking, k, collection, persistence, hash path | Yes |
| `config/agent.yml` | CSV path | Yes, defaults to synthetic sample |
| `config/prompts.yml` | Three prompt paths | Yes |
| `data/knowledge/demo_*.txt` | Two newly authored sample documents | Yes |
| `data/external/records.example.csv` | 120 synthetic records | Yes |
| `chroma_db/`, `md5.text` | Locally generated index / deduplication | No |
| `logs/` | Dated logs | No |
| `.streamlit/config.toml` | 127.0.0.1:8501 and disabled usage statistics | Yes |

Configuration loads during module import: restart after changing models or paths. Default logs no longer print full RAG prompts, but exceptions can still contain context or paths; sanitize before publishing diagnostics.

## Common issues

| Symptom | First check |
| --- | --- |
| Missing API key | Set OPENAI_API_KEY in the starting terminal; offline checks need no real key |
| Key set but 401 / 403 | Key belongs to the base_url provider and account has access |
| 404 or unsupported tool calling | Check provider model ID and tool-calling support, not only client version |
| Empty retrieval | Ingestion ran, extractable text exists, index matches hashes |
| Empty PDF content | Scans need separate OCR |
| Dimension error after embedding change | Rebuild collection and deduplication state consistently |
| Random identity / month in report | Defaults are demos; provide explicit ID / month or integrate real identity / date services |
| History lost on restart | MemorySaver and Streamlit session_state are not long-term stores |
| Recursion limit after repeated tools | Inspect repeated tool failure and exit conditions before raising limits |
| Garbled Windows terminal Chinese | Use `-X utf8`; files and README use UTF-8 |

This assumes a trusted local learning environment, without account authentication, knowledge permissions, quotas, rate limiting, or production audit infrastructure. Design these separately before shared deployment and assess what retrieved content goes to model services.

## Verification and source entry points

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/verify.py
```

Offline checks establish deterministic graph and tool behavior, not availability of real model services. The graph is in `agent/react_agent.py`, demo in `tools/offline_demo.py`, and ingestion in `tools/ingest.py`. Restart after prompt, model, or configuration changes. Sanitize paths and context before sharing errors.
