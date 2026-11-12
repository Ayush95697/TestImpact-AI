import React from 'react';
import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  Bot,
  CheckCircle2,
  Cpu,
  Database,
  FileCode2,
  GitPullRequest,
  Layers,
  Search,
  Server,
  ShieldCheck,
  UserCheck,
} from 'lucide-react';
import { useSystemCapabilities } from '../hooks/useSystemStatus';

interface WorkflowStep {
  label: string;
  subtitle: string;
  icon: React.FC<{ className?: string }>;
  optional?: boolean;
}

const WORKFLOW_STEPS: WorkflowStep[] = [
  { label: 'Change Request', subtitle: 'Proposed modifications & modules', icon: GitPullRequest },
  { label: 'FastAPI Backend', subtitle: 'Validation & orchestration', icon: Server },
  { label: 'Historical Data Retrieval', subtitle: 'Test cases, defects & runs', icon: Layers },
  { label: 'Company Text Embeddings API', subtitle: '736-dim dense vectors', icon: Cpu },
  { label: 'ChromaDB Semantic Search', subtitle: 'Project-isolated retrieval', icon: Database },
  { label: 'Recommendation Engine', subtitle: 'Deterministic scoring & rank', icon: ShieldCheck },
  { label: 'Optional LLM Explanation', subtitle: 'LLaMA 3.1 8B grounded notes', icon: Bot, optional: true },
  { label: 'QA Review', subtitle: 'Human Accept / Reject audit', icon: UserCheck },
];

const SOLUTION_STEPS = [
  'Stores projects, modules, test cases, defects and execution history.',
  'Accepts a new developer change request.',
  'Retrieves relevant historical records using semantic search.',
  'Combines retrieved evidence with known module-to-test relationships.',
  'Ranks candidate test cases using deterministic scoring.',
  'Uses an LLM optionally to explain recommendations.',
  'Allows QA engineers to review and accept or reject suggestions.',
];

const PROBLEM_DRIVERS = [
  'Bug fixes',
  'New features',
  'API modifications',
  'Business logic updates',
];

const LIMITATIONS = [
  'The current system is a decision-support prototype.',
  'Recommendations are heuristic and evidence-based.',
  'It does not automatically inspect Git diffs.',
  'It does not automatically execute regression tests.',
  'The QA engineer makes final testing decisions.',
  'Recommendations are not guaranteed proof of impact.',
];

const TEAM_MEMBERS = [
  { name: 'Aastha Teotia', initials: 'AT', accent: 'bg-indigo-600' },
  { name: 'Mankaran Saini', initials: 'MS', accent: 'bg-teal-600' },
  { name: 'Ayush Mishra', initials: 'AM', accent: 'bg-navy' },
];

export const AboutPage: React.FC = () => {
  const capabilitiesQuery = useSystemCapabilities();
  const capabilities = capabilitiesQuery.data;

  const techStack = [
    { name: 'React', category: 'Frontend UI', status: 'Active' },
    { name: 'TypeScript', category: 'Type Safety', status: 'Active' },
    { name: 'Tailwind CSS', category: 'Design System', status: 'Active' },
    { name: 'FastAPI', category: 'REST API Backend', status: 'Active' },
    { name: 'Python', category: 'Core Runtime', status: 'Active' },
    { name: 'SQLAlchemy', category: 'ORM Layer', status: 'Active' },
    { name: 'SQLite', category: 'Local development database', status: 'Active' },
    { name: 'LangChain', category: 'RAG & LLM Abstraction', status: 'Active' },
    {
      name: 'Company Text Embeddings API',
      category: 'Vector Generation',
      status: capabilities
        ? capabilities.rag_available
          ? 'Configured'
          : 'Unconfigured (Optional/Env)'
        : 'Backend-configured',
    },
    { name: 'ChromaDB', category: 'Local Vector Store', status: 'Active' },
    {
      name: 'LLaMA 3.1 8B',
      category: 'Optional Explanation Model',
      status: capabilities
        ? capabilities.llm_explanations_available
          ? 'Configured (Active)'
          : 'Optional / Not Configured'
        : 'Optional (When Configured)',
    },
  ];

  return (
    <div className="space-y-8">
      {/* A. Hero Section */}
      <section className="surface-card overflow-hidden border-t-4 border-t-indigo-600 p-6 sm:p-8">
        <div className="max-w-4xl space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded bg-indigo-50 px-2.5 py-0.5 font-mono text-xs font-semibold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
              TestImpact AI
            </span>
            <span className="text-xs font-medium text-app-text-secondary">
              Version 1.0.0
            </span>
          </div>

          <h2 className="font-heading text-2xl font-extrabold tracking-tight text-app-text sm:text-3xl">
            TestImpactAI - Intelligence Test Coverage and Impact Analysis
          </h2>

          <p className="text-base font-semibold text-indigo-600 dark:text-indigo-400">
            Understand Change Impact. Prioritize Regression Testing.
          </p>

          <p className="text-sm leading-relaxed text-app-text-secondary sm:text-base">
            TestImpact AI is an AI-assisted regression testing decision-support platform
            that helps QA teams identify existing test cases that may need to be re-executed
            when application functionality changes.
          </p>
        </div>
      </section>

      {/* B. The Problem & C. Our Solution */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="surface-card p-6">
          <div className="mb-4 flex items-center gap-2.5">
            <div className="rounded-md bg-amber-50 p-2 text-amber-600 dark:bg-amber-950/50 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4" />
            </div>
            <h3 className="font-heading text-base font-bold text-app-text">The Problem</h3>
          </div>

          <p className="text-sm text-app-text-secondary">
            Software applications constantly change through:
          </p>
          <ul className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {PROBLEM_DRIVERS.map((driver) => (
              <li
                key={driver}
                className="flex items-center gap-2 rounded-md border border-app-border bg-app-muted/40 px-3 py-2 text-xs font-medium text-app-text"
              >
                <FileCode2 className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
                {driver}
              </li>
            ))}
          </ul>

          <div className="mt-4 space-y-2.5 text-sm leading-relaxed text-app-text-secondary">
            <p>
              A change in one area can unintentionally break another. Running every test
              after every change is inefficient, while testing only the modified component
              may miss side effects.
            </p>
            <p className="font-medium text-app-text">
              Identifying relevant existing regression tests is a major challenge.
            </p>
          </div>
        </section>

        <section className="surface-card p-6">
          <div className="mb-4 flex items-center gap-2.5">
            <div className="rounded-md bg-teal-50 p-2 text-teal-600 dark:bg-teal-950/50 dark:text-teal-400">
              <Search className="h-4 w-4" />
            </div>
            <h3 className="font-heading text-base font-bold text-app-text">Our Solution</h3>
          </div>

          <ol className="space-y-2.5">
            {SOLUTION_STEPS.map((step, index) => (
              <li key={step} className="flex items-start gap-3 text-sm text-app-text">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-600 font-mono text-[11px] font-bold text-white">
                  {index + 1}
                </span>
                <span className="leading-relaxed">{step}</span>
              </li>
            ))}
          </ol>
        </section>
      </div>

      {/* D. How It Works */}
      <section className="surface-card p-6">
        <div className="mb-5">
          <h3 className="font-heading text-base font-bold text-app-text">How It Works</h3>
          <p className="mt-0.5 text-xs text-app-text-secondary">
            End-to-end deterministic impact scoring paired with semantic retrieval and optional LLaMA explanations
          </p>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {WORKFLOW_STEPS.map((step, idx) => {
            const Icon = step.icon;
            return (
              <div
                key={step.label}
                className="relative flex flex-col justify-between rounded-md border border-app-border bg-app-muted/35 p-4"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-50 text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-300">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="font-mono text-[11px] font-bold text-app-text-secondary">
                      0{idx + 1}
                    </span>
                  </div>
                  {step.optional && (
                    <span className="rounded border border-indigo-200 bg-indigo-50 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-700 dark:border-indigo-800 dark:bg-indigo-950/50 dark:text-indigo-300">
                      Optional
                    </span>
                  )}
                </div>

                <div className="mt-3">
                  <p className="text-xs font-bold text-app-text">{step.label}</p>
                  <p className="mt-0.5 text-[11px] text-app-text-secondary">
                    {step.subtitle}
                  </p>
                </div>

                {idx < WORKFLOW_STEPS.length - 1 && (
                  <div className="mt-3 flex justify-end text-app-text-secondary/70">
                    <ArrowRight className="hidden h-3.5 w-3.5 lg:block" />
                    <ArrowDown className="h-3.5 w-3.5 lg:hidden" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* E. Technology Stack & F. Scope and Limitations */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <section className="surface-card p-6 lg:col-span-7">
          <div className="mb-4">
            <h3 className="font-heading text-base font-bold text-app-text">
              Technology Stack
            </h3>
            <p className="mt-0.5 text-xs text-app-text-secondary">
              Core implemented platform components and capability-gated enterprise services
            </p>
          </div>

          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            {techStack.map((item) => {
              const isOptional =
                item.status.toLowerCase().includes('optional') ||
                item.status.toLowerCase().includes('unconfigured');
              return (
                <div
                  key={item.name}
                  className="flex items-start justify-between gap-2 rounded-md border border-app-border bg-app-muted/30 px-3.5 py-2.5"
                >
                  <div>
                    <p className="text-xs font-bold text-app-text">{item.name}</p>
                    <p className="text-[11px] text-app-text-secondary">{item.category}</p>
                  </div>
                  <span
                    className={`shrink-0 rounded px-2 py-0.5 text-[10px] font-semibold ${
                      isOptional
                        ? 'bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300'
                        : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                    }`}
                  >
                    {item.status}
                  </span>
                </div>
              );
            })}
          </div>
        </section>

        <section className="surface-card p-6 lg:col-span-5">
          <div className="mb-4 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-teal-600 dark:text-teal-400" />
            <h3 className="font-heading text-base font-bold text-app-text">
              Project Scope &amp; Limitations
            </h3>
          </div>

          <ul className="space-y-2.5 text-sm text-app-text-secondary">
            {LIMITATIONS.map((item) => (
              <li key={item} className="flex items-start gap-2.5">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-600 dark:bg-teal-400" />
                <span className="leading-relaxed">{item}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {/* G. Meet Team SynapseX */}
      <section className="surface-card p-6">
        <div className="mb-5 text-center sm:text-left">
          <p className="font-mono text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
            Team Name: SynapseX
          </p>
          <h3 className="mt-1 font-heading text-lg font-bold text-app-text">
            Meet Team SynapseX
          </h3>
          <p className="mt-0.5 text-xs text-app-text-secondary">
            Project: TestImpactAI - Intelligence Test Coverage and Impact Analysis
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {TEAM_MEMBERS.map((member) => (
            <div
              key={member.name}
              className="flex items-center gap-4 rounded-lg border border-app-border bg-app-muted/30 p-5"
            >
              <div
                aria-hidden="true"
                className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full font-heading text-sm font-bold text-white ${member.accent}`}
              >
                {member.initials}
              </div>
              <div className="min-w-0">
                <h4 className="truncate font-heading text-sm font-bold text-app-text">
                  {member.name}
                </h4>
                <p className="mt-0.5 text-xs text-app-text-secondary">Team SynapseX</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* H. Footer */}
      <footer className="surface-card flex flex-col items-start justify-between gap-2 px-6 py-4 text-xs text-app-text-secondary sm:flex-row sm:items-center">
        <div>
          <span className="font-semibold text-app-text">TestImpact AI</span>
          <span className="mx-2 text-app-border-strong">|</span>
          <span>TestImpactAI - Intelligence Test Coverage and Impact Analysis</span>
        </div>
        <div className="flex items-center gap-3 font-mono">
          <span>Team SynapseX</span>
          <span className="text-app-border-strong">|</span>
          <span className="font-semibold text-app-text">Version 1.0.0</span>
        </div>
      </footer>
    </div>
  );
};

