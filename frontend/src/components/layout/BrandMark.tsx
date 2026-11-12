import React from 'react';

export const BrandMark: React.FC<{ className?: string }> = ({ className = 'h-8 w-8' }) => (
  <svg
    viewBox="0 0 32 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-hidden="true"
  >
    <rect width="32" height="32" rx="7" fill="#1E293B" fillOpacity="0.45" />
    <circle cx="16" cy="16" r="8.5" stroke="#6366F1" strokeWidth="2.2" />
    <circle cx="16" cy="16" r="3.5" fill="#14B8A6" />
    <path
      d="M16 4V8M16 24V28M4 16H8M24 16H28"
      stroke="#94A3B8"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
  </svg>
);

