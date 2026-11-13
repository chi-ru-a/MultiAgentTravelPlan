/**
 * 思考链组件 - 流式展示推理过程
 */
import React, { useState } from 'react';
import { ThoughtStep } from '../types';

interface ThoughtChainProps {
  thoughts: ThoughtStep[];
  isStreaming?: boolean;
}

export const ThoughtChain: React.FC<ThoughtChainProps> = ({ 
  thoughts, 
  isStreaming = false
}) => {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!thoughts || thoughts.length === 0) {
    return null;
  }

  const handleToggle = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <div className="mb-2">
      {/* 收起后的摘要 */}
      {!isExpanded && (
        <button
          onClick={handleToggle}
          className="flex items-center space-x-2 text-xs text-gray-500 hover:text-gray-700 transition-colors group"
        >
          <span className="text-base">🧠</span>
          <span>思考了 {thoughts.length} 步</span>
          <span className="text-gray-400 group-hover:text-gray-600">点击展开</span>
        </button>
      )}

      {/* 展开的思考过程 */}
      {isExpanded && (
        <div className="transition-all duration-300">
          <div className="flex items-center space-x-2 mb-2">
            <span className={`text-base ${isStreaming ? 'animate-pulse' : ''}`}>🧠</span>
            <span className="text-xs font-medium text-gray-600">
              {isStreaming ? '正在思考...' : `推理过程 (${thoughts.length}步)`}
            </span>
            <button
              onClick={handleToggle}
              className="ml-auto text-xs text-gray-400 hover:text-gray-600"
            >
              收起
            </button>
          </div>

          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-3 space-y-1.5 border border-blue-100">
            {thoughts.map((thought, index) => (
              <ThoughtItem
                key={index}
                thought={thought}
                isLast={index === thoughts.length - 1}
                isStreaming={isStreaming && index === thoughts.length - 1}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

interface ThoughtItemProps {
  thought: ThoughtStep;
  isLast: boolean;
  isStreaming: boolean;
}

const ThoughtItem: React.FC<ThoughtItemProps> = ({ thought, isLast, isStreaming }) => {
  const content = thought.content || '';
  
  // 提取emoji和内容
  const emojiMatch = content.match(/^([📋💭⚡👁️🎯])\s*(计划|思考|执行|观察|决策)[:：]\s*(.+)$/);
  const emoji = emojiMatch ? emojiMatch[1] : '💡';
  const label = emojiMatch ? emojiMatch[2] : '';
  const text = emojiMatch ? emojiMatch[3] : content;

  return (
    <div className={`flex items-start space-x-2 text-xs ${isLast && isStreaming ? 'animate-fade-in' : ''}`}>
      <span className="text-sm flex-shrink-0 mt-0.5">{emoji}</span>
      <div className="flex-1 min-w-0">
        {label && (
          <span className="font-medium text-gray-700 mr-1">{label}:</span>
        )}
        <span className="text-gray-600">
          {text}
          {isStreaming && (
            <span className="inline-block ml-1 w-0.5 h-3 bg-blue-500 animate-pulse"></span>
          )}
        </span>
      </div>
      {thought.duration > 0 && (
        <span className="text-gray-400 text-[10px] whitespace-nowrap flex-shrink-0">
          {thought.duration.toFixed(1)}s
        </span>
      )}
    </div>
  );
};
