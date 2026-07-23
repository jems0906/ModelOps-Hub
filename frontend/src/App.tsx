import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiRequest, asJsonObject } from "./api";
import {
  DashboardSummary,
  Deployment,
  DeployStatus,
  Experiment,
  InferenceLog,
  LoginResponse,
  ModelRecord,
  UserRole
} from "./types";

const defaultSummary: DashboardSummary = {
  total_models: 0,
  total_versions: 0,
  total_experiments: 0,
  active_deployments: 0,
  inference_metrics: {
    total_requests: 0,
    error_rate: 0,
    avg_latency_ms: 0,
    p95_latency_ms: 0
  }
};

function parseRoleFromToken(token: string): UserRole {
  try {
    const parts = token.split(".");
    if (parts.length < 2) {
      return "viewer";
    }
    const decoded = JSON.parse(atob(parts[1])) as { role?: string };
    return decoded.role === "admin" ? "admin" : "viewer";
  } catch {
    return "viewer";
  }
}

function formatTime(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function classifyRequest(statusCode: number): "ok" | "warn" | "error" {
  if (statusCode >= 500) {
    return "error";
  }
  if (statusCode >= 400) {
    return "warn";
  }
  return "ok";
}

const SLO_ERROR_RATE_TARGET = 0.02;
const SLO_P95_MS_TARGET = 250;

export default function App() {
  const [token, setToken] = useState<string>(localStorage.getItem("modelops_token") ?? "");
  const [role, setRole] = useState<UserRole>((localStorage.getItem("modelops_role") as UserRole) ?? "viewer");
  const [email, setEmail] = useState(localStorage.getItem("modelops_email") ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string>("");

  const [models, setModels] = useState<ModelRecord[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [logs, setLogs] = useState<InferenceLog[]>([]);
  const [summary, setSummary] = useState<DashboardSummary>(defaultSummary);

  const [newModelName, setNewModelName] = useState("");
  const [newModelTeam, setNewModelTeam] = useState("AI Platform");
  const [newModelDesc, setNewModelDesc] = useState("");

  const [selectedModelId, setSelectedModelId] = useState<number>(0);
  const [newVersionTag, setNewVersionTag] = useState("v1.0.0");
  const [newVersionUri, setNewVersionUri] = useState("s3://artifacts/model.pkl");
  const [newVersionChangelog, setNewVersionChangelog] = useState("");

  const [expVersionId, setExpVersionId] = useState<number>(0);
  const [expRunName, setExpRunName] = useState("baseline-run");
  const [expParameters, setExpParameters] = useState('{"lr": 0.01, "batch_size": 128}');
  const [expMetrics, setExpMetrics] = useState('{"auc": 0.91, "f1": 0.82}');
  const [expArtifact, setExpArtifact] = useState("s3://artifacts/experiment-1");

  const [depVersionId, setDepVersionId] = useState<number>(0);
  const [depStrategy, setDepStrategy] = useState<"canary" | "blue_green">("canary");
  const [depStatus, setDepStatus] = useState<DeployStatus>("pending");
  const [depTraffic, setDepTraffic] = useState(10);
  const [depEnv, setDepEnv] = useState("production");
  const [depNotes, setDepNotes] = useState("Initial rollout");

  const [logVersionId, setLogVersionId] = useState<number>(0);
  const [logRequestId, setLogRequestId] = useState("req-001");
  const [logLatency, setLogLatency] = useState(120);
  const [logStatusCode, setLogStatusCode] = useState(200);
  const [logError, setLogError] = useState("");

  const isAdmin = role === "admin";

  const versionOptions = useMemo(
    () =>
      models.flatMap((model) =>
        model.versions.map((version) => ({
          id: version.id,
          label: `${model.name} ${version.version_tag}`
        }))
      ),
    [models]
  );

  const deploymentStatusCounts = useMemo(() => {
    return deployments.reduce(
      (acc, item) => {
        acc[item.status] += 1;
        return acc;
      },
      {
        pending: 0,
        running: 0,
        shifted: 0,
        failed: 0
      } as Record<DeployStatus, number>
    );
  }, [deployments]);

  const avgTraffic = useMemo(() => {
    if (deployments.length === 0) {
      return 0;
    }
    return Math.round(deployments.reduce((sum, item) => sum + item.traffic_percent, 0) / deployments.length);
  }, [deployments]);

  const recentFailureRate = useMemo(() => {
    const recent = logs.slice(0, 20);
    if (recent.length === 0) {
      return 0;
    }
    const failures = recent.filter((item) => item.status_code >= 400).length;
    return failures / recent.length;
  }, [logs]);

  const recentLatencyBars = useMemo(() => {
    const rows = logs.slice(0, 16);
    const maxLatency = rows.reduce((max, row) => Math.max(max, row.latency_ms), 0);
    return rows
      .map((row) => ({
        requestId: row.request_id,
        statusCode: row.status_code,
        latencyMs: row.latency_ms,
        width: maxLatency > 0 ? (row.latency_ms / maxLatency) * 100 : 0
      }))
      .reverse();
  }, [logs]);

  const latestModelVersionByModel = useMemo(() => {
    return models.map((model) => {
      const latestVersion = model.versions[0];
      return {
        modelId: model.id,
        modelName: model.name,
        ownerTeam: model.owner_team,
        latestVersionTag: latestVersion?.version_tag ?? "none",
        latestVersionCreatedBy: latestVersion?.created_by ?? "-",
        latestVersionCreatedAt: latestVersion?.created_at ?? ""
      };
    });
  }, [models]);

  const deploymentTimeline = useMemo(() => {
    return [...deployments]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 6);
  }, [deployments]);

  const incidentFeed = useMemo(() => {
    return logs
      .filter((log) => log.status_code >= 500 || log.latency_ms > SLO_P95_MS_TARGET)
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 8);
  }, [logs]);

  const reliabilityScore = useMemo(() => {
    const errorPressure = Math.min(summary.inference_metrics.error_rate / SLO_ERROR_RATE_TARGET, 2);
    const latencyPressure = Math.min(summary.inference_metrics.p95_latency_ms / SLO_P95_MS_TARGET, 2);
    const score = Math.max(0, Math.round(100 - ((errorPressure + latencyPressure) / 4) * 100));
    return score;
  }, [summary.inference_metrics.error_rate, summary.inference_metrics.p95_latency_ms]);

  const errorBudgetRemaining = useMemo(() => {
    const usage = summary.inference_metrics.error_rate / SLO_ERROR_RATE_TARGET;
    return Math.max(0, Math.min(100, Math.round((1 - usage) * 100)));
  }, [summary.inference_metrics.error_rate]);

  async function refreshAll(currentToken: string) {
    setIsRefreshing(true);
    const [modelRows, experimentRows, deploymentRows, logRows, summaryRow] = await Promise.all([
      apiRequest<ModelRecord[]>("/models", "GET", currentToken),
      apiRequest<Experiment[]>("/experiments", "GET", currentToken),
      apiRequest<Deployment[]>("/deployments", "GET", currentToken),
      apiRequest<InferenceLog[]>("/inference/logs", "GET", currentToken),
      apiRequest<DashboardSummary>("/dashboard/summary", "GET", currentToken)
    ]);

    setModels(modelRows);
    setExperiments(experimentRows);
    setDeployments(deploymentRows);
    setLogs(logRows);
    setSummary(summaryRow);

    const firstModel = modelRows[0];
    if (firstModel) {
      setSelectedModelId((prev) => prev || firstModel.id);
    }

    const firstVersion = modelRows.flatMap((m) => m.versions)[0];
    if (firstVersion) {
      setExpVersionId((prev) => prev || firstVersion.id);
      setDepVersionId((prev) => prev || firstVersion.id);
      setLogVersionId((prev) => prev || firstVersion.id);
    }

    setLastRefreshedAt(new Date().toISOString());
    setIsRefreshing(false);
  }

  useEffect(() => {
    if (!token) {
      return;
    }

    refreshAll(token).catch((err) => {
      setError(err.message);
      setIsRefreshing(false);
    });
  }, [token]);

  async function login(e: FormEvent) {
    e.preventDefault();
    setError("");

    const formData = new URLSearchParams();
    formData.append("username", email);
    formData.append("password", password);

    try {
      const data = await apiRequest<LoginResponse>("/auth/login", "POST", undefined, formData, true);
      const detectedRole = parseRoleFromToken(data.access_token);
      setToken(data.access_token);
      setRole(detectedRole);

      localStorage.setItem("modelops_token", data.access_token);
      localStorage.setItem("modelops_role", detectedRole);
      localStorage.setItem("modelops_email", email);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function logout() {
    localStorage.removeItem("modelops_token");
    localStorage.removeItem("modelops_role");
    localStorage.removeItem("modelops_email");
    setToken("");
    setRole("viewer");
    setEmail("");
    setPassword("");
    setModels([]);
    setExperiments([]);
    setDeployments([]);
    setLogs([]);
    setSummary(defaultSummary);
    setLastRefreshedAt("");
  }

  async function createModel(e: FormEvent) {
    e.preventDefault();
    if (!token || !isAdmin) {
      return;
    }

    await apiRequest<ModelRecord>("/models", "POST", token, {
      name: newModelName,
      description: newModelDesc,
      owner_team: newModelTeam
    });
    setNewModelName("");
    setNewModelDesc("");
    await refreshAll(token);
  }

  async function createVersion(e: FormEvent) {
    e.preventDefault();
    if (!token || !isAdmin || !selectedModelId) {
      return;
    }

    await apiRequest(`/models/${selectedModelId}/versions`, "POST", token, {
      version_tag: newVersionTag,
      artifact_uri: newVersionUri,
      changelog: newVersionChangelog
    });

    setNewVersionChangelog("");
    await refreshAll(token);
  }

  async function createExperiment(e: FormEvent) {
    e.preventDefault();
    if (!token || !isAdmin || !expVersionId) {
      return;
    }

    await apiRequest("/experiments", "POST", token, {
      model_version_id: expVersionId,
      run_name: expRunName,
      parameters: asJsonObject(expParameters),
      metrics: asJsonObject(expMetrics),
      artifact_uri: expArtifact,
      status: "completed"
    });

    await refreshAll(token);
  }

  async function createDeployment(e: FormEvent) {
    e.preventDefault();
    if (!token || !isAdmin || !depVersionId) {
      return;
    }

    await apiRequest("/deployments", "POST", token, {
      model_version_id: depVersionId,
      environment: depEnv,
      strategy: depStrategy,
      status: depStatus,
      traffic_percent: depTraffic,
      notes: depNotes
    });

    await refreshAll(token);
  }

  async function createInferenceLog(e: FormEvent) {
    e.preventDefault();
    if (!token || !logVersionId) {
      return;
    }

    await apiRequest("/inference/logs", "POST", token, {
      model_version_id: logVersionId,
      request_id: logRequestId,
      latency_ms: logLatency,
      status_code: logStatusCode,
      error_message: logError
    });

    await refreshAll(token);
  }

  if (!token) {
    return (
      <main className="login-shell">
        <section className="login-panel">
          <h1>ModelOps Hub</h1>
          <p>Model lifecycle governance, experiment intelligence, and live inference observability.</p>
          <form onSubmit={login} className="form-grid">
            <label>
              Email
              <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="admin@modelops.local" required />
            </label>
            <label>
              Password
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </label>
            <button type="submit">Sign In</button>
          </form>
          <small>Demo users: admin@modelops.local/admin1234 or viewer@modelops.local/viewer1234</small>
          {error && <div className="error">{error}</div>}
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="header-title-wrap">
          <h1>ModelOps Hub</h1>
          <p>Lifecycle governance, deployment control, and inference reliability in one control plane.</p>
        </div>
        <div className="header-actions">
          <div className={`status-pill ${summary.inference_metrics.error_rate >= 0.1 ? "status-error" : "status-ok"}`}>
            {summary.inference_metrics.error_rate >= 0.1 ? "Attention" : "Stable"}
          </div>
          <button onClick={() => refreshAll(token).catch((err) => setError(err.message))} disabled={isRefreshing}>
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </button>
          <button onClick={logout}>Log Out</button>
        </div>
      </header>

      <section className="ops-ribbon">
        <article>
          <h4>Operator</h4>
          <p>{email}</p>
          <small>Role: {role}</small>
        </article>
        <article>
          <h4>Last refresh</h4>
          <p>{lastRefreshedAt ? formatTime(lastRefreshedAt) : "Not yet"}</p>
          <small>{isRefreshing ? "Sync in progress" : "Data synchronized"}</small>
        </article>
        <article>
          <h4>Rollout avg traffic</h4>
          <p>{avgTraffic}%</p>
          <small>Across {deployments.length} deployments</small>
        </article>
        <article>
          <h4>Recent failure ratio</h4>
          <p>{formatPercent(recentFailureRate)}</p>
          <small>Last {Math.min(logs.length, 20)} requests</small>
        </article>
      </section>

      <section className="cards">
        <article className="kpi-card">
          <h3>Registered Models</h3>
          <p>{summary.total_models}</p>
          <small>Versioned assets under governance</small>
        </article>
        <article className="kpi-card">
          <h3>Version Count</h3>
          <p>{summary.total_versions}</p>
          <small>All immutable release records</small>
        </article>
        <article className="kpi-card">
          <h3>Tracked Experiments</h3>
          <p>{summary.total_experiments}</p>
          <small>Metrics, parameters, and artifacts</small>
        </article>
        <article className="kpi-card">
          <h3>Active Deployments</h3>
          <p>{summary.active_deployments}</p>
          <small>Running rollout sessions</small>
        </article>
      </section>

      <section className="cards metrics-grid">
        <article className="metric-card">
          <h3>Total Requests</h3>
          <p>{summary.inference_metrics.total_requests}</p>
          <small>Observed inference calls</small>
        </article>
        <article className="metric-card">
          <h3>Error Rate</h3>
          <p>{formatPercent(summary.inference_metrics.error_rate)}</p>
          <small className={summary.inference_metrics.error_rate >= 0.1 ? "text-error" : "text-ok"}>
            {summary.inference_metrics.error_rate >= 0.1 ? "Above target" : "Within target"}
          </small>
        </article>
        <article className="metric-card">
          <h3>Avg Latency</h3>
          <p>{summary.inference_metrics.avg_latency_ms} ms</p>
          <small>End-to-end response average</small>
        </article>
        <article className="metric-card">
          <h3>P95 Latency</h3>
          <p>{summary.inference_metrics.p95_latency_ms} ms</p>
          <small>Tail latency pressure</small>
        </article>
      </section>

      <section className="cards metrics-grid deployment-health-grid">
        <article className="health-card">
          <h3>Pending</h3>
          <p>{deploymentStatusCounts.pending}</p>
        </article>
        <article className="health-card">
          <h3>Running</h3>
          <p>{deploymentStatusCounts.running}</p>
        </article>
        <article className="health-card">
          <h3>Shifted</h3>
          <p>{deploymentStatusCounts.shifted}</p>
        </article>
        <article className="health-card health-failed">
          <h3>Failed</h3>
          <p>{deploymentStatusCounts.failed}</p>
        </article>
      </section>

      <section className="ops-deep-grid">
        <article className="panel slo-panel">
          <h2>SLO Guardrails</h2>
          <p className="panel-subtitle">Reliability score and budget posture against live inference behavior.</p>
          <div className="slo-score-row">
            <div>
              <span className="label">Reliability score</span>
              <p className="score-value">{reliabilityScore}</p>
            </div>
            <div>
              <span className="label">Error budget remaining</span>
              <p className={`score-value ${errorBudgetRemaining < 40 ? "text-error" : "text-ok"}`}>{errorBudgetRemaining}%</p>
            </div>
          </div>
          <div className="slo-track-wrap">
            <div className="slo-track-label-row">
              <span>Error rate target ({formatPercent(SLO_ERROR_RATE_TARGET)})</span>
              <span>{formatPercent(summary.inference_metrics.error_rate)}</span>
            </div>
            <div className="slo-track">
              <div
                className={`slo-fill ${summary.inference_metrics.error_rate > SLO_ERROR_RATE_TARGET ? "slo-bad" : "slo-good"}`}
                style={{ width: `${Math.min((summary.inference_metrics.error_rate / SLO_ERROR_RATE_TARGET) * 100, 100)}%` }}
              />
            </div>
          </div>
          <div className="slo-track-wrap">
            <div className="slo-track-label-row">
              <span>P95 target ({SLO_P95_MS_TARGET} ms)</span>
              <span>{summary.inference_metrics.p95_latency_ms} ms</span>
            </div>
            <div className="slo-track">
              <div
                className={`slo-fill ${summary.inference_metrics.p95_latency_ms > SLO_P95_MS_TARGET ? "slo-bad" : "slo-good"}`}
                style={{ width: `${Math.min((summary.inference_metrics.p95_latency_ms / SLO_P95_MS_TARGET) * 100, 100)}%` }}
              />
            </div>
          </div>
        </article>

        <article className="panel timeline-panel">
          <h2>Release Timeline</h2>
          <p className="panel-subtitle">Latest rollout events across environments and strategies.</p>
          <ul>
            {deploymentTimeline.map((dep) => (
              <li key={dep.id} className="timeline-item">
                <div className="item-topline">
                  <strong>{dep.environment}</strong>
                  <span className="tag">v{dep.model_version_id}</span>
                  <span className={`status-pill status-${dep.status}`}>{dep.status}</span>
                </div>
                <div className="item-grid">
                  <span>strategy: {dep.strategy === "blue_green" ? "blue/green" : "canary"}</span>
                  <span>traffic: {dep.traffic_percent}%</span>
                  <span>{formatTime(dep.created_at)}</span>
                </div>
              </li>
            ))}
          </ul>
        </article>
      </section>

      <section className="panel">
        <h2>Incident Feed</h2>
        <p className="panel-subtitle">High-latency and server-error requests that need operator attention.</p>
        <ul className="incident-grid">
          {incidentFeed.length === 0 ? (
            <li className="incident-item incident-clear">
              <strong>No active incidents</strong>
              <span>Requests are currently within configured thresholds.</span>
            </li>
          ) : (
            incidentFeed.map((log) => (
              <li key={log.id} className="incident-item">
                <div className="item-topline">
                  <strong>{log.request_id}</strong>
                  <span className={`status-pill status-${classifyRequest(log.status_code)}`}>HTTP {log.status_code}</span>
                  {log.latency_ms > SLO_P95_MS_TARGET && <span className="tag">latency spike</span>}
                </div>
                <div className="item-grid">
                  <span>model version: {log.model_version_id}</span>
                  <span>latency: {log.latency_ms} ms</span>
                  <span>{formatTime(log.created_at)}</span>
                </div>
                {log.error_message && <small className="text-error">{log.error_message}</small>}
              </li>
            ))
          )}
        </ul>
      </section>

      {error && <div className="error">{error}</div>}

      <section className="panel-grid">
        <article className="panel">
          <h2>Model Registry</h2>
          <p className="panel-subtitle">Ownership, latest release lineage, and version progression.</p>
          <ul>
            {latestModelVersionByModel.map((model) => (
              <li key={model.modelId} className="registry-item">
                <div className="item-topline">
                  <strong>{model.modelName}</strong>
                  <span className="tag">{model.ownerTeam}</span>
                </div>
                <div className="item-grid">
                  <span>Latest version: {model.latestVersionTag}</span>
                  <span>Owner: {model.latestVersionCreatedBy}</span>
                  <span>{model.latestVersionCreatedAt ? formatTime(model.latestVersionCreatedAt) : "No version published"}</span>
                </div>
              </li>
            ))}
          </ul>
          <form onSubmit={createModel} className="form-grid">
            <h4>Add Model</h4>
            <input placeholder="Model name" value={newModelName} onChange={(e) => setNewModelName(e.target.value)} disabled={!isAdmin} required />
            <input placeholder="Owner team" value={newModelTeam} onChange={(e) => setNewModelTeam(e.target.value)} disabled={!isAdmin} required />
            <textarea placeholder="Description" value={newModelDesc} onChange={(e) => setNewModelDesc(e.target.value)} disabled={!isAdmin} />
            <button type="submit" disabled={!isAdmin}>Create Model</button>
          </form>
          <form onSubmit={createVersion} className="form-grid">
            <h4>Add Version</h4>
            <select value={selectedModelId} onChange={(e) => setSelectedModelId(Number(e.target.value))} disabled={!isAdmin || models.length === 0}>
              {models.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
            <input value={newVersionTag} onChange={(e) => setNewVersionTag(e.target.value)} disabled={!isAdmin} />
            <input value={newVersionUri} onChange={(e) => setNewVersionUri(e.target.value)} disabled={!isAdmin} />
            <textarea value={newVersionChangelog} onChange={(e) => setNewVersionChangelog(e.target.value)} disabled={!isAdmin} placeholder="Change log" />
            <button type="submit" disabled={!isAdmin}>Register Version</button>
          </form>
        </article>

        <article className="panel">
          <h2>Experiment Tracking</h2>
          <p className="panel-subtitle">Recent runs with metric payload visibility and artifact references.</p>
          <ul>
            {experiments.slice(0, 8).map((exp) => (
              <li key={exp.id} className="experiment-item">
                <div className="item-topline">
                  <strong>{exp.run_name}</strong>
                  <span className="tag">v{exp.model_version_id}</span>
                </div>
                <div className="item-grid">
                  <span>metrics: {JSON.stringify(exp.metrics)}</span>
                  <span>parameters: {JSON.stringify(exp.parameters)}</span>
                  <span>artifact: {exp.artifact_uri}</span>
                </div>
              </li>
            ))}
          </ul>
          <form onSubmit={createExperiment} className="form-grid">
            <h4>Track Experiment</h4>
            <select value={expVersionId} onChange={(e) => setExpVersionId(Number(e.target.value))} disabled={!isAdmin || versionOptions.length === 0}>
              {versionOptions.map((version) => (
                <option key={version.id} value={version.id}>{version.label}</option>
              ))}
            </select>
            <input value={expRunName} onChange={(e) => setExpRunName(e.target.value)} disabled={!isAdmin} />
            <textarea value={expParameters} onChange={(e) => setExpParameters(e.target.value)} disabled={!isAdmin} />
            <textarea value={expMetrics} onChange={(e) => setExpMetrics(e.target.value)} disabled={!isAdmin} />
            <input value={expArtifact} onChange={(e) => setExpArtifact(e.target.value)} disabled={!isAdmin} />
            <button type="submit" disabled={!isAdmin}>Save Experiment</button>
          </form>
        </article>

        <article className="panel">
          <h2>Deploy Workflow</h2>
          <p className="panel-subtitle">Rollout state and traffic posture for canary and blue/green controls.</p>
          <ul>
            {deployments.slice(0, 8).map((dep) => (
              <li key={dep.id} className="deployment-item">
                <div className="item-topline">
                  <strong>{dep.environment}</strong>
                  <span className="tag">{dep.strategy === "blue_green" ? "Blue/Green" : "Canary"}</span>
                  <span className={`status-pill status-${dep.status}`}>{dep.status}</span>
                </div>
                <div className="traffic-row">
                  <span>Version {dep.model_version_id}</span>
                  <span>{dep.traffic_percent}% traffic</span>
                </div>
                <div className="traffic-track">
                  <div className="traffic-fill" style={{ width: `${Math.min(Math.max(dep.traffic_percent, 0), 100)}%` }} />
                </div>
                <small>{dep.notes || "No notes"}</small>
              </li>
            ))}
          </ul>
          <form onSubmit={createDeployment} className="form-grid">
            <h4>Deploy Model</h4>
            <select value={depVersionId} onChange={(e) => setDepVersionId(Number(e.target.value))} disabled={!isAdmin || versionOptions.length === 0}>
              {versionOptions.map((version) => (
                <option key={version.id} value={version.id}>{version.label}</option>
              ))}
            </select>
            <input value={depEnv} onChange={(e) => setDepEnv(e.target.value)} disabled={!isAdmin} />
            <select value={depStrategy} onChange={(e) => setDepStrategy(e.target.value as "canary" | "blue_green")} disabled={!isAdmin}>
              <option value="canary">Canary</option>
              <option value="blue_green">Blue/Green</option>
            </select>
            <select value={depStatus} onChange={(e) => setDepStatus(e.target.value as DeployStatus)} disabled={!isAdmin}>
              <option value="pending">Pending</option>
              <option value="running">Running</option>
              <option value="shifted">Shifted</option>
              <option value="failed">Failed</option>
            </select>
            <input type="number" min={0} max={100} value={depTraffic} onChange={(e) => setDepTraffic(Number(e.target.value))} disabled={!isAdmin} />
            <textarea value={depNotes} onChange={(e) => setDepNotes(e.target.value)} disabled={!isAdmin} />
            <button type="submit" disabled={!isAdmin}>Create Deployment</button>
          </form>
        </article>

        <article className="panel">
          <h2>Inference Observability</h2>
          <p className="panel-subtitle">Request stream, latency trend, and response health classification.</p>
          <div className="latency-strip">
            {recentLatencyBars.map((point) => (
              <div
                key={`${point.requestId}-${point.statusCode}`}
                className={`latency-bar latency-${classifyRequest(point.statusCode)}`}
                style={{ width: `${Math.max(point.width, 4)}%` }}
                title={`${point.requestId}: ${point.latencyMs} ms (status ${point.statusCode})`}
              />
            ))}
          </div>
          <ul>
            {logs.slice(0, 10).map((log) => (
              <li key={log.id} className="inference-item">
                <div className="item-topline">
                  <strong>{log.request_id}</strong>
                  <span className={`status-pill status-${classifyRequest(log.status_code)}`}>HTTP {log.status_code}</span>
                </div>
                <div className="item-grid">
                  <span>version: {log.model_version_id}</span>
                  <span>latency: {log.latency_ms} ms</span>
                  <span>{formatTime(log.created_at)}</span>
                </div>
                {log.error_message && <small className="text-error">{log.error_message}</small>}
              </li>
            ))}
          </ul>
          <form onSubmit={createInferenceLog} className="form-grid">
            <h4>Log Inference</h4>
            <select value={logVersionId} onChange={(e) => setLogVersionId(Number(e.target.value))} disabled={versionOptions.length === 0}>
              {versionOptions.map((version) => (
                <option key={version.id} value={version.id}>{version.label}</option>
              ))}
            </select>
            <input value={logRequestId} onChange={(e) => setLogRequestId(e.target.value)} />
            <input type="number" value={logLatency} onChange={(e) => setLogLatency(Number(e.target.value))} />
            <input type="number" value={logStatusCode} onChange={(e) => setLogStatusCode(Number(e.target.value))} />
            <textarea value={logError} onChange={(e) => setLogError(e.target.value)} placeholder="Error text if any" />
            <button type="submit">Push Log</button>
          </form>
        </article>
      </section>
    </main>
  );
}
