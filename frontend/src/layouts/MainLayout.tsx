import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Activity,
  ChevronRight,
  FolderKanban,
  GitPullRequest,
  History,
  Info,
  LayoutDashboard,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  X,
} from 'lucide-react';
import { useBackendHealth, useSystemCapabilities } from '../hooks/useSystemStatus';
import { BrandMark } from '../components/layout/BrandMark';
import { ThemeToggle } from '../components/common/ThemeToggle';

interface NavItem {
  to: string;
  label: string;
  icon: React.FC<{ className?: string }>;
  matchPrefix?: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/projects', label: 'Projects', icon: FolderKanban },
  { to: '/change-requests', label: 'Change Requests', icon: GitPullRequest },
  { to: '/impact-analysis', label: 'Impact Analysis', icon: Activity, matchPrefix: '/impact-analysis' },
  { to: '/analysis-history', label: 'Analysis History', icon: History },
  { to: '/about', label: 'About', icon: Info },
];

interface RouteMeta {
  title: string;
  section: string;
}

function getRouteMeta(pathname: string): RouteMeta {
  if (pathname === '/') return { title: 'Dashboard', section: 'Overview' };
  if (pathname.startsWith('/projects')) return { title: 'Projects & QA Assets', section: 'Workspace' };
  if (pathname.startsWith('/change-requests')) return { title: 'Change Requests', section: 'Analysis Input' };
  if (pathname.startsWith('/impact-analysis')) return { title: 'Impact Analysis', section: 'Core Workspace' };
  if (pathname.startsWith('/analysis-history')) return { title: 'Analysis History', section: 'Audit Trail' };
  if (pathname.startsWith('/about')) return { title: 'About TestImpact AI', section: 'Documentation' };
  return { title: 'TestImpact AI', section: 'Platform' };
}

export const MainLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const healthQuery = useBackendHealth();
  const capabilitiesQuery = useSystemCapabilities();

  const routeMeta = getRouteMeta(location.pathname);
  const isBackendOnline = healthQuery.isSuccess && healthQuery.data?.status === 'healthy';
  const capabilities = capabilitiesQuery.data;

  const renderSidebarContent = (isMobile = false) => {
    const collapsed = !isMobile && sidebarCollapsed;
    return (
      <div className="flex h-full flex-col bg-app-sidebar text-slate-100">
        {/* Top Brand */}
        <div className="flex h-16 items-center justify-between border-b border-white/10 px-4">
          <div className={`flex items-center gap-3 overflow-hidden ${collapsed ? 'justify-center w-full' : ''}`}>
            <BrandMark className="h-8 w-8 shrink-0" />
            {!collapsed && (
              <div className="min-w-0">
                <p className="truncate font-heading text-sm font-bold tracking-tight text-white">
                  TestImpact AI
                </p>
                <p className="truncate text-[11px] font-medium text-slate-300/80">
                  Regression Test Intelligence
                </p>
              </div>
            )}
          </div>
          {isMobile && (
            <button
              type="button"
              onClick={() => setMobileMenuOpen(false)}
              aria-label="Close navigation menu"
              className="rounded-md p-1.5 text-slate-300 hover:bg-white/10 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        {/* Navigation Links */}
        <nav aria-label="Primary navigation" className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                onClick={() => setMobileMenuOpen(false)}
                title={collapsed ? item.label : undefined}
                className={({ isActive }) => {
                  const active =
                    isActive ||
                    (item.matchPrefix ? location.pathname.startsWith(item.matchPrefix) : false);
                  return `group flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors ${
                    collapsed ? 'justify-center px-2' : ''
                  } ${
                    active
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-300 hover:bg-white/10 hover:text-white'
                  }`;
                }}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </NavLink>
            );
          })}
        </nav>

        {/* Bottom Metadata & Controls */}
        <div className="border-t border-white/10 p-3 space-y-3">
          {!collapsed ? (
            <>
              <ThemeToggle className="border-white/15 bg-white/5 text-slate-200 hover:bg-white/10 hover:text-white" />
              <div className="rounded-md bg-white/5 px-3 py-2.5 text-xs">
                <div className="flex items-center justify-between text-slate-300">
                  <span className="font-medium">Team</span>
                  <span className="font-semibold text-white">SynapseX</span>
                </div>
                <div className="mt-1 flex items-center justify-between text-slate-400">
                  <span>Version</span>
                  <span className="font-mono text-[11px] text-teal-300">1.0.0</span>
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <ThemeToggle compact className="!border-white/15 !bg-white/5 !text-slate-200 hover:!bg-white/10" />
              <span className="font-mono text-[10px] text-slate-400">v1.0</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="flex min-h-screen bg-app-bg text-app-text">
      {/* Desktop Fixed/Collapsible Sidebar */}
      <aside
        className={`hidden md:flex md:flex-col md:fixed md:inset-y-0 md:z-30 border-r border-slate-800/40 transition-all duration-200 ${
          sidebarCollapsed ? 'md:w-[72px]' : 'md:w-64'
        }`}
      >
        {renderSidebarContent(false)}
      </aside>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div
            className="fixed inset-0 bg-slate-950/60"
            onClick={() => setMobileMenuOpen(false)}
          />
          <aside className="relative z-10 w-64 max-w-[85vw] flex-shrink-0 shadow-2xl">
            {renderSidebarContent(true)}
          </aside>
        </div>
      )}

      {/* Main Content Shell */}
      <div
        className={`flex min-w-0 flex-1 flex-col transition-all duration-200 ${
          sidebarCollapsed ? 'md:pl-[72px]' : 'md:pl-64'
        }`}
      >
        {/* Top Header */}
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-4 border-b border-app-border bg-app-surface/95 px-4 backdrop-blur-sm sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Open navigation menu"
              className="rounded-md border border-app-border-strong p-2 text-app-text-secondary hover:bg-app-muted hover:text-app-text md:hidden"
            >
              <Menu className="h-4 w-4" />
            </button>

            <button
              type="button"
              onClick={() => setSidebarCollapsed((prev) => !prev)}
              aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              className="hidden rounded-md border border-app-border p-1.5 text-app-text-secondary hover:bg-app-muted hover:text-app-text md:inline-flex"
            >
              {sidebarCollapsed ? (
                <PanelLeftOpen className="h-4 w-4" />
              ) : (
                <PanelLeftClose className="h-4 w-4" />
              )}
            </button>

            <div className="min-w-0">
              <div className="hidden sm:flex items-center gap-1.5 text-[11px] font-medium text-app-text-secondary">
                <span>TestImpact AI</span>
                <ChevronRight className="h-3 w-3" />
                <span>{routeMeta.section}</span>
              </div>
              <h1 className="truncate font-heading text-base font-bold text-app-text sm:text-lg">
                {routeMeta.title}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Backend Status Pill */}
            <div
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${
                healthQuery.isLoading
                  ? 'border-app-border bg-app-muted text-app-text-secondary'
                  : isBackendOnline
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-300'
                  : 'border-red-200 bg-red-50 text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300'
              }`}
              title={
                capabilities
                  ? `RAG Embeddings: ${capabilities.rag_available ? 'Ready' : 'Not Configured'} | LLM Explanations: ${capabilities.llm_explanations_available ? 'Available' : 'Disabled'}`
                  : 'Checking FastAPI server connectivity'
              }
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  healthQuery.isLoading
                    ? 'animate-pulse bg-slate-400'
                    : isBackendOnline
                    ? 'bg-emerald-500'
                    : 'bg-red-500'
                }`}
              />
              <span className="hidden sm:inline">
                {healthQuery.isLoading
                  ? 'Connecting...'
                  : isBackendOnline
                  ? 'FastAPI Connected'
                  : 'Backend Offline'}
              </span>
              <span className="sm:hidden">
                {healthQuery.isLoading ? '...' : isBackendOnline ? 'Online' : 'Offline'}
              </span>
            </div>

            {isBackendOnline && capabilities && (
              <div className="hidden lg:flex items-center gap-1.5 rounded-full border border-app-border bg-app-muted/70 px-2.5 py-1 text-[11px] font-medium text-app-text-secondary">
                <span
                  className={
                    capabilities.rag_available
                      ? 'text-teal-600 dark:text-teal-400'
                      : 'text-app-text-secondary'
                  }
                >
                  RAG: {capabilities.rag_available ? 'On' : 'Off'}
                </span>
                <span className="text-app-border-strong">|</span>
                <span
                  className={
                    capabilities.llm_explanations_available
                      ? 'text-indigo-600 dark:text-indigo-400'
                      : 'text-app-text-secondary'
                  }
                >
                  LLM: {capabilities.llm_explanations_available ? 'On' : 'Off'}
                </span>
              </div>
            )}

            <ThemeToggle compact />
          </div>
        </header>

        {/* Main View */}
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
};

