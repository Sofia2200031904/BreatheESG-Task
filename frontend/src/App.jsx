import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileSearch,
  Filter,
  Lock,
  Pencil,
  RefreshCcw,
  ShieldCheck,
  Upload,
  XCircle,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";
const ACTOR = "maya.analyst";

const statusStyles = {
  valid: "bg-teal-50 text-teal-800 ring-teal-200",
  warning: "bg-amber-50 text-amber-800 ring-amber-200",
  failed: "bg-rose-50 text-rose-800 ring-rose-200",
  approved: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  rejected: "bg-zinc-100 text-zinc-700 ring-zinc-200",
};

const sourceLabels = {
  sap_fuel_procurement: "SAP Fuel & Procurement",
  utility_electricity: "Utility Electricity",
  corporate_travel: "Corporate Travel",
};

function App() {
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState("");
  const [sources, setSources] = useState([]);
  const [batches, setBatches] = useState([]);
  const [records, setRecords] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [summary, setSummary] = useState(null);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [filters, setFilters] = useState({ status: "", source_type: "", suspicious: false });
  const [uploadState, setUploadState] = useState({ data_source_id: "", file: null });
  const [editing, setEditing] = useState(false);
  const [editDraft, setEditDraft] = useState({});
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    apiGet("/companies/").then((data) => {
      setCompanies(data);
      if (data.length) setCompanyId(String(data[0].id));
    });
  }, []);

  useEffect(() => {
    if (!companyId) return;
    refreshWorkspace();
  }, [companyId, filters.status, filters.source_type, filters.suspicious]);

  const selectedCompany = companies.find((company) => String(company.id) === String(companyId));
  const failedRecords = records.filter((record) => record.status === "failed").length;
  const warningRecords = records.filter((record) => record.status === "warning").length;
  const approvedRecords = records.filter((record) => record.status === "approved").length;

  const visibleSources = useMemo(() => sources.filter((source) => String(source.company) === String(companyId)), [sources, companyId]);

  async function refreshWorkspace() {
    setLoading(true);
    setMessage("");
    try {
      const query = new URLSearchParams({ company_id: companyId });
      const recordQuery = new URLSearchParams({ company_id: companyId });
      if (filters.status) recordQuery.set("status", filters.status);
      if (filters.source_type) recordQuery.set("source_type", filters.source_type);
      if (filters.suspicious) recordQuery.set("suspicious", "true");
      const [sourceData, batchData, recordData, logData, summaryData] = await Promise.all([
        apiGet(`/data-sources/?${query}`),
        apiGet(`/batches/?${query}`),
        apiGet(`/records/?${recordQuery}`),
        apiGet(`/audit-logs/?${query}`),
        apiGet(`/summary/?${query}`),
      ]);
      setSources(sourceData);
      setBatches(batchData);
      setRecords(recordData);
      setAuditLogs(logData);
      setSummary(summaryData);
      setSelectedRecord((current) => {
        if (!current && recordData.length) return recordData[0];
        const updated = recordData.find((record) => record.id === current?.id);
        return updated || recordData[0] || null;
      });
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function uploadCsv(event) {
    event.preventDefault();
    if (!uploadState.data_source_id || !uploadState.file) {
      setMessage("Choose a source type and CSV file first.");
      return;
    }
    const formData = new FormData();
    formData.append("company_id", companyId);
    formData.append("data_source_id", uploadState.data_source_id);
    formData.append("uploaded_by", ACTOR);
    formData.append("file", uploadState.file);
    setLoading(true);
    try {
      const batch = await apiPost("/upload/", formData, true);
      setMessage(`Uploaded ${batch.original_filename}: ${batch.total_rows} rows processed.`);
      setUploadState({ data_source_id: uploadState.data_source_id, file: null });
      await refreshWorkspace();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  function startEdit(record) {
    setEditing(true);
    setEditDraft({
      activity_date: record.activity_date || "",
      period_start: record.period_start || "",
      period_end: record.period_end || "",
      facility_code: record.facility_code || "",
      category: record.category || "",
      subcategory: record.subcategory || "",
      quantity: record.quantity || "",
      unit: record.unit || "",
      co2e_kg: record.co2e_kg || "",
      resolve_issues: false,
    });
  }

  async function saveEdit() {
    if (!selectedRecord) return;
    try {
      const updated = await apiPatch(`/records/${selectedRecord.id}/`, { ...editDraft, actor: ACTOR });
      setSelectedRecord(updated);
      setEditing(false);
      setMessage("Record updated and audit log captured.");
      await refreshWorkspace();
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function reviewRecord(action) {
    if (!selectedRecord) return;
    try {
      const updated = await apiPost(`/records/${selectedRecord.id}/${action}/`, {
        actor: ACTOR,
        notes: action === "approve" ? "Reviewed for audit readiness." : "Rejected during analyst review.",
      });
      setSelectedRecord(updated);
      setMessage(action === "approve" ? "Record approved and locked." : "Record rejected.");
      await refreshWorkspace();
    } catch (error) {
      setMessage(error.message);
    }
  }

  return (
    <main className="min-h-screen bg-[#f7f8f4]">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-reef">
              <ShieldCheck className="h-4 w-4" />
              ESG ingestion and audit review
            </div>
            <h1 className="mt-1 text-2xl font-semibold tracking-normal text-ink md:text-3xl">
              Analyst workbench
            </h1>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <select
              className="h-10 rounded-md border border-zinc-300 bg-white px-3 text-sm shadow-sm"
              value={companyId}
              onChange={(event) => setCompanyId(event.target.value)}
            >
              {companies.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.name}
                </option>
              ))}
            </select>
            <button
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium shadow-sm hover:bg-zinc-50"
              onClick={refreshWorkspace}
              type="button"
            >
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <section className="border-b border-zinc-200 bg-[#eef5f1]">
        <div className="mx-auto grid max-w-7xl gap-3 px-4 py-4 md:grid-cols-4">
          <Metric label="Total records" value={summary?.records || 0} icon={Database} />
          <Metric label="Open issues" value={summary?.open_issues || 0} icon={AlertTriangle} tone="amber" />
          <Metric label="Approved" value={approvedRecords} icon={ClipboardCheck} tone="green" />
          <Metric label="CO2e kg" value={formatNumber(summary?.co2e_kg || 0)} icon={ShieldCheck} tone="ink" />
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-4 px-4 py-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <form className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm" onSubmit={uploadCsv}>
            <div className="mb-3 flex items-center gap-2">
              <Upload className="h-4 w-4 text-reef" />
              <h2 className="text-sm font-semibold text-ink">Upload source CSV</h2>
            </div>
            <div className="space-y-3">
              <select
                className="h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm"
                value={uploadState.data_source_id}
                onChange={(event) => setUploadState((state) => ({ ...state, data_source_id: event.target.value }))}
              >
                <option value="">Select source</option>
                {visibleSources.map((source) => (
                  <option key={source.id} value={source.id}>
                    {sourceLabels[source.source_type]}
                  </option>
                ))}
              </select>
              <input
                className="block w-full text-sm file:mr-3 file:h-9 file:rounded-md file:border-0 file:bg-ink file:px-3 file:text-sm file:font-medium file:text-white"
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => setUploadState((state) => ({ ...state, file: event.target.files?.[0] || null }))}
              />
              <button
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-reef px-3 text-sm font-semibold text-white shadow-sm hover:bg-teal-800 disabled:opacity-60"
                disabled={loading}
                type="submit"
              >
                <Upload className="h-4 w-4" />
                Process CSV
              </button>
            </div>
          </form>

          <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center gap-2">
              <Filter className="h-4 w-4 text-ink" />
              <h2 className="text-sm font-semibold text-ink">Review filters</h2>
            </div>
            <div className="space-y-3">
              <select
                className="h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm"
                value={filters.status}
                onChange={(event) => setFilters((state) => ({ ...state, status: event.target.value }))}
              >
                <option value="">All statuses</option>
                <option value="failed">Failed</option>
                <option value="warning">Warning</option>
                <option value="valid">Valid</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
              <select
                className="h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm"
                value={filters.source_type}
                onChange={(event) => setFilters((state) => ({ ...state, source_type: event.target.value }))}
              >
                <option value="">All sources</option>
                {Object.entries(sourceLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-2 text-sm text-zinc-700">
                <input
                  className="h-4 w-4 rounded border-zinc-300 text-reef"
                  checked={filters.suspicious}
                  type="checkbox"
                  onChange={(event) => setFilters((state) => ({ ...state, suspicious: event.target.checked }))}
                />
                Suspicious and failed only
              </label>
            </div>
          </div>

          <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-ink">Uploaded batches</h2>
            <div className="mt-3 space-y-2">
              {batches.slice(0, 8).map((batch) => (
                <button
                  className="w-full rounded-md border border-zinc-200 p-3 text-left hover:border-reef hover:bg-teal-50"
                  key={batch.id}
                  onClick={() => setFilters((state) => ({ ...state, status: "", suspicious: false }))}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium text-ink">{batch.original_filename}</span>
                    <StatusBadge status={batch.status} />
                  </div>
                  <p className="mt-1 text-xs text-zinc-500">
                    {batch.total_rows} rows | {sourceLabels[batch.source_type]}
                  </p>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <div className="space-y-4">
          {message && (
            <div className="rounded-md border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700 shadow-sm">
              {message}
            </div>
          )}

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(380px,0.85fr)]">
            <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
              <div className="flex flex-col gap-2 border-b border-zinc-200 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-ink">Normalized records</h2>
                  <p className="text-xs text-zinc-500">
                    {selectedCompany?.name || "Tenant"} | {failedRecords} failed | {warningRecords} warnings
                  </p>
                </div>
              </div>
              <div className="max-h-[620px] overflow-auto scrollbar-thin">
                <table className="w-full min-w-[760px] border-collapse text-left text-sm">
                  <thead className="sticky top-0 bg-zinc-50 text-xs uppercase text-zinc-500">
                    <tr>
                      <th className="px-4 py-3 font-semibold">Status</th>
                      <th className="px-4 py-3 font-semibold">Scope</th>
                      <th className="px-4 py-3 font-semibold">Source</th>
                      <th className="px-4 py-3 font-semibold">Activity</th>
                      <th className="px-4 py-3 font-semibold">Quantity</th>
                      <th className="px-4 py-3 font-semibold">CO2e</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {records.map((record) => (
                      <tr
                        className={`cursor-pointer hover:bg-teal-50 ${selectedRecord?.id === record.id ? "bg-teal-50" : ""}`}
                        key={record.id}
                        onClick={() => {
                          setSelectedRecord(record);
                          setEditing(false);
                        }}
                      >
                        <td className="px-4 py-3"><StatusBadge status={record.status} locked={record.locked} /></td>
                        <td className="px-4 py-3 font-medium text-ink">{record.scope.replace("_", " ")}</td>
                        <td className="px-4 py-3 text-zinc-600">{sourceLabels[record.source_type]}</td>
                        <td className="px-4 py-3 text-zinc-600">{record.activity_date || record.period_end || "Needs date"}</td>
                        <td className="px-4 py-3 text-zinc-600">{formatNumber(record.quantity)} {record.unit}</td>
                        <td className="px-4 py-3 text-zinc-600">{formatNumber(record.co2e_kg)} kg</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!records.length && (
                  <div className="p-8 text-center text-sm text-zinc-500">
                    No records match the current filters.
                  </div>
                )}
              </div>
            </section>

            <RecordDetail
              auditLogs={auditLogs}
              editDraft={editDraft}
              editing={editing}
              onApprove={() => reviewRecord("approve")}
              onEdit={() => startEdit(selectedRecord)}
              onReject={() => reviewRecord("reject")}
              onSave={saveEdit}
              record={selectedRecord}
              setEditDraft={setEditDraft}
              setEditing={setEditing}
            />
          </div>
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value, icon: Icon, tone = "reef" }) {
  const tones = {
    reef: "bg-teal-100 text-teal-800",
    amber: "bg-amber-100 text-amber-800",
    green: "bg-emerald-100 text-emerald-800",
    ink: "bg-slate-200 text-ink",
  };
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase text-zinc-500">{label}</p>
          <p className="mt-1 text-2xl font-semibold text-ink">{value}</p>
        </div>
        <span className={`grid h-10 w-10 place-items-center rounded-md ${tones[tone]}`}>
          <Icon className="h-5 w-5" />
        </span>
      </div>
    </div>
  );
}

function StatusBadge({ status, locked }) {
  const Icon = status === "failed" ? XCircle : status === "warning" ? AlertTriangle : status === "approved" ? CheckCircle2 : FileSearch;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold ring-1 ${statusStyles[status] || statusStyles.valid}`}>
      {locked ? <Lock className="h-3 w-3" /> : <Icon className="h-3 w-3" />}
      {status}
    </span>
  );
}

function RecordDetail({ record, editing, editDraft, setEditDraft, setEditing, onEdit, onSave, onApprove, onReject, auditLogs }) {
  if (!record) {
    return (
      <section className="rounded-lg border border-zinc-200 bg-white p-6 text-sm text-zinc-500 shadow-sm">
        Select a record to inspect raw data, normalized values, validation issues, and audit trail.
      </section>
    );
  }

  const relevantLogs = auditLogs.filter((log) => log.normalized_record === record.id || log.raw_record === record.raw_record?.id);

  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-zinc-200 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <StatusBadge status={record.status} locked={record.locked} />
            <span className="text-xs text-zinc-500">Batch #{record.batch}</span>
          </div>
          <h2 className="mt-2 text-base font-semibold text-ink">{record.category}</h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium hover:bg-zinc-50 disabled:opacity-50"
            disabled={record.locked}
            onClick={onEdit}
            type="button"
          >
            <Pencil className="h-4 w-4" />
            Edit
          </button>
          <button
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-rose-200 bg-white px-3 text-sm font-medium text-berry hover:bg-rose-50 disabled:opacity-50"
            disabled={record.locked}
            onClick={onReject}
            type="button"
          >
            <XCircle className="h-4 w-4" />
            Reject
          </button>
          <button
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-ink px-3 text-sm font-semibold text-white hover:bg-slate-800"
            onClick={onApprove}
            type="button"
          >
            <Lock className="h-4 w-4" />
            Approve
          </button>
        </div>
      </div>

      <div className="space-y-5 p-4">
        {editing ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {["activity_date", "period_start", "period_end", "facility_code", "category", "subcategory", "quantity", "unit", "co2e_kg"].map((field) => (
              <label className="text-xs font-medium uppercase text-zinc-500" key={field}>
                {field.replaceAll("_", " ")}
                <input
                  className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm normal-case text-ink"
                  value={editDraft[field] ?? ""}
                  onChange={(event) => setEditDraft((draft) => ({ ...draft, [field]: event.target.value }))}
                />
              </label>
            ))}
            <label className="flex items-center gap-2 text-sm text-zinc-700 sm:col-span-2">
              <input
                className="h-4 w-4 rounded border-zinc-300 text-reef"
                checked={Boolean(editDraft.resolve_issues)}
                onChange={(event) => setEditDraft((draft) => ({ ...draft, resolve_issues: event.target.checked }))}
                type="checkbox"
              />
              Mark open validation issues resolved
            </label>
            <div className="flex gap-2 sm:col-span-2">
              <button className="h-10 rounded-md bg-reef px-4 text-sm font-semibold text-white" onClick={onSave} type="button">
                Save changes
              </button>
              <button className="h-10 rounded-md border border-zinc-300 px-4 text-sm font-medium" onClick={() => setEditing(false)} type="button">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <Detail label="Scope" value={record.scope.replace("_", " ")} />
            <Detail label="Activity date" value={record.activity_date || record.period_end || "Missing"} />
            <Detail label="Facility or meter" value={record.facility_code || "Missing"} />
            <Detail label="Quantity" value={`${formatNumber(record.quantity)} ${record.unit}`} />
            <Detail label="CO2e" value={`${formatNumber(record.co2e_kg)} kg`} />
            <Detail label="Approved by" value={record.approved_by || "Not approved"} />
          </div>
        )}

        <Panel title="Validation issues">
          <div className="space-y-2">
            {record.validation_issues?.map((issue) => (
              <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3" key={issue.id}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-ink">{issue.rule_code}</span>
                  <StatusBadge status={issue.severity === "error" ? "failed" : "warning"} />
                </div>
                <p className="mt-1 text-sm text-zinc-600">{issue.message}</p>
                <p className="mt-1 text-xs text-zinc-500">{issue.field} | {issue.is_resolved ? "resolved" : "open"}</p>
              </div>
            ))}
            {!record.validation_issues?.length && <p className="text-sm text-zinc-500">No validation issues detected.</p>}
          </div>
        </Panel>

        <Panel title="Raw vs normalized">
          <div className="grid gap-3">
            <JsonBlock title="Raw source row" data={record.raw_record?.raw_data || {}} />
            <JsonBlock title="Normalized data" data={record.normalized_data || {}} />
          </div>
        </Panel>

        <Panel title="Audit trail">
          <div className="space-y-2">
            {relevantLogs.slice(0, 6).map((log) => (
              <div className="rounded-md border border-zinc-200 p-3 text-sm" key={log.id}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-ink">{log.action}</span>
                  <span className="text-xs text-zinc-500">{new Date(log.created_at).toLocaleString()}</span>
                </div>
                <p className="mt-1 text-zinc-600">{log.actor || "system"}</p>
              </div>
            ))}
            {!relevantLogs.length && <p className="text-sm text-zinc-500">No audit events loaded for this row.</p>}
          </div>
        </Panel>
      </div>
    </section>
  );
}

function Detail({ label, value }) {
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
      <p className="text-xs font-medium uppercase text-zinc-500">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-ink">{title}</h3>
      {children}
    </div>
  );
}

function JsonBlock({ title, data }) {
  return (
    <div className="rounded-md border border-zinc-200 bg-[#111827] p-3">
      <p className="mb-2 text-xs font-semibold uppercase text-zinc-300">{title}</p>
      <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words text-xs leading-relaxed text-zinc-100">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

async function apiGet(path) {
  return apiRequest(path, { method: "GET" });
}

async function apiPost(path, body, isForm = false) {
  return apiRequest(path, {
    method: "POST",
    body: isForm ? body : JSON.stringify(body),
    headers: isForm ? undefined : { "Content-Type": "application/json" },
  });
}

async function apiPatch(path, body) {
  return apiRequest(path, {
    method: "PATCH",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

async function apiRequest(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(data?.detail || JSON.stringify(data) || `Request failed with ${response.status}`);
  }
  return data;
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "0";
  const number = Number(value);
  if (Number.isNaN(number)) return value;
  return new Intl.NumberFormat("en", { maximumFractionDigits: 2 }).format(number);
}

export default App;
