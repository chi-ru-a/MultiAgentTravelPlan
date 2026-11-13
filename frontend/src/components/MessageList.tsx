/**
 * 消息列表组件 - 车站发车时刻表风格
 */
import React, { useEffect, useRef, useCallback } from 'react';
import { MessageItem } from './MessageItem';

interface MessageListProps {
  messages: any[];
  isLoading: boolean;
  showThoughts: boolean;
  defaultExpandedThinking?: boolean;
  onExampleClick?: (message: string) => void;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  isLoading,
  showThoughts,
  defaultExpandedThinking = false,
  onExampleClick,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const shouldScrollRef = useRef(true);
  const scrollTimeoutRef = useRef<NodeJS.Timeout>();
  const previousMessagesLengthRef = useRef(0);
  const previousLastMessageContentRef = useRef('');

  // 获取最后一条消息的内容，用于检测内容变化
  const getLastMessageContent = useCallback(() => {
    if (messages.length === 0) return '';
    const lastMsg = messages[messages.length - 1];
    return lastMsg.content || '';
  }, [messages]);

  // 使用稳定的滚动控制
  const scrollToBottom = useCallback((force = false) => {
    if (!shouldScrollRef.current && !force) return;

    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }

    scrollTimeoutRef.current = setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, 50);
  }, []);

  // 只在新消息添加时滚动，避免每次内容更新都滚动
  useEffect(() => {
    const currentLength = messages.length;
    const currentLastContent = getLastMessageContent();

    // 新消息添加时滚动
    if (currentLength !== previousMessagesLengthRef.current) {
      scrollToBottom();
      previousMessagesLengthRef.current = currentLength;
      previousLastMessageContentRef.current = currentLastContent;
    }
    // 流式输出时也滚动（最后一条消息内容增长）
    else if (currentLastContent !== previousLastMessageContentRef.current) {
      scrollToBottom();
      previousLastMessageContentRef.current = currentLastContent;
    }
  }, [messages.length, messages, scrollToBottom, getLastMessageContent]);

  // 用户手动滚动时禁用自动滚动
  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    shouldScrollRef.current = isNearBottom;
  }, []);

  // 格式化时间戳
  const formatTime = () => {
    const now = new Date();
    return now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  };

  // 渲染消息卡片
  const renderMessage = (message: any, index: number) => {
    // 使用稳定的 key（只依赖 message.id），避免内容更新时重渲染
    const key = message.id;

    const isLastAssistant = index === messages.length - 1 && message.role === 'assistant';
    // 流式状态：正在加载且是最后一条助手消息
    const isStreaming = isLoading && isLastAssistant;

    return (
      <div
        key={key}
        className={`min-h-[80px] ${
          // 只在刚开始没有内容时显示扫描线效果
          (!message.content && isLastAssistant && isLoading) ? 'scanline-overlay' : ''
        } ${
          message.role === 'user' ? 'anim-slide-in-right' : 'anim-slide-in-left'
        }`}
        style={{ animationPlayState: 'running' }}
      >
        {/* 时间戳分隔线 */}
        {index === 0 || messages[index - 1].role !== message.role ? (
          <div className="flex items-center gap-3 mb-3">
            <div className="progress-bar" style={{ flex: 1, opacity: 0.3 }}>
              <div className="progress-fill" style={{ width: '100%' }}></div>
            </div>
            <div className="font-mono text-xs" style={{ color: 'var(--fg-muted)' }}>
              {formatTime()}
            </div>
            <div className="progress-bar" style={{ flex: 1, opacity: 0.3 }}>
              <div className="progress-fill" style={{ width: '100%' }}></div>
            </div>
          </div>
        ) : null}

        <MessageItem
          message={message}
          showThoughts={showThoughts}
          defaultExpandedThinking={defaultExpandedThinking}
          isStreaming={isStreaming}
        />
      </div>
    );
  };

  return (
    <div
      ref={scrollContainerRef}
      className="flex-1 overflow-y-auto px-4 py-6"
      style={{
        background: 'var(--bg-primary)',
      }}
      onScroll={handleScroll}
    >
      <div className="max-w-3xl mx-auto space-y-6">
        {messages.length === 0 ? (
          /* 空状态 - 欢迎画面 */
          <div className="welcome-container min-h-[400px]">
            <div className="welcome-badge anim-fade-in">
              <span className="badge-icon">🚄</span>
              <div className="text-left">
                <div className="font-display font-semibold text-lg" style={{ color: 'var(--fg-primary)' }}>
                  智慧出行
                </div>
                <div className="font-mono text-xs" style={{ color: 'var(--fg-muted)' }}>
                  STATUS: ACTIVE | DELAY: 0ms
                </div>
              </div>
            </div>

            <div className="anim-fade-in" style={{ animationDelay: '0.1s' }}>
              <div className="flex items-center gap-4 mb-4">
                <div className="progress-bar" style={{ width: '80px' }}>
                  <div className="progress-fill" style={{ width: '100%' }}></div>
                </div>
                <span className="font-mono text-xs" style={{ color: 'var(--fg-muted)' }}>
                  准备就绪
                </span>
              </div>
            </div>

            <p className="welcome-subtitle anim-fade-in" style={{ animationDelay: '0.2s' }}>
              查询班次 · 天气预报 · 业务咨询
            </p>

            <div className="example-chips anim-fade-in" style={{ animationDelay: '0.3s' }}>
              <button
                className="example-chip"
                onClick={() => onExampleClick?.('查明天北京到上海的班次')}
              >
                查明天北京到上海的班次
              </button>
              <button
                className="example-chip"
                onClick={() => onExampleClick?.('儿童票怎么买？有什么优惠？')}
              >
                儿童票怎么买？有什么优惠？
              </button>
              <button
                className="example-chip"
                onClick={() => onExampleClick?.('明天北京天气怎么样')}
              >
                明天北京天气怎么样
              </button>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message, index) => renderMessage(message, index))}
          </>
        )}
      </div>

      <div ref={messagesEndRef} style={{ height: '100px' }} />
    </div>
  );
};