/**
 * 聊天界面主组件 - 车站终端风格
 */
import React from 'react';
import { MessageList } from './MessageList';
import { InputBox } from './InputBox';
import { useChatStore } from '../store/chatStore';

export const ChatInterface: React.FC = () => {
  const {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
    showThoughts,
    toggleShowThoughts,
    defaultExpandedThinking,
    toggleDefaultExpandedThinking,
    toggleTheme,
    theme,
  } = useChatStore();

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg-primary)' }}>
      {/* 顶部导航栏 - 车站信息板风格 */}
      <header className="nav-header">
        <div className="flex justify-between items-center max-w-4xl mx-auto">
          {/* 品牌 */}
          <div className="nav-brand">
            <span className="brand-logo">🚄</span>
            <h1 className="brand-name">智慧出行</h1>
            <div
              className="hidden sm:flex items-center gap-2 px-3 py-1 ml-2 rounded"
              style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)' }}
            >
              <span className="status-dot active"></span>
              <span className="font-mono text-xs" style={{ color: 'var(--fg-muted)' }}>在线</span>
            </div>
          </div>

          {/* 控制按钮 */}
          <div className="nav-controls">
            {/* 主题切换按钮 */}
            <button
              onClick={toggleTheme}
              className="control-btn"
              title={theme === 'dark' ? '切换明亮模式' : '切换深色模式'}
            >
              <span>{theme === 'dark' ? '☀' : '🌙'}</span>
            </button>
            <button
              onClick={toggleShowThoughts}
              className={`control-btn ${showThoughts ? 'active' : ''}`}
              title={showThoughts ? '隐藏思考' : '显示思考'}
            >
              <span style={{ color: showThoughts ? 'var(--status-accent)' : '' }}>
                {showThoughts ? '[显示]' : '[隐藏]'}
              </span>
              <span className="ml-1">思考</span>
            </button>
            <button
              onClick={toggleDefaultExpandedThinking}
              className={`control-btn ${defaultExpandedThinking ? 'active' : ''}`}
              title={defaultExpandedThinking ? '默认收起' : '默认展开'}
            >
              <span style={{ color: defaultExpandedThinking ? 'var(--status-accent)' : '' }}>
                {defaultExpandedThinking ? '[展开]' : '[收起]'}
              </span>
              <span className="ml-1">默认</span>
            </button>
            {messages.length > 0 && (
              <button
                onClick={clearMessages}
                className="control-btn"
                style={{ borderColor: 'var(--status-error)' }}
                title="清空对话"
              >
                <span className="ml-1">清空</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* 错误提示 - 系统警报风格 */}
      {error && (
        <div
          className="border-l-4 px-4 py-3 text-sm mx-auto max-w-4xl mt-4"
          style={{
            background: 'var(--bg-tertiary)',
            borderColor: 'var(--status-error)',
            color: 'var(--status-error)'
          }}
        >
          <span className="font-mono">⚠ 错误:</span> {error}
        </div>
      )}

      {/* 消息区域 */}
      <div className="flex-1 overflow-hidden">
        <div className="max-w-4xl mx-auto h-full flex flex-col">
          <MessageList
            messages={messages}
            isLoading={isLoading}
            showThoughts={showThoughts}
            defaultExpandedThinking={defaultExpandedThinking}
            onExampleClick={sendMessage}
          />
          <InputBox onSend={sendMessage} isLoading={isLoading} />
        </div>
      </div>
    </div>
  );
};