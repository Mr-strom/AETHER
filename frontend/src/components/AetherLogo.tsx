import React from 'react';

interface AetherLogoProps {
  size?: number;
  className?: string;
}

/** Circular "A" icon — Linkin Park-style stylized A inside a circle */
export const AetherIcon: React.FC<AetherLogoProps> = ({ size = 32, className = '' }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 100 100"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
  >
    {/* Outer circle */}
    <circle cx="50" cy="50" r="46" stroke="white" strokeWidth="3.5" fill="none" />
    {/* Stylized A — triangle with crossbar */}
    <path
      d="M50 18 L28 76 L36 76 L41 62 L59 62 L64 76 L72 76 L50 18Z M44 54 L50 36 L56 54 L44 54Z"
      fill="white"
    />
    {/* Inner chevron accent */}
    <path
      d="M38 72 L50 28 L62 72"
      stroke="white"
      strokeWidth="2"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      opacity="0.3"
    />
  </svg>
);

/** "AETHER" wordmark in spaced letters */
export const AetherWordmark: React.FC<{ className?: string; large?: boolean }> = ({
  className = '',
  large = false,
}) => (
  <span
    className={`font-headline font-semibold tracking-[0.35em] ${
      large ? 'text-4xl md:text-5xl' : 'text-lg'
    } text-gray-200 select-none ${className}`}
  >
    AETHER
  </span>
);

/** Combined icon + wordmark for top bar */
export const AetherBrand: React.FC<{ iconSize?: number; className?: string }> = ({
  iconSize = 28,
  className = '',
}) => (
  <div className={`flex items-center gap-2.5 ${className}`}>
    <AetherIcon size={iconSize} />
    <AetherWordmark />
  </div>
);
