/**
 * 聊天状态管理 - Zustand Store (支持流式和思考链)
 */
import { create } from 'zustand';
import { Message, ChatState, ThoughtStep } from '../types';
import { chatApi } from '../api/chat';

interface ChatStore extends ChatState {
  addMessage: (message: Message) => void;
  updateMessageContent: (messageId: string, newContent: string, newThoughts?: ThoughtStep[]) => void;
  appendMessageThought: (messageId: string, thought: ThoughtStep) => void;
  sendMessage: (content: string) => Promise<void>;
  sendMessageStream: (content: string) => void;
  clearMessages: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  toggleShowThoughts: () => void;
  updateOrAppendThought: (messageId: string, thought: ThoughtStep) => void;
  toggleDefaultExpandedThinking: () => void;
  toggleTheme: () => void;
}

// 初始化主题
const savedTheme = (localStorage.getItem('theme') as 'dark' | 'light') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  sessionId: null,
  isLoading: false,
  error: null,
  showThoughts: true,
  defaultExpandedThinking: true,
  needsUserInput: false,
  theme: savedTheme,

  addMessage: (message) => {
    set((state) => ({
      messages: [...state.messages, message],
    }));
  },

  updateMessageContent: (messageId: string, newContent: string, newThoughts?: ThoughtStep[]) => {
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === messageId
          ? {
              ...msg,
              content: newContent,
              ...(newThoughts !== undefined && { thoughts: newThoughts })
            }
          : msg
      ),
    }));
  },

  updateOrAppendThought: (messageId: string, thought: ThoughtStep) => {
    set((state) => ({
      messages: state.messages.map((msg) => {
        if (msg.id !== messageId) return msg;

        const existingThoughts = msg.thoughts || [];
        // 根据 agent 和 content 前缀匹配来更新现有思考
        const existingIndex = existingThoughts.findIndex(
          t => t.agent === thought.agent &&
              t.content.length > 10 &&
              t.content.substring(0, 10) === thought.content.substring(0, 10)
        );

        if (existingIndex >= 0) {
          // 更新现有思考
          const updatedThoughts = [...existingThoughts];
          updatedThoughts[existingIndex] = thought;
          return { ...msg, thoughts: updatedThoughts };
        } else {
          // 添加新思考（如果是新 agent 或完全不同的内容）
          return { ...msg, thoughts: [...existingThoughts, thought] };
        }
      }),
    }));
  },

  appendMessageThought: (messageId: string, thought: ThoughtStep) => {
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === messageId
          ? { ...msg, thoughts: [...(msg.thoughts || []), thought] }
          : msg
      ),
    }));
  },

  sendMessage: async (content: string) => {
    const state = get();

    // 添加用户消息
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    };
    state.addMessage(userMessage);

    // 设置加载状态
    set({ isLoading: true, error: null, needsUserInput: false });

    // 创建助手消息占位符
    const assistantMessageId = (Date.now() + 1).toString();
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      thoughts: [],
    };
    state.addMessage(assistantMessage);

    try {
      // 获取当前的 showThoughts 状态，用于之后回调中使用
      const shouldShowThoughts = state.showThoughts;
      console.log('[Store] sendMessage 被调用，state.showThoughts:', state.showThoughts, 'shouldShowThoughts:', shouldShowThoughts);

      // 始终请求后端发送思考内容，这样用户之后可随时开启查看
      await chatApi.sendMessageStream(
        {
          message: content,
          session_id: state.sessionId || undefined,
          show_thought: true,  // 始终请求思考内容，由前端决定是否显示
        },
        {
          onSessionId: (sessionId) => {
            set({ sessionId });
          },
          onThinkingStart: () => {
            // 思考开始 - 始终初始化空的 thoughts 数组
            console.log('[Store] onThinkingStart 触发');
            set((s) => ({
              messages: s.messages.map((msg) =>
                msg.id === assistantMessageId ? { ...msg, thoughts: [] } : msg
              ),
            }));
          },
          onThinking: (thought) => {
            // 实时更新或添加思考步骤 - 始终接收，保存到 store，展示时再根据 showThoughts 决定是否显示
            console.log('[Store] onThinking 触发，shouldShowThoughts:', shouldShowThoughts, 'thought:', thought);

            // 始终更新思考内容，不受 shouldShowThoughts 限制
            const currentState = get();
            const targetMsg = currentState.messages.find(m => m.id === assistantMessageId);
            if (!targetMsg) {
              console.log('[Store] 未找到目标消息:', assistantMessageId, '当前消息:', currentState.messages.map(m => m.id));
              return;
            }

            const existingThoughts = targetMsg.thoughts || [];
            // 使用 agent + content 的前缀来判断是否是同一个思考更新

            const existingIndex = existingThoughts.findIndex(
              t => t.agent === thought.agent &&
                  t.content.length > 10 &&
                  thought.content.length > 10 &&
                  t.content.substring(0, 15) === thought.content.substring(0, 15)
            );

            let updatedThoughts;
            if (existingIndex >= 0) {
              // 更新现有思考
              updatedThoughts = [...existingThoughts];
              updatedThoughts[existingIndex] = thought;
              console.log('[Store] 更新现有思考:', existingIndex, thought);
            } else {
              // 添加新思考（从一开始或内容完全不同）
              updatedThoughts = [...existingThoughts, thought];
              console.log('[Store] 添加新思考，总共:', updatedThoughts.length);
            }

            set((s) => ({
              messages: s.messages.map((msg) =>
                msg.id === assistantMessageId ? { ...msg, thoughts: updatedThoughts } : msg
              ),
            }));
          },
          onThinkingEnd: () => {
            // 思考结束 - 始终将所有思考标记为非流式
            console.log('[Store] onThinkingEnd 触发');
            set((s) => ({
              messages: s.messages.map((msg) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      thoughts: (msg.thoughts || []).map(t => ({ ...t, is_streaming: false })),
                    }
                  : msg
              ),
            }));
          },
          onResponseStart: () => {
            // 回复开始
          },
          onContent: (content) => {
            // 实时更新消息内容（流式），保留 thoughts
            set((s) => ({
              messages: s.messages.map((msg) =>
                msg.id === assistantMessageId ? { ...msg, content, thoughts: msg.thoughts } : msg
              ),
            }));
          },
          onResponseEnd: (data) => {
            // 回复结束 - 确保所有思考标记为非流式
            console.log('[Store] onResponseEnd 收到 thoughts 数量:', (data.thoughts || []).length);
            console.log('[Store] onResponseEnd 收到 thoughts:', data.thoughts);

            const finalThoughts = (data.thoughts || []).map(t => ({ ...t, is_streaming: false }));
            console.log('[Store] 处理后的 finalThoughts 数量:', finalThoughts.length);
            console.log('[Store] 处理后的 finalThoughts:', finalThoughts);

            set((s) => ({
              messages: s.messages.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, content: data.content, thoughts: finalThoughts }
                  : msg
              ),
              needsUserInput: data.needs_input,
            }));

            // 打印更新后的 messages 状态
            const currentState = get();
            const updatedMsg = currentState.messages.find(m => m.id === assistantMessageId);
            if (updatedMsg) {
              console.log('[Store] 更新后的消息 thoughts 数量:', (updatedMsg.thoughts || []).length);
              console.log('[Store] 更新后的消息 thoughts:', updatedMsg.thoughts);
            }
          },
          onError: (error) => {
            console.error('流式请求错误:', error);
            set({ error });
            set((s) => ({
              messages: s.messages.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, content: `抱歉，${error}` }
                  : msg
              ),
            }));
          },
        }
      );
    } catch (error: any) {
      const errorMessage = error.message || '发送消息失败，请重试';
      set({ error: errorMessage });
      set((s) => ({
        messages: s.messages.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, content: `抱歉，${errorMessage}` }
            : msg
        ),
      }));
    } finally {
      set({ isLoading: false });
    }
  },

  sendMessageStream: (content: string) => {
    // 使用 sendMessage 作为流式发送的实现
    get().sendMessage(content);
  },

  clearMessages: () => {
    const state = get();
    if (state.sessionId) {
      chatApi.deleteSession(state.sessionId).catch(console.error);
    }
    set({
      messages: [],
      sessionId: null,
      error: null,
      needsUserInput: false,
    });
  },

  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  toggleShowThoughts: () => set((state) => ({ showThoughts: !state.showThoughts })),
  toggleDefaultExpandedThinking: () => set((state) => ({ defaultExpandedThinking: !state.defaultExpandedThinking })),
  toggleTheme: () => {
    const state = get();
    const newTheme = state.theme === 'dark' ? 'light' : 'dark';
    set({ theme: newTheme });
    // 切换 DOM 的 data-theme 属性
    document.documentElement.setAttribute('data-theme', newTheme);
    // 保存到本地存储
    localStorage.setItem('theme', newTheme);
  },
}));

// 空函数，避免未导入类型导致的警告
export const _unused: any = null;