import React from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { BarChart3 } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import type { DistributionItem, ProjectOverviewItem } from '../../types/api';

const IMPACT_COLORS: Record<string, string> = {
  High: '#DC2626',
  Medium: '#D97706',
  Low: '#0D9488',
};

const EXECUTION_COLORS: Record<string, string> = {
  passed: '#16A34A',
  failed: '#DC2626',
  blocked: '#D97706',
};

const EmptyChartPlaceholder: React.FC<{ title: string; subtitle: string }> = ({
  title,
  subtitle,
}) => (
  <div className="flex h-[240px] flex-col items-center justify-center rounded-md border border-dashed border-app-border px-4 text-center">
    <BarChart3 className="mb-2 h-6 w-6 text-app-text-secondary/70" />
    <p className="text-sm font-semibold text-app-text">{title}</p>
    <p className="mt-1 max-w-xs text-xs text-app-text-secondary">{subtitle}</p>
  </div>
);

interface DashboardChartsProps {
  impactDistribution: DistributionItem[];
  executionDistribution: DistributionItem[];
  projectsOverview: ProjectOverviewItem[];
}

export const DashboardCharts: React.FC<DashboardChartsProps> = ({
  impactDistribution,
  executionDistribution,
  projectsOverview,
}) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const gridColor = isDark ? '#293449' : '#E2E8F0';
  const tickColor = isDark ? '#94A3B8' : '#64748B';
  const tooltipStyle = {
    backgroundColor: isDark ? '#172033' : '#FFFFFF',
    borderColor: isDark ? '#334155' : '#E2E8F0',
    borderRadius: '8px',
    color: isDark ? '#F8FAFC' : '#0F172A',
    fontSize: '12px',
  };

  const hasImpactData = impactDistribution.some((item) => item.count > 0);
  const hasExecutionData = executionDistribution.some((item) => item.count > 0);
  const hasProjectAssets = projectsOverview.some(
    (project) => project.test_case_count > 0 || project.module_count > 0
  );

  const formattedExecData = executionDistribution.map((item) => ({
    ...item,
    displayLabel: item.label.charAt(0).toUpperCase() + item.label.slice(1),
  }));

  const projectBarData = projectsOverview.slice(0, 6).map((p) => ({
    name: p.name.length > 14 ? `${p.name.slice(0, 13)}…` : p.name,
    fullName: p.name,
    'Test Cases': p.test_case_count,
    Modules: p.module_count,
  }));

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {/* Chart 1: Recommendation Impact Distribution */}
      <section className="surface-card p-5">
        <div className="mb-4">
          <h3 className="text-sm font-bold text-app-text">
            Recommendations by Impact Level
          </h3>
          <p className="text-xs text-app-text-secondary">
            Distribution of deterministic heuristic classifications
          </p>
        </div>
        {hasImpactData ? (
          <div className="h-[240px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={impactDistribution}
                margin={{ top: 8, right: 12, left: -16, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: tickColor, fontSize: 12 }}
                  axisLine={{ stroke: gridColor }}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: tickColor, fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: isDark ? '#1E293B' : '#F1F5F9' }} />
                <Bar
                  dataKey="count"
                  name="Recommendations"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={48}
                  isAnimationActive={false}
                >
                  {impactDistribution.map((entry) => (
                    <Cell
                      key={entry.label}
                      fill={IMPACT_COLORS[entry.label] ?? '#4F46E5'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyChartPlaceholder
            title="No Recommendations Yet"
            subtitle="Trigger impact analysis on a change request to visualize heuristic impact levels."
          />
        )}
      </section>

      {/* Chart 2: Test Execution Status Distribution */}
      <section className="surface-card p-5">
        <div className="mb-4">
          <h3 className="text-sm font-bold text-app-text">
            Test Execution Status
          </h3>
          <p className="text-xs text-app-text-secondary">
            Historical pass, failure, and blocked run outcomes
          </p>
        </div>
        {hasExecutionData ? (
          <div className="h-[240px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={formattedExecData}
                  dataKey="count"
                  nameKey="displayLabel"
                  cx="50%"
                  cy="46%"
                  innerRadius={52}
                  outerRadius={78}
                  paddingAngle={3}
                  isAnimationActive={false}
                >
                  {formattedExecData.map((entry) => (
                    <Cell
                      key={entry.label}
                      fill={EXECUTION_COLORS[entry.label.toLowerCase()] ?? '#64748B'}
                    />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend
                  verticalAlign="bottom"
                  height={32}
                  wrapperStyle={{ fontSize: '12px', color: tickColor }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyChartPlaceholder
            title="No Execution History"
            subtitle="Record test executions inside a project to view pass/fail distribution."
          />
        )}
      </section>

      {/* Chart 3: Project-wise Test Case & Module Distribution */}
      <section className="surface-card p-5">
        <div className="mb-4">
          <h3 className="text-sm font-bold text-app-text">
            Project Coverage Footprint
          </h3>
          <p className="text-xs text-app-text-secondary">
            Test cases and architectural modules per project
          </p>
        </div>
        {hasProjectAssets ? (
          <div className="h-[240px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={projectBarData}
                margin={{ top: 8, right: 12, left: -16, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis
                  dataKey="name"
                  interval={0}
                  angle={-15}
                  textAnchor="end"
                  height={48}
                  tick={{ fill: tickColor, fontSize: 10 }}
                  axisLine={{ stroke: gridColor }}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: tickColor, fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  cursor={{ fill: isDark ? '#1E293B' : '#F1F5F9' }}
                  labelFormatter={(_, payload) =>
                    (payload?.[0]?.payload as { fullName?: string } | undefined)?.fullName ?? ''
                  }
                />
                <Legend
                  verticalAlign="bottom"
                  height={24}
                  wrapperStyle={{ fontSize: '12px', color: tickColor }}
                />
                <Bar
                  dataKey="Test Cases"
                  fill="#4F46E5"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={28}
                  isAnimationActive={false}
                />
                <Bar
                  dataKey="Modules"
                  fill="#0D9488"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={28}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyChartPlaceholder
            title="No Project Assets"
            subtitle="Create a project with modules and test cases to see coverage metrics."
          />
        )}
      </section>
    </div>
  );
};

