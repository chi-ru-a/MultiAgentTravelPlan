/**
 * API客户端 - 支持Claude风格思考过程
 */
import axios from 'axios';
import { ChatRequest, ChatResponse, ThoughtStep } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    console.log(`[API Response] ${response.config.url}`, response.data);
    return response;
  },
  (error) => {
    console.error('[API Response Error]', error);
    return Promise.reject(error);
  }
);

export interface StreamEvent {
  type: 'session_id' | 'thinking_start' | 'thinking' | 'thinking_stream' | 'thinking_end' | 'response_start' | 'content' | 'content_stream' | 'response_end' | 'error';
  session_id?: string;
  thought?: ThoughtStep;
  block?: any;                  // thinking_stream 时包含
  blocks?: any[];               // 一组思考块
  content?: string;
  delta?: string;               // content_stream 时的增量文本（新格式）
  chunk?: string;               // content_stream 时的单个 token（旧格式）
  accumulated?: string;         // content_stream 时累积的内容
  agent?: string;               // 产出内容的 Agent 名称
  agent_display?: string;       // Agent 显示名称
  thoughts?: ThoughtStep[];
  needs_input?: boolean;
  error?: string;
}

export interface StreamCallbacks {
  onSessionId?: (sessionId: string) => void;
  onThinkingStart?: () => void;
  onThinking?: (thought: ThoughtStep) => void;
  onThinkingStream?: (block: any) => void;
  onThinkingEnd?: () => void;
  onResponseStart?: () => void;
  onContent?: (content: string) => void;
  onResponseEnd?: (data: { content: string; thoughts: ThoughtStep[]; needs_input: boolean }) => void;
  onError?: (error: string) => void;
}

export const chatApi = {
  sendMessage: async (request: ChatRequest): Promise<ChatResponse> => {
    const response = await apiClient.post<ChatResponse>('/chat', request);
    return response.data;
  },

  sendMessageStream: async (request: ChatRequest, callbacks: StreamCallbacks): Promise<void> => {
    try {
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
      }

      const reader = response.body?.getReader();

      if (!reader) {
        callbacks.onError?.('无法读取响应流');
        return;
      }

      await parseSSEReader(reader, callbacks);
    } catch (error) {
      callbacks.onError?.(error instanceof Error ? error.message : '请求失败');
    }
  },

  deleteSession: async (sessionId: string): Promise<void> => {
    await apiClient.delete(`/session/${sessionId}`);
  },

  healthCheck: async (): Promise<boolean> => {
    try {
      await apiClient.get('/health');
      return true;
    } catch {
      return false;
    }
  },
};

/**
 * 解析 SSE 事件流（Claude风格思考过程）
 */
 async function parseSSEReader(reader: ReadableStreamDefaultReader<Uint8Array>, callbacks: StreamCallbacks): Promise<void> {
  return new Promise((resolve, reject) => {
    const decoder = new TextDecoder();
    let buffer = '';
    let allThinkingBlocks: Map<string, any> = new Map();
    let currentContent = '';
    let accumulated_content = '';
    let eventCount = 0;
    let nextBlockId = 1; // 计数器，为每个思考块生成唯一 ID

    console.log('[SSE] 开始解析 SSE 事件流');

    async function read() {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            console.log(`[SSE] 流读取完成，共处理 ${eventCount} 个事件`);
            break;
          }

          buffer += decoder.decode(value, { stream: true });

          // 按双换行符分隔事件
          const events = buffer.split('\n\n');
          buffer = events.pop() || '';

          for (const eventStr of events) {
            if (!eventStr.trim()) continue;

            const lines = eventStr.split('\n');
            let dataLine = '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                dataLine = line.slice(6);
              }
            }

            if (!dataLine.trim()) continue;

            eventCount++;

            try {
              const event: StreamEvent = JSON.parse(dataLine);
              console.log(`[SSE] 事件 ${eventCount}:`, event.type, event);

              switch (event.type) {
                case 'session_id':
                  callbacks.onSessionId?.(event.session_id!);
                  break;

                case 'thinking_start':
                  console.log('[SSE] 思考开始');
                  callbacks.onThinkingStart?.();
                  allThinkingBlocks.clear();
                  break;

                case 'thinking':
                  // 兼容 block 和 thought 两种格式
                  const thinkingBlock = event.block || event.thought;
                  if (thinkingBlock) {
                    console.log('[SSE] 收到 thinking 事件:', thinkingBlock);
                    const blockId = thinkingBlock.id || thinkingBlock.agent || 'unknown';
                    const thought: any = {
                      content: thinkingBlock.content || '',
                      agent: thinkingBlock.agent || 'Agent',
                      duration: thinkingBlock.duration || 0,
                      is_streaming: thinkingBlock.is_streaming || false,
                      sub_thoughts: []
                    };
                    allThinkingBlocks.set(blockId, thought);
                    callbacks.onThinking?.(thought);
                  }
                  break;

                case 'thinking_stream':
                  console.log('[SSE] 收到 thinking_stream 事件，block:', event.block, 'blocks 数量:', event.blocks?.length || 0);
                  if (event.block) {
                    const block = event.block;
                    // 使用计数器生成唯一 blockId（后端不再提供 block.id）
                    const blockId = block.id || `block_${nextBlockId++}`;

                    // 更新或添加思考块
                    allThinkingBlocks.set(blockId, block);

                    // 转换为 ThoughtStep 格式并实时回调
                    const thought: any = {
                      content: block.content || '',
                      agent: block.agent || 'Agent',
                      agent_display: block.agent_display || '',
                      duration: 0,
                      is_streaming: block.is_streaming || false,
                      sub_thoughts: []
                    };
                    callbacks.onThinking?.(thought);
                  } else if (event.blocks) {
                    console.log('[SSE] 收到 thinking_stream blocks 事件，数量:', event.blocks.length);
                    event.blocks.forEach((block, i) => {
                      const blockId = block.id || `block_${i}`;
                      const thought: any = {
                        content: block.content || '',
                        agent: block.agent || 'Agent',
                        duration: block.duration || 0,
                        is_streaming: block.is_streaming || false,
                        sub_thoughts: []
                      };
                      allThinkingBlocks.set(blockId, thought);
                      callbacks.onThinking?.(thought);
                    });
                  }
                  break;

                case 'thinking_end':
                  console.log('[SSE] 思考结束，思考块数量:', allThinkingBlocks.size);
                  callbacks.onThinkingEnd?.();
                  break;

                case 'response_start':
                  callbacks.onResponseStart?.();
                  currentContent = '';
                  break;

                case 'content':
                  // 后端已经发送累积的完整内容，直接使用
                  currentContent = event.content || '';
                  callbacks.onContent?.(currentContent);
                  break;

                case 'content_stream':
                  // 流式输出：支持 delta + accumulated（新格式）和 chunk（旧格式）
                  const delta = (event as any).delta || event.chunk || '';
                  accumulated_content = event.accumulated || (accumulated_content + delta);
                  callbacks.onContent?.(accumulated_content);
                  break;

                case 'response_end':
                  console.log('[SSE] 回复结束，思考数量:', allThinkingBlocks.size);
                  console.log('[SSE] 后端发送的 thoughts 数组:', event.thoughts?.length || 0);
                  if (event.thoughts && event.thoughts.length > 0) {
                    console.log('[SSE] 后端 thoughts 内容:', event.thoughts);
                  }
                  // 使用 allThinkingBlocks 而不是 event.thoughts，因为后端现在发送的是空数组
                  callbacks.onResponseEnd?.({
                    content: event.content || currentContent,
                    thoughts: Array.from(allThinkingBlocks.values()),
                    needs_input: event.needs_input || false,
                  });
                  break;

                case 'error':
                  callbacks.onError?.(event.error || '未知错误');
                  break;
              }
            } catch (e) {
              console.error('[SSE] 解析事件失败:', e, '原始数据:', dataLine);
            }
          }
        }

        // 处理缓冲区剩余内容
        if (buffer.trim()) {
          const lines = buffer.split('\n');
          let dataLine = '';
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              dataLine = line.slice(6);
            }
          }
          if (dataLine.trim()) {
            try {
              const event: StreamEvent = JSON.parse(dataLine);
              if (event.type === 'error') {
                callbacks.onError?.(event.error || '未知错误');
              }
            } catch (e) {
              console.error('[SSE] 解析缓冲区事件失败:', e);
            }
          }
        }

        resolve();
      } catch (error) {
        console.error('[SSE] 读取流失败:', error);
        reject(error);
      }
    }

    read();
  });
}