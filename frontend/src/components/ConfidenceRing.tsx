import React from 'react';

interface ConfidenceRingProps {
  confidence: string;
  size?: number;
}

/** SVG progress ring indicating confidence level. */
const ConfidenceRing: React.FC<ConfidenceRingProps> = ({ confidence, size = 24 }) => {
  const percent = confidence === 'high' ? 90 : confidence === 'medium' ? 60 : 30;
  const color = confidence === 'high' ? '#22C55E' : confidence === 'medium' ? '#EAB308' : '#EF4444';
  const radius = (size - 4) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - percent / 100);

  return (
    <div className="relative inline-flex items-center gap-1.5" title={`${confidence} confidence (${percent}%)`}>
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Track */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="#2a2f3d" strokeWidth="2.5"
        />
        {/* Progress */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth="2.5"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          className="transition-all duration-700"
        />
        {/* Center dot */}
        <circle cx={size / 2} cy={size / 2} r={2.5} fill={color} className="origin-center rotate-90" />
      </svg>
      <span className="text-xs font-mono" style={{ color }}>
        {confidence}
      </span>
    </div>
  );
};

export default ConfidenceRing;
