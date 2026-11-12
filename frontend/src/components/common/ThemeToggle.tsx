import React from 'react';
import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

interface ThemeToggleProps {
  compact?: boolean;
  className?: string;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({
  compact = false,
  className = '',
}) => {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      className={`inline-flex items-center justify-center gap-2 rounded-md border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
        compact
          ? 'h-9 w-9 border-app-border-strong bg-app-surface text-app-text hover:bg-app-muted'
          : 'w-full px-3 py-2 text-xs font-medium'
      } ${className}`}
    >
      {isDark ? <Sun className="h-4 w-4 shrink-0 text-amber-400" /> : <Moon className="h-4 w-4 shrink-0" />}
      {!compact && <span>{isDark ? 'Light Mode' : 'Dark Mode'}</span>}
    </button>
  );
};

