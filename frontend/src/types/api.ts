export interface HealthResponse {
  status: string;
  application: string;
}

export interface SystemCapabilitiesResponse {
  rag_available: boolean;
  llm_explanations_available: boolean;
}

export interface ProjectOverviewItem {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  module_count: number;
  test_case_count: number;
  defect_count: number;
  change_request_count: number;
}

export interface DistributionItem {
  label: string;
  count: number;
}

export interface AnalysisRunSummaryResponse {
  id: number;
  change_request_id: number | null;
  change_request_title: string | null;
  project_id: number | null;
  project_name: string | null;
  status: string;
  total_recommendations: number;
  created_at: string;
  completed_at: string | null;
}

export interface AnalysisRunListResponse {
  total: number;
  limit: number;
  offset: number;
  items: AnalysisRunSummaryResponse[];
}

export interface DashboardSummaryResponse {
  total_projects: number;
  total_modules: number;
  total_test_cases: number;
  total_defects: number;
  total_change_requests: number;
  total_analysis_runs: number;
  projects_overview: ProjectOverviewItem[];
  impact_level_distribution: DistributionItem[];
  execution_status_distribution: DistributionItem[];
  recent_analysis_runs: AnalysisRunSummaryResponse[];
}

export interface Project {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string | null;
}

export interface ProjectUpdate {
  name?: string;
  description?: string | null;
}

export interface ModuleItem {
  id: number;
  project_id: number;
  name: string;
  description: string | null;
}

export interface ModuleCreate {
  name: string;
  description?: string | null;
}

export interface ModuleUpdate {
  name?: string;
  description?: string | null;
}

export interface TestCase {
  id: number;
  project_id: number;
  title: string;
  steps: string;
  expected_result: string;
  priority: string;
  module_ids: number[];
}

export interface TestCaseCreate {
  project_id: number;
  title: string;
  steps: string;
  expected_result: string;
  priority: string;
  module_ids: number[];
}

export interface TestCaseUpdate {
  title?: string;
  steps?: string;
  expected_result?: string;
  priority?: string;
  module_ids?: number[];
}

export interface Defect {
  id: number;
  project_id: number;
  module_id: number;
  title: string;
  description: string;
  resolution_notes: string | null;
  severity: string;
  created_at: string;
}

export interface DefectCreate {
  project_id: number;
  module_id: number;
  title: string;
  description: string;
  resolution_notes?: string | null;
  severity: string;
}

export interface DefectUpdate {
  title?: string;
  description?: string;
  resolution_notes?: string | null;
  severity?: string;
}

export type ExecutionStatus = 'passed' | 'failed' | 'blocked';

export interface TestExecution {
  id: number;
  test_case_id: number;
  status: ExecutionStatus | string;
  build_version: string | null;
  executed_at: string;
}

export interface TestExecutionCreate {
  test_case_id: number;
  status: ExecutionStatus;
  build_version?: string | null;
}

export interface ChangeRequest {
  id: number;
  project_id: number;
  title: string;
  description: string;
  status: string;
  module_ids: number[];
  created_at: string;
}

export interface ChangeRequestCreate {
  project_id: number;
  title: string;
  description: string;
  status?: string;
  module_ids: number[];
}

export interface ChangeRequestUpdate {
  title?: string;
  description?: string;
  status?: string;
  module_ids?: number[];
}

export interface SupportingEvidence {
  source_type: string;
  source_id: number;
  title: string;
  retrieval_rank?: number | null;
  distance?: number | null;
  module_id?: number | null;
  module_name?: string | null;
}

export type ReviewStatus = 'pending' | 'accepted' | 'rejected';

export interface Recommendation {
  id: number;
  test_case_id: number;
  test_case_title: string;
  rank: number;
  score: number;
  impact_level: string;
  reason: string;
  score_breakdown: Record<string, number>;
  supporting_evidence: SupportingEvidence[];
  review_status: ReviewStatus | string;
}

export interface AnalysisResponse {
  analysis_run_id: number;
  change_request_id: number;
  project_id: number;
  status: string;
  total_recommendations: number;
  recommendations: Recommendation[];
}

export interface AnalysisRunDetail {
  id: number;
  change_request_id: number | null;
  status: string;
  created_at: string;
  completed_at: string | null;
  total_recommendations: number;
  recommendations: Recommendation[];
}

export interface EvidenceReference {
  source_type: string;
  source_id: number;
}

export interface RecommendationExplanation {
  recommendation_id: number;
  test_case_id: number;
  explanation: string;
  evidence_refs: EvidenceReference[];
}

export interface AnalysisExplanation {
  analysis_run_id: number;
  model_name: string;
  overall_summary: string;
  risk_observations: string[];
  recommendations: RecommendationExplanation[];
  limitations: string[];
  created_at: string;
}

export interface IndexResponse {
  project_id: number;
  total_indexed: number;
  test_cases_indexed: number;
  defects_indexed: number;
  test_executions_indexed: number;
  status: string;
}

