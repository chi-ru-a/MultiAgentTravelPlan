实现了websocket但却没有使用吗？



## 模型/工具/数据库

问答模型：qwen-max

嵌入模型：qwen3.7-text-embedding-flash



前端：React

后端：FastAPI、LangChain 、LangGraph 

向量数据库：Qdrant



工具：航班、天气、知识库检索

天气查询用的是 ZHIPU 的联网搜索

航班查询用的是模拟数据，可以接入12306的MCP

## 项目介绍

### 多 Agent 旅行规划系统——项目介绍

这个项目是一个基于 React、FastAPI、LangChain 和 LangGraph 开发的多 Agent 旅行规划系统，主要解决用户一个问题中包含多个不同业务需求时，如何进行任务拆分、并行执行和结果整合的问题。

在整体架构上，后端采用 Supervisor + Worker Agent + Synthesizer 的多 Agent 协作模式。

**首先是请求接收和任务调度。**

用户在前端输入问题后，React 通过 Fetch 向 FastAPI 发送 HTTP POST 请求。后端接收到请求后，将用户消息封装成 LangChain 的 HumanMessage，并构建 LangGraph 的初始 State，然后调用工作流执行。

**其次是 Supervisor 意图识别和任务分配。**

Supervisor 采用关键词匹配和 LLM 意图识别相结合的双层路由策略。对于能够明确匹配的简单请求，直接选择对应的 Agent；对于包含多个业务意图或者语义不明确的请求，再调用 LLM 分析用户需求，生成任务列表和执行计划。

如果是多个独立任务，就通过 LangGraph 的 Send API 将任务并行分发给不同的 Worker Agent。

**然后是 Worker Agent 执行业务任务。**

项目针对不同业务创建了专业 Agent，包括班次查询、天气查询、知识库检索和闲聊 Agent。每个 Agent 通过 LangGraph 的 ReAct 模式绑定对应的 LangChain Tool，由大模型根据任务需求提取工具参数并调用工具。

例如，班次查询 Agent 负责提取出发地、目的地和日期，调用班次查询服务；天气 Agent 根据城市调用联网搜索服务；知识库 Agent 则调用 RAG 检索工具获取相关业务政策。

**接下来是 Synthesizer 汇总。**

多个 Worker 执行完成后，将结果写入 LangGraph 的共享 State。项目通过自定义 Reducer 实现并行结果聚合，Synthesizer 获取所有 Agent 的执行结果，再调用 LLM 进行统一整理，生成最终回答。

**最后是流式输出。**

项目采用 SSE 实现流式响应。通过 LangGraph 的自定义 Stream Writer 推送 Agent 执行进度和回答事件，后端使用 StreamingResponse 持续返回数据，前端通过 Fetch ReadableStream 解析事件并更新页面，实现思考过程和回答内容的实时展示。

在知识库方面，项目基于 Embedding 和 Qdrant 实现 RAG，支持稠密向量和稀疏向量混合检索。用户提出业务政策问题后，知识库工具将问题向量化，从向量数据库中检索相关知识片段，再交给 LLM 结合用户问题生成回答。

======================



我参与开发的是一个基于 React、FastAPI、LangChain 和 LangGraph 构建的多 Agent 旅行服务系统。

这个项目主要解决的是用户在一次对话中可能提出多个不同类型需求的问题，例如同时查询班次、天气以及出行政策等。

在整体架构上，我采用 Supervisor + Worker Agent + Synthesizer 的协作模式。

首先，由 Supervisor 负责识别用户意图和任务拆分，采用关键词匹配与 LLM 相结合的双层路由策略，判断应该调用哪些专业 Agent。

然后，由不同的 Worker Agent 执行具体任务，例如班次查询、天气查询和知识库咨询。对于多个独立任务，使用 LangGraph 的 Send API 实现并行调度，并通过共享状态 State 和 Reducer 规约器聚合各个 Agent 的执行结果。

最后，由 Synthesizer 对多个 Agent 的结果进行整合，生成统一的回复。

在工具管理方面，我通过 ToolRegistry 统一注册和管理工具，方便后续扩展新的业务能力。

在知识库方面，使用 Embedding 模型将文本转换为向量，并结合 Qdrant 等向量数据库实现知识检索，为退票、改签和票价政策等问题提供回答依据。

此外，后端通过 FastAPI 提供接口，利用 SSE 实现流式响应，前端使用 React 接收流式事件并实时展示执行过程和最终结果。





**工作流编排**

在整体架构上，我采用 Supervisor + Worker Agent + Synthesizer 的协作模式。

首先，由 Supervisor 负责识别用户意图和任务拆分，采用关键词匹配与 LLM 相结合的双层路由策略，判断应该调用哪些 Worker Agent。

如果需要调用多个 Worker Agent，使用 LangGraph 的 Send API 实现并行调度。

接着由不同的 Worker Agent 执行具体任务，包含四个 Worker Agent：天气查询、航班查询、政策服务咨询、闲聊。将 Worker Agent 的执行结果放到共享状态的 agent_outputs 字段当中，对该字段使用自定义规约器实现追加。

最后，多个 Worker Agent 并行扇入到 Synthesizer 节点，该节点对多个 Worker Agent 的结果进行整合，再调用 LLM 生成统一的回复。

**工具管理**

在工具管理方面，我定义了 ToolRegistry 类，在里面定义了各种方法，比如 获取工具配置、获取工具实例、获取所有工具、获取销毁工具，通过 ToolRegistry 类和它方法来统一注册和管理工具；

在用 create_worker_agents() 创建 Worker Agent 时，就是获取所有工具并遍历，通过 LangGraph 的 create_react_agent()，传入模型、工具、系统提示词，挨个把工具注册为 Agent；

系统提示词我定义为了一个字典，key 是工具的 name，value 是这个 Worker Agent 的系统提示词；

这样做，新增一个 Worker Agent，只需要定义一个工具，再调用 ToolRegistry 的 registry() 方法，再新增一个系统提示词，系统就会自动的将这个工具注册为一个 Agent，如果用户的问题需要用到这个 Agent，Supervisor 可以直接路由到这个 Agent；



所有的工具都在 _tools 列表当中，注销一个工具，就是把这个工具从这个列表中移除，自然也就没有了这个 Worker Agent，Supervisor 也不会再路由到它

**知识库问答**

实际情况是：没有文档、没有加载、没有切分，没有使用LangChain的Embeddings、VectorStore、Retriever API

自己实现了Embeddings、对Qdrant数据库的增【入口】删查【检索】

不能这样说，这样是给自己挖坑，能问的太多了，随便说一条自己都不知道怎么说



我首先使用爬虫爬取了一些航空公司的政策页面，维护一个政策页面配置文件，包含url、公司名称、政策类型什么的，通过 requests 去爬取这些页面的内容，拿到 HTML 后，通过 BeautifulSoup 解析网页，去除导航栏、菜单、广告、页脚这些无关信息，保留政策正文、标题层级、段落等结构，政策里经常包含表格，对表格单独提取，转换成 Markdown 格式，最终得到结构化的政策文本，存到 Markdown 文件中；

之后使用 LangChain 的加载器加载政策文件为 Document 对象，把URL、公式名称、政策类型这些元数据给放到 Document 中

再使用 LangChain 的 RecursiveCharacterTextSplitter 按标题、段落、标点符号递归切分，尽量保持语义完整

切分之后，再使用 LangChain 的 DashScopeEmbeddings API 将切分后的文本向量化

再使用 LangChain 提供的 QdrantVectorStore 将向量、原始文本、元数据一起存放到向量库

在检索阶段，用 embed_query() 将用户问题向量化，再使用 LangChain 的 EnsembleRetriever 进行混合检索；因为票价、退票、改签这种服务政策很适合关键词查询，但也为了防止关键词检索不到，因此使用混合检索；EnsembleRetriever 的底层是使用了 RRF 倒数排名融合算法来融合向量检索和关键词检索的结果；【EnsembleRetriever 会自动进行合并去重（根据文档块的唯一id）】

取检索内容的 topk，这里取的是5，放到事先定义的提示词模版当中，和用户的问题一起发给LLM，由模型生成增强后的回答

最后对模型生成的回答做了一些后处理，包括

* 敏感词过滤：我这里目前是定义了一个敏感词列表来过滤，如果回答中包含敏感词，就返回默认回答
  * 定义列表过滤关键词，这种做法不全面且容易被穿透，LangChain 也提供了 RunnableLambda，可以把自己的过滤函数接入整个 RAG 链；也可以接入专门的内容审核模型来过滤
* 回答包含引用来源：在检索的时候保留每个 Document 的元数据，把来源信息一块给到模型让其生成带引用的回答？【要在提示词中要求，不能让模型凭空生成引用链接】【如果要做到句子级引用，可以让模型在生成答案时同时返回引用文档 ID，再由后端校验 ID 是否属于本次检索结果。】



**流式输出**

通过 stream_writer() 产生流式事件、通过 workflow.astream(stream_mode="custom") 接收自定义事件、通过 StreamingResponse 持续向前端推送 SSE、前端通过 response.body.getReader() 不断读取数据并展示；



**模型/工具/数据库**

为什么这样选型？

问答模型：qwen-max

嵌入模型：qwen3.7-text-embedding-flash



前端：React

后端：FastAPI、LangChain 、LangGraph 

向量数据库：Qdrant



工具：航班、天气、知识库检索

天气查询用的是 ZHIPU 的联网搜索

航班查询用的是模拟数据，可以接入12306的MCP





**切分策略**

```python
# 模型上下文有限，因此要设置chunk_size和chunk_overlap
# 按分隔符切分，能满足chunk_size就停止，不满足就用下一个分隔符，所有分隔符都无法满足chunk_size，就按chunk_size截断切分，并保留chunk_overlap的重叠
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
)
```

**文本向量化**

Embeddings API

* embed_documents(texts)：入库，多个文档转换为向量
* embed_query(text)：检索，用户问题转换为向量

**向量存储**

```python
# 这会将向量、原始文本、metadata 作为 Payload 一起存储
vector_store = QdrantVectorStore.from_documents(
    documents=split_docs,
    embedding=embeddings,
    url="http://localhost:6333",
    collection_name="travel_policy"
)
```

![image-20261111173511787](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261111173511787.png)

**混合检索**

```python
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

# 向量检索
vector_retriever = vector_store.as_retriever(
    search_kwargs={"k": 10}
)

# BM25关键词检索
bm25_retriever = BM25Retriever.from_documents(
    split_docs
)
bm25_retriever.k = 10

# 混合检索
ensemble_retriever = EnsembleRetriever(
    retrievers=[
        vector_retriever,
        bm25_retriever
    ],
    weights=[0.6, 0.4]
)

docs = ensemble_retriever.invoke(
    "南航 CZ3101 航班退票规定"
)
```









## 用户问题到响应整体流程

【session_id、thread_id，并通过 InMemorySaver 持久化记忆】；工作流在启动时就预热过；Synthesizer 节点内部会判断，如果是单个 Worker Agent 就认为输出过了，不做处理，直接穿透；关键词匹配：我在统一注册工具时，定义了一个 BaseModel，给每个工具都加了一些配置信息，包括名字、功能描述、关键词、优先级、必要的参数等等，因此可以进行关键词匹配；

![image-20261106125724589](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106125724589.png)



用户输入问题，比如“帮我查询明天北京到上海的高铁，顺便查询一下上海明天的天气”，向后端发起请求，后端的 `chat_stream` 接收请求，获取预热后的工作流、生成会话 id 用于区分不同会话、把用户问题封装成 HumanMessage、调用 workflow.astream() 执行工作流、再用 StreamingResponse 返回 SSE 数据；

用户的问题进入工作流之后，首先进入 Synthesizer 节点，该节点负责识别用户意图和任务拆分，在这里我采用关键词匹配与 LLM 相结合的双层路由策略，具体是对每个工具定义了一些关键词，如果问题比较简单，进行关键词匹配，如果能匹配到就不需要再走 LLM，节省成本和响应时间，如果问题比较复杂，还是要走 LLM 进行意图识别的；识别到用户意图之后，如果不需要执行任务直接走到 END 节点，如果需要执行任务，则分发任务给对应的 Worker Agent；如果是单个任务，对应的 Worker Agent 直接把结果流式输出到前端，如果是多个 Worker Agent，则用 LangGraph 的 send 并行扇出多个任务，并由 Synthesizer 节点汇总结果之后，再流式输出到前端；



多个 Agent 是并行阻塞式调用，结果都存放在共享状态的 agent_outputs 字段中，为了避免结果被覆盖，用 Annotated[list, _reset_on_empty] 指定了自定义的规约器，对 多个 Agent 的结果进行合并；

Synthesizer 汇总：根据结果数量，0、1个不汇总，多个结果，预设了一个提示词模版，把多个结果对变量替换，再调用 LLM 汇总；

流式输出：单个 Worker Agent 和 Synthesizer 节点产生流式事件、再用 StreamingResponse 将事件包装成 SSE 返回给前端、前端解析 SSE 并展示；

流式输出：通过 stream_writer() 产生流式事件、通过 workflow.astream(stream_mode="custom") 接收自定义事件、通过 StreamingResponse 持续向前端推送 SSE、前端通过 response.body.getReader() 不断读取数据并展示；

`InMemorySaver` + `thread_id` 持久化 checkpointer 

新增一个工具：只需要新建一个工具、注册到 ToolRegistry、再添加系统提示词，create_worker_agents() 会自动从注册中心创建新 Agent 并加入工作流图，Supervisor 会根据工具关键词以及工具描述，自动将相关请求路由到新 Agent。



## 踩坑

![image-20261106143953511](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106143953511.png)

![image-20261106144405820](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106144405820.png)

有记忆的，清空的是agent的回复，message字段并没有动；

不清空，每一轮的agent_outpus都会带着之前轮的agent输出，汇总结果在汇总时就会包含之前轮的回复，成本高还不对；

![image-20261106144753910](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106144753910.png)



## LangChain内置RAG API

![image-20261111170750613](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261111170750613.png)

![image-20261111170758841](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261111170758841.png)

![image-20261111170805747](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261111170805747.png)

![image-20261111170815923](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261111170815923.png)

![image-20261111170824004](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261111170824004.png)



## Qdrant 数据库与 RAG 流程

Collection：集合、表

Point：一条数据，id【内容的 MD5 哈希，天然去重】、向量 Vector、元数据 Payload

Payload：自定义的 JSON 格式的元数据

基础操作：存【put 请求】、取【get 或 post 请求】、删【delete 请求】，client 发的嘛



加载：对应的加载器，PDF、word、txt、md

切分：RecursiveCharacterTextSplitter 递归字符切分、块大小【3000字符】、overlap【块大小的10%~20%，比如15%】、分隔符

千问的嵌入模型、给块加元数据【原始文本、标题、来源】、存入 Qdrant 数据库

用户问题查询重写、查询扩展【如果没有现成实现，可以用提示词调大模型】，VectorEmbeddingsAccesserProxy 这个代理对用户问题向量化，再去向量库查询，默认返回前5条，交给 知识库Agent，进行检索增强

```
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=[
        "\n\n",
        "\n",
        "。",
        "！",
        "？",
        "；",
        "，",
        ""
    ]
)
```

给知识库agent使用的工具只有查询search！！！

但自己实现了完整的操作 Qdrant 数据库的方法，查询、新增、删除；手写 HTTP 请求操作  Qdrant 数据库；

查询给agent用，新增用于切分向量化再存入数据库，删除可以管理员删除过期文档【并没有实现角色系统，这是扩展的点】；

但是，为什么不用LangChain提供的落库和检索接口？

* LangChain的封装是一层黑盒，也是写死的，无法自己去添加更多的控制，也会屏蔽掉很多 Qdrant 原生的强大能力
* 可以少引入一些依赖
* 业务逻辑与框架解耦，后续换框架依然可以复用这些代码



统一格式：Document 对象或其列表

![image-20261106140908670](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106140908670.png)

![image-20261106141010357](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106141010357.png)

![image-20261106141056111](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106141056111.png)

![image-20261106141235588](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106141235588.png)

















![image-20261106134520421](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106134520421.png)



![image-20261106132834993](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106132834993.png)

![image-20261106132917276](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106132917276.png)

![image-20261106133008715](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106133008715.png)



## 工具

### 知识库工具流程

![image-20261106120847922](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106120847922.png)



### 查其他工具

下面这三种图是通用的 React Agent 的思路，但不适合本项目；

本项目由 Supervisor 这个节点来识别用户意图，决定走哪些 Worker Agent，然后走到对应的 Worker Agent，这些 Agent 是 React 结构的，但就只有一个工具，是不会根据结果再去思考调用别的工具的，它们能调的就只有各自的一个工具；

但也确实是 React 结构，会根据结果进行判断，是否需要再次调用；

![image-20261106130742569](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106130742569.png)

![image-20261106130824456](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106130824456.png)

![image-20261106130928822](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106130928822.png)



![image-20261106130101031](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106130101031.png)

![image-20261106130210753](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106130210753.png)

![image-20261106130257036](C:\Users\chen\AppData\Roaming\Typora\typora-user-images\image-20261106130257036.png)

## 前端

前端本质上只干了**三件事**：**把界面画出来（UI）、把用户的话发给后端（网络请求）、把后端返回的字一个个蹦出来（流式渲染）**。

**向后端发起请求 -> 解析后端响应数据 -> 渲染界面**



底层通信

- 因为这个项目后端不仅返回最终结果，还返回了 Supervisor 的路由、Agent 的思考过程。所以前端没有用普通的 Axios，而是**基于原生 `fetch` 和 `ReadableStream` 手写了一个 SSE（Server-Sent Events）解析器**。
- 按照后端定义的协议/事件（`session_id`、`thinking_stream`、`content_stream` 等），利用 `TextDecoder` 把一个个数据块解码成 JSON 对象

状态管理

* 为了处理复杂的流式状态，引入了 Zustand 做状态管理。当接收到后端的 `thinking_stream` 事件时，它会实时更新当前 Agent 的思考进度；当接收到 `content_stream` 事件时，它会把增量文本（delta）拼接到消息内容上。
* 由于后端采用了**多 Agent 并行**，前端特别处理了**思考块（Thinking Block）的去重和更新**逻辑。同一个 Agent 的连续输出会被更新到同一个块里，不同 Agent 的输出会独立展示，最终拼装成一条完整的心路历程

交互细节

1. **“思考过程可折叠”**：考虑到有些用户不想看长篇大论的思考过程，前端提供了 `showThoughts` 开关，随时可以收起或展开思考链。
2. **“滚动锁定”**：在流式输出时，文字是不断增加的。我们做了一个聪明的自动滚动逻辑——如果用户往上翻看历史，自动滚动就会暂停；如果用户在最底部，它才会自动跟随最新文字。
3. **“打字机光标”**：在生成正文和思考过程时，都会有一个闪烁的光标（`cursor-blink`），告诉用户“系统还在思考，请不要走开”。