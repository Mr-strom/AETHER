import React from 'react';
import { Sparkles } from 'lucide-react';

interface ThinkingStep {
  step: string;
  message: string;
  completed: boolean;
}

interface ThinkingBubbleProps {
  steps: ThinkingStep[];
  currentStep: string | null;
}

const STEP_ICONS: Record<string, string> = {
  planning: '🔍',
  retrieving: '📚',
  crag: '🔄',
  conflicts: '⚠️',
  synthesizing: '✍️',
  validating: '✅',
};

const ThinkingBubble: React.FC<ThinkingBubbleProps> = ({ steps, currentStep }) => {
  if (steps.length === 0) return null;

  return (
    <div className="animate-fade-in space-y-2">
      <div className="flex items-center gap-2">
        <Sparkles size={16} className="text-primary animate-pulse-subtle" />
        <span className="text-sm font-headline font-semibold text-gray-300">
          Aether
        </span>
      </div>
      <div className="pl-6">
        <div className="bg-aether-card border-l-2 border-primary rounded-lg rounded-tl-none px-4 py-3 max-w-[480px]">
          <div className="space-y-1.5">
            {steps.map((s, i) => {
              const icon = STEP_ICONS[s.step] || '•';
              const isActive = s.step === currentStep && !s.completed;

              return (
                <div
                  key={i}
                  className={`flex items-center gap-2 text-xs font-mono transition-all duration-300 animate-slide-right ${
                    s.completed
                      ? 'text-gray-500'
                      : isActive
                      ? 'text-gray-200'
                      : 'text-gray-400'
                  }`}
                  style={{ animationDelay: `${i * 50}ms` }}
                >
                  {s.completed ? (
                    <span className="text-accent-green text-xs w-4 text-center">✓</span>
                  ) : isActive ? (
                    <span className="w-4 text-center">{icon}</span>
                  ) : (
                    <span className="w-4 text-center text-neutral">○</span>
                  )}
                  <span className={isActive ? 'font-medium' : ''}>
                    {s.message}
                  </span>
                  {isActive && (
                    <span className="flex gap-0.5 ml-1">
                      <span className="w-1 h-1 bg-primary rounded-full animate-typing" style={{ animationDelay: '0ms' }} />
                      <span className="w-1 h-1 bg-primary rounded-full animate-typing" style={{ animationDelay: '200ms' }} />
                      <span className="w-1 h-1 bg-primary rounded-full animate-typing" style={{ animationDelay: '400ms' }} />
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export type { ThinkingStep };
export default ThinkingBubble;
