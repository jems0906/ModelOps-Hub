export type UserRole = "admin" | "viewer";

export type LoginResponse = {
  access_token: string;
  token_type: string;
};

export type ModelVersion = {
  id: number;
  model_id: number;
  version_tag: string;
  artifact_uri: string;
  changelog: string;
  created_by: string;
  created_at: string;
};

export type ModelRecord = {
  id: number;
  name: string;
  description: string;
  owner_team: string;
  created_at: string;
  versions: ModelVersion[];
};

export type Experiment = {
  id: number;
  model_version_id: number;
  run_name: string;
  parameters: Record<string, unknown>;
  metrics: Record<string, unknown>;
  artifact_uri: string;
  status: string;
  created_at: string;
};

export type DeployStatus = "pending" | "running" | "shifted" | "failed";
export type DeployStrategy = "canary" | "blue_green";

export type Deployment = {
  id: number;
  model_version_id: number;
  environment: string;
  strategy: DeployStrategy;
  status: DeployStatus;
  traffic_percent: number;
  notes: string;
  created_at: string;
};

export type InferenceLog = {
  id: number;
  model_version_id: number;
  request_id: string;
  latency_ms: number;
  status_code: number;
  error_message: string;
  created_at: string;
};

export type InferenceMetrics = {
  total_requests: number;
  error_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
};

export type DashboardSummary = {
  total_models: number;
  total_versions: number;
  total_experiments: number;
  active_deployments: number;
  inference_metrics: InferenceMetrics;
};
