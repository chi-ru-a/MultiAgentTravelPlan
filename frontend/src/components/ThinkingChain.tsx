/**
 * 思考过程组件 - 终端日志风格
 */
import React, { useState, useMemo, useRef, useEffect } from 'react';

interface ThinkingBlock {
  id: string;
  content: string;
  agent?: string;
  agent_display?: string;
  isStreaming: boolean;
  duration?: number;
}

interface ThinkingChainProps {
  blocks: ThinkingBlock[];
  isStreaming: boolean;
  defaultExpanded?: boolean;
}

// Agent 状态色映射
const AGENT_COLORS: Record<string, string> = {
  ticket: '#ff6b35',
  weather: '#3b82f6',
  consultation: '#a855f7',
  chitchat: '#6b7280',
  supervisor: '#00ff9d',
  Synthesizer: '#f59e0b',
};

// 提取纯文本
function extractText(content: string): string {
  return content
    .replace(/^[📋💭⚡👁️🎯✓✗🔍💬🌐]+(\s+[计划思考执行观察决策]+[:：]\s*)?/, '')
    .replace(/^[📋💭⚡👁️🎯✓✗🔍💬🌐]+/, '')
    .trim();
}

// 获取操作类型标识
function getOperationType(content: string): string {
  const lower = content.toLowerCase();

  if (lower.includes('分析') || lower.includes('推理') || lower.includes('识别')) return '分析';
  if (lower.includes('搜索') || lower.includes('查询') || lower.includes('联网')) return '搜索';
  if (lower.includes('执行') || lower.includes('处理') || lower.includes('调用')) return '执行';
  if (lower.includes('找到') || lower.includes('成功') || lower.includes('完成')) return '完成';
  if (lower.includes('失败') || lower.includes('错误') || lower.includes('未找到')) return '错误';
  if (lower.includes('规划') || lower.includes('计划')) return '规划';

  return '信息';
}

// 获取 Agent 背景色
function getAgentBgColor(agent: string | undefined): string {
  return (agent && AGENT_COLORS[agent]) || '#6b7280';
}

export const ThinkingChain: React.FC<ThinkingChainProps> = ({
  blocks,
  isStreaming,
  defaultExpanded = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // 处理并去重思考块
  const safeBlocks = useMemo(() => {
    if (!Array.isArray(blocks)) return [];

    const seen = new Set<string>();
    const result = [];

    for (const block of blocks) {
      const text = extractText(block.content);
      const key = `${block.agent || ''}:${text.substring(0, 20)}`;

      if (!seen.has(key)) {
        seen.add(key);
        result.push({
          ...block,
          extractedText: text,
          opType: getOperationType(block.content),
        });
      }
    }

    return result;
  }, [blocks]);

  const stepCount = safeBlocks.length;
  const terminalBodyRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    if (isExpanded && terminalBodyRef.current) {
      terminalBodyRef.current.scrollTop = terminalBodyRef.current.scrollHeight;
    }
  }, [isExpanded, stepCount, isStreaming]);

  if (stepCount === 0 && !isStreaming) {
    return null;
  }

  return (
    <div className="terminal-panel">
      {/* 终端头部 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="terminal-header w-full text-left cursor-pointer hover:opacity-80 transition-opacity"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {/* macOS 风格窗口点 */}
           {/*  <span className="terminal-dot red"></span>
            <span className="terminal-dot yellow"></span>
            <span className="terminal-dot green"></span> */}

            <span className="font-mono text-xs ml-2" style={{ color: 'var(--fg-muted)' }}>
              思考内容
            </span>

            {/* 步数徽章 */}
            <span
              className="font-mono text-xs px-2 py-0.5 rounded ml-2"
              style={{
                background: 'var(--bg-tertiary)',
                color: 'var(--fg-muted)',
              }}
            >
              [{stepCount}]
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* 流式状态指示 */}
            {isStreaming && (
              <div className="flex items-center gap-1">
                <span className="status-dot processing"></span>
                <span className="font-mono text-xs" style={{ color: 'var(--fg-muted)' }}>
                  运行中
                </span>
              </div>
            )}

            {/* 展开/收起箭头 */}
            <svg
              className={`chevron ${isExpanded ? 'expanded' : ''}`}
              style={{ color: 'var(--fg-muted)' }}
              width="14"
              height="14"
              viewBox="0 0 14 14"
              fill="none"
            >
              <path
                d="M2.91663 3.5L6.99996 7.58333L11.0833 3.5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
        </div>
      </button>

      {/* 终端主体 */}
      {isExpanded && (
        <div className="terminal-body" ref={terminalBodyRef}>
          <div className="space-y-1">
            {safeBlocks.map((block, index) => {
              const agentColor = getAgentBgColor(block.agent);
              const agentLabel = block.agent_display || block.agent || '系统';
              const extractedText = (block as any).extractedText || extractText(block.content);
              const opType = (block as any).opType || '信息';

              return (
                <div key={block.id || index} className="terminal-line group">
                  {/* 时间戳 */}
                  <span className="terminal-prefix font-mono" style={{ color: 'var(--fg-muted)' }}>
                    {String(index + 1).padStart(2, '0')}:{String(Date.now() % 1000).padStart(3, '0')}
                  </span>

                  {/* 操作类型 */}
                  <span
                    className="font-mono text-xs px-1.5 py-0.5 rounded mr-1"
                    style={{
                      background: 'var(--bg-tertiary)',
                      color: 'var(--fg-muted)',
                      minWidth: '36px',
                      textAlign: 'center',
                    }}
                  >
                    {opType}
                  </span>

                  {/* Agent 标签 */}
                  <span
                    className="font-mono text-xs px-1.5 py-0.5 rounded mr-2"
                    style={{
                      background: `${agentColor}20`,
                      color: agentColor,
                      minWidth: '65px',
                      textAlign: 'center',
                    }}
                  >
                    {agentLabel}
                  </span>

                  {/* 内容 */}
                  <span className="terminal-content font-mono">
                    {extractedText}
                  </span>

                  {/* 流式光标 */}
                  {block.isStreaming && isStreaming && (
                    <span className="inline-flex ml-1">
                      <span
                        className="inline-block w-1 h-3 bg-green-400 animate-pulse"
                        style={{ background: 'var(--status-accent)' }}
                      />
                    </span>
                  )}
                </div>
              );
            })}

            {/* 流式继续提示 */}
            {isStreaming && stepCount > 0 && (
              <div className="terminal-line">
                <span className="terminal-prefix" />
                {/* 进度条 */}
                <div className="flex items-center gap-2 flex-1">
                  <div className="flex-1 h-2 bg-gray-600/50 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-300 ease-out"
                      style={{
                        width: `${Math.min(stepCount * 15, 100)}%`,
                        background: 'linear-gradient(90deg, #22c55e, #4ade80)',
                        boxShadow: '0 0 4px rgba(34, 197, 94, 0.5)'
                      }}
                    />
                  </div>
                  <span className="text-xs opacity-50 w-8 text-right">{Math.min(stepCount * 15, 100)}%</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};