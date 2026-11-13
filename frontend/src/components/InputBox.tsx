/**
 * 输入框组件 - 票务终端风格
 */
import React, { useState, KeyboardEvent, useRef, useEffect } from 'react';

interface InputBoxProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export const InputBox: React.FC<InputBoxProps> = ({ onSend, isLoading }) => {
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // 自动聚焦
  useEffect(() => {
    if (!isLoading) {
      inputRef.current?.focus();
    }
  }, [isLoading]);

  const handleSend = () => {
    if (input.trim() && !isLoading) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !isLoading) {
      e.preventDefault();
      handleSend();
    }
  };

  const isDisabled = !input.trim() || isLoading;

  return (
    <div
      className="border-t"
      style={{
        background: 'var(--bg-secondary)',
        borderColor: 'var(--border-subtle)',
      }}
    >
      <div className="max-w-4xl mx-auto p-4">
        <div className="flex items-center gap-3">
          {/* 状态指示 */}
          <div className="hidden sm:flex items-center gap-2 px-2">
            <span
              className={`status-dot ${isLoading ? 'processing' : 'active'}`}
              style={{ width: '6px', height: '6px' }}
            />
            <span className="font-mono text-xs" style={{ color: 'var(--fg-muted)' }}>
              {isLoading ? '忙碌' : '就绪'}
            </span>
          </div>

          {/* 输入框 */}
          <div className="flex-1 relative">
            {/* <div className="absolute left-4 top-1/2 -translate-y-1/2 font-mono text-xs " style={{ color: 'var(--fg-muted)' }}>
              {'>'}
            </div> */}
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="输入查询内容..."
              className="input-terminal pl-8"
              disabled={isLoading}
              style={{ fontFamily: 'var(--font-mono)' }}
            />
          </div>

          {/* 发送按钮 */}
          <button
            onClick={handleSend}
            disabled={isDisabled}
            className={`btn-primary px-6 py-3 font-mono text-xs ${
              isDisabled ? 'opacity-50 cursor-not-allowed' : ''
            }`}
            style={{
              opacity: isDisabled ? 0.4 : 1,
            }}
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <span className="inline-block w-2 h-2 rounded-full animate-pulse" style={{ background: 'var(--fg-primary)' }}></span>
                发送中
              </span>
            ) : (
              '发送 >'
            )}
          </button>
        </div>

        {/* 底部提示 */}
        <div className="flex justify-between items-center mt-3 pt-2" style={{ borderTop: '1px solid var(--border-subtle)' }}>
          <div className="flex items-center gap-4 font-mono text-xs" style={{ color: 'var(--fg-muted)' }}>
            <span>回车: 发送</span>
          </div>
          <div className="font-mono text-xs" style={{ color: 'var(--fg-muted)' }}>
            v1.0.0 | 状态: 正常
          </div>
        </div>
      </div>
    </div>
  );
};