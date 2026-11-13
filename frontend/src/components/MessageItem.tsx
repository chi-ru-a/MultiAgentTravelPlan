/**
 * 消息气泡组件 - 出行信息卡风格
 */
import React from 'react';
import { ThinkingChain } from './ThinkingChain';

interface MessageItemProps {
  message: any;
  showThoughts?: boolean;
  defaultExpandedThinking?: boolean;
  isStreaming?: boolean;
}

// 生成哈希ID
function hashString(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(36);
}

// 缓存的 Agent 名称映射
const AGENT_NAMES: Record<string, string> = {
  ticket: '智慧出行',
  weather: '天气查询',
  consultation: '知识库',
  chitchat: '闲聊',
  supervisor: '任务规划',
  Synthesizer: '结果汇总',
};

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  showThoughts,
  defaultExpandedThinking = false,
  isStreaming = false,
}) => {
  const isUser = message.role === 'user';
  const hasThoughts = !isUser && showThoughts && message.thoughts && message.thoughts.length > 0;

  // 格式化时间戳
  const formatTimestamp = (timestamp: Date) => {
    const date = new Date(timestamp);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');
    const ms = date.getMilliseconds().toString().padStart(3, '0').slice(0, 2);
    return `${hours}:${minutes}:${seconds}.${ms}`;
  };

  return (
    <div className={`w-full ${isUser ? 'flex justify-end' : 'flex justify-start'}`}>
      <div className={`w-full ${isUser ? 'max-w-[85%]' : 'max-w-[95%]'} space-y-3`}>
        {/* 思考过程 - 终端面板 */}
        {(hasThoughts || (!message.content && isStreaming && !isUser)) && (
          <div className={`${isUser ? 'flex justify-end' : ''}`}>
            <div className={`${isUser ? 'w-full max-w-[500px]' : 'w-full'}`}>
              {/* 只有真正有思考内容时才显示 ThinkingChain */}
              {hasThoughts ? (
                <ThinkingChain
                  blocks={message.thoughts!.map((t: any, index: number) => ({
                    id: `${message.id}_${index}_${hashString(t.agent || '')}`,
                    content: t.content,
                    agent: t.agent,
                    agent_display: AGENT_NAMES[t.agent] || t.agent,
                    isStreaming: t.is_streaming,
                    duration: t.duration,
                  }))}
                  isStreaming={isStreaming}
                  defaultExpanded={defaultExpandedThinking}
                />
              ) : !message.content && isStreaming && !isUser ? (
                /* 处理中进度条 - 集成在思考框位置 */
                <div className="terminal-panel">
                  <button className="terminal-header w-full text-left cursor-pointer">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs ml-2" style={{ color: 'var(--fg-muted)' }}>
                        思考内容
                      </span>
                      <span
                        className="font-mono text-xs px-2 py-0.5 rounded ml-2"
                        style={{
                          background: 'var(--bg-tertiary)',
                          color: 'var(--fg-muted)',
                        }}
                      >
                        [0]
                      </span>
                      <div className="flex items-center gap-1">
                        <span className="status-dot processing"></span>
                        <span className="font-mono text-xs" style={{ color: 'var(--fg-muted)' }}>
                          运行中
                        </span>
                      </div>
                    </div>
                  </button>
                  <div className="terminal-body">
                    <div className="terminal-line">
                      <span className="terminal-prefix font-mono" style={{ color: 'var(--fg-muted)' }}>
                        00:000
                      </span>
                      <span
                        className="font-mono text-xs px-1.5 py-0.5 rounded mr-2"
                        style={{
                          background: 'var(--bg-tertiary)',
                          color: 'var(--fg-muted)',
                          minWidth: '36px',
                          textAlign: 'center',
                        }}
                      >
                        规划
                      </span>
                      <span
                        className="font-mono text-xs px-1.5 py-0.5 rounded mr-2"
                        style={{
                          background: 'rgba(0, 255, 157, 0.1)',
                          color: '#00ff9d',
                          minWidth: '48px',
                          textAlign: 'center',
                        }}
                      >
                        系统
                      </span>
                      <span className="terminal-content font-mono">
                        正在处理您的请求...
                      </span>
                    </div>
                    <div className="terminal-line">
                      <span className="terminal-prefix" />
                      <span className="font-mono" style={{ color: 'var(--fg-muted)' }}>
                        <span className="inline-flex items-center gap-1">
                          <span className="animate-pulse">▌</span>
                          处理中...
                        </span>
                      </span>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        )}

        {/* 消息内容 - 信息卡风格 */}
        {message.content && (
          <div
            className={`message-card ${message.role} ${isUser ? 'ml-8' : ''}`}
            style={{
              background: isUser ? 'rgba(255, 107, 53, 0.1)' : 'var(--bg-secondary)',
            }}
          >
            {/* 元信息栏 */}
            <div className="flex items-center justify-between mb-3 pb-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs px-2 py-0.5 rounded" style={{
                  background: isUser ? 'rgba(255, 107, 53, 0.2)' : 'rgba(57, 211, 83, 0.1)',
                  color: isUser ? 'var(--status-orange)' : 'var(--status-accent)',
                }}>
                  {isUser ? '用户' : '回复'}
                </span>
                <span className="font-mono text-xs" style={{ color: 'var(--fg-muted)' }}>
                  ↱ {formatTimestamp(message.timestamp)}
                </span>
              </div>
              {isStreaming && !isUser && (
                <div className="flex items-center gap-2">
                  <span className="status-dot active" style={{ width: '4px', height: '4px' }}></span>
                  <span className="font-mono text-xs" style={{ color: 'var(--fg-muted)' }}>
                    输出中
                  </span>
                </div>
              )}
            </div>

            {/* 内容区域 */}
            <div
              className={`text-sm whitespace-pre-wrap break-words leading-relaxed ${
                isStreaming && !isUser ? 'cursor-blink' : ''
              }`}
              style={{ color: isUser ? 'var(--fg-primary)' : 'var(--fg-secondary)' }}
            >
              {message.content}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};