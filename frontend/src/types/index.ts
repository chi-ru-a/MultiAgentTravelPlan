/**
 * 类型定义（Claude/DeepSeek风格思考过程）
 */
export interface ThoughtStep {
  content: string;                    // 思考内容
  agent: string;                      // 执行的Agent名称
  duration: number;                   // 耗时（秒）
  is_streaming: boolean;             // 是否正在流式输出
  sub_thoughts?: ThoughtStep[];      // 子思考（可选）
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  thoughts?: ThoughtStep[];         // 思考链
}

export interface ChatState {
  messages: Message[];
  sessionId: string | null;
  isLoading: boolean;
  error: string | null;
  showThoughts: boolean;              // 是否展示思考过程
  defaultExpandedThinking: boolean;   // 思考过程默认展开/收起
  needsUserInput?: boolean;          // 是否需要用户输入
  theme: 'dark' | 'light';             // 主题模式
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  show_thought?: boolean;              // 是否请求展示思考过程
}

export interface ChatResponse {
  response: string;
  session_id: string;
  needs_input: boolean;
  thoughts?: ThoughtStep[];
  metadata?: Record<string, any>;
}