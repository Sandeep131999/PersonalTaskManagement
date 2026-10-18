import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowDownToLine, ArrowLeft, ArrowRight, CalendarDays, Check, CheckCircle2,
  Circle, Clock3, LayoutDashboard, ListTodo, LoaderCircle, Pause,
  Plus, Search, Settings2, Trash2, X,
} from "lucide-react";
import { api } from "./api.js";

const pad = (value) => String(value).padStart(2, "0");
const localDate = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
const today = localDate(new Date());
const dateLabel = (value, options = { month: "short", day: "numeric", year: "numeric" }) =>
  new Date(`${value}T12:00:00`).toLocaleDateString(undefined, options);
const startOfMonth = (date) => new Date(date.getFullYear(), date.getMonth(), 1);

function App() {
  const [summary, setSummary] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [month, setMonth] = useState(startOfMonth(new Date()));
  const [selectedDate, setSelectedDate] = useState(today);
  const [section, setSection] = useState("overview");
  const [modal, setModal] = useState(null);
  const [report, setReport] = useState([]);
  const [reportStart, setReportStart] = useState(today);
  const [reportEnd, setReportEnd] = useState(today);
  const [reportStatus, setReportStatus] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [token, setToken] = useState(sessionStorage.getItem("task-api-token") || "");
  const [tokenVerified, setTokenVerified] = useState(false);
  const [tokenError, setTokenError] = useState("");

  useEffect(() => {
    if (token) {
      api.checkAuth(token)
        .then(() => setTokenVerified(true))
        .catch(() => setTokenVerified(false));
    }
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    const first = localDate(new Date(month.getFullYear(), month.getMonth(), 1));
    const last = localDate(new Date(month.getFullYear(), month.getMonth() + 1, 0));
    try {
      const [nextSummary, nextTasks] = await Promise.all([api.summary(), api.tasks(first, last)]);
      setSummary(nextSummary);
      setTasks(nextTasks);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => { refresh(); }, [refresh]);

  const tasksByDate = useMemo(() => {
    const result = new Map();
    for (const task of tasks) result.set(task.task_date, [...(result.get(task.task_date) || []), task]);
    return result;
  }, [tasks]);

  const calendarDays = useMemo(() => {
    const firstDay = startOfMonth(month);
    const start = new Date(firstDay);
    start.setDate(1 - firstDay.getDay());
    return Array.from({ length: 42 }, (_, index) => {
      const day = new Date(start);
      day.setDate(start.getDate() + index);
      return day;
    });
  }, [month]);

  const selectedTasks = (tasksByDate.get(selectedDate) || []).filter((task) =>
    task.title.toLowerCase().includes(search.toLowerCase()),
  );

  async function runReport(event) {
    event.preventDefault();
    setError("");
    try {
      setReport(await api.report(reportStart, reportEnd, reportStatus));
    } catch (err) {
      setError(err.message);
    }
  }

  function exportCsv() {
    const columns = ["task_id", "title", "description", "task_date", "priority", "status", "completed_at"];
    const lines = [columns.join(","), ...report.map((task) => columns.map((key) =>
      `"${String(task[key] ?? "").replaceAll('"', '""')}"`,
    ).join(","))];
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    link.download = `tasks-${reportStart}-${reportEnd}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async function changeStatus(task, status) {
    if (task.status === status) return;
    setBusy(true);
    try {
      await api.setStatus(task.task_id, status);
      await refresh();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function removeTask(task) {
    if (!window.confirm(`Delete "${task.title}"?`)) return;
    setBusy(true);
    try {
      await api.remove(task.task_id);
      await refresh();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function saveTask(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      title: form.get("title").trim(),
      description: form.get("description").trim(),
      task_date: form.get("task_date"),
      priority: form.get("priority"),
    };
    setBusy(true);
    setError("");
    try {
      if (modal.task) await api.update(modal.task.task_id, payload);
      else await api.create(payload);
      setSelectedDate(payload.task_date);
      setMonth(startOfMonth(new Date(`${payload.task_date}T12:00:00`)));
      setModal(null);
      await refresh();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function saveToken(event) {
    event.preventDefault();
    const value = new FormData(event.currentTarget).get("token").trim();
    setTokenError("");
    if (value) {
      try {
        await api.checkAuth(value);
      } catch (err) {
        setTokenVerified(false);
        setTokenError(err.message);
        return;
      }
    }
    if (value) sessionStorage.setItem("task-api-token", value);
    else sessionStorage.removeItem("task-api-token");
    setToken(value);
    setTokenVerified(Boolean(value));
    setModal(null);
    await refresh();
  }

  const tasksForPanel = section === "overview"
    ? (summary?.today_tasks || [])
    : section === "calendar"
      ? selectedTasks
      : [];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={() => setSection("overview")}>
          <span className="brand-mark"><Check size={20} strokeWidth={3} /></span>
          <span>daymark<span className="brand-dot">.</span></span>
        </a>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="nav-list">
          <button className={`nav-item ${section === "overview" ? "active" : ""}`} onClick={() => setSection("overview")}><LayoutDashboard size={18} />Overview</button>
          <button className={`nav-item ${section === "calendar" ? "active" : ""}`} onClick={() => setSection("calendar")}><CalendarDays size={18} />Calendar</button>
          <button className={`nav-item ${section === "reports" ? "active" : ""}`} onClick={() => setSection("reports")}><ListTodo size={18} />Reports</button>
        </nav>
        <div className="sidebar-bottom">
          <div className="storage-note"><span className="status-dot" />Google Sheets storage</div>
          <button className="profile" onClick={() => setModal({ token: true })}>
            <span className="avatar">Y</span><span className="profile-name">Your workspace<small>{tokenVerified ? "Token verified" : token ? "Token not verified" : "Personal account"}</small></span><Settings2 size={17} />
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> <strong>{section === "overview" ? "Overview" : section === "calendar" ? "Calendar" : "Reports"}</strong></div>
          <div className="top-actions"><span className="date-chip"><CalendarDays size={15} />{dateLabel(today, { weekday: "short", month: "short", day: "numeric" })}</span><button className="primary-button small" onClick={() => setModal({ task: null })}><Plus size={17} />New task</button></div>
        </header>

        <div className="page-content">
          <div className="page-heading">
            <div><div className="eyebrow">{dateLabel(today, { weekday: "long", month: "long", day: "numeric" }).toUpperCase()}</div><h1>{section === "overview" ? "Your day, at a glance." : section === "calendar" ? "Plan your time." : "Task report."}</h1><p>{section === "overview" ? "A little progress each day adds up." : section === "calendar" ? "Keep your schedule clear and achievable." : "Review what you have planned and completed."}</p></div>
            {section === "calendar" && <button className="primary-button" onClick={() => setModal({ task: null })}><Plus size={17} />Add a task</button>}
          </div>

          {error && <div className="error-banner" role="alert"><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss error"><X size={16} /></button></div>}

          {section === "overview" && <>
            <section className="stats-grid">
              <StatCard title="All tasks" value={summary?.total ?? "—"} icon={<ListTodo />} tint="lavender" note="In your workspace" />
              <StatCard title="To do" value={summary?.pending ?? "—"} icon={<Circle />} tint="blue" note="Ready when you are" />
              <StatCard title="On hold" value={summary?.on_hold ?? "—"} icon={<Pause />} tint="amber" note="Paused for now" />
              <StatCard title="Completed" value={summary?.completed ?? "—"} icon={<CheckCircle2 />} tint="green" note="One step at a time" />
              <StatCard title="Overdue" value={summary?.overdue ?? "—"} icon={<Clock3 />} tint="amber" note={summary?.overdue ? "Needs a new plan" : "You're all caught up"} />
            </section>
            <section className="overview-grid">
              <article className="card today-card">
                <div className="card-heading"><div><div className="section-kicker">TODAY</div><h2>Today's focus</h2></div><button className="text-button" onClick={() => { setSection("calendar"); setSelectedDate(today); }}>View calendar <ArrowRight size={15} /></button></div>
                {loading ? <Loading /> : <TaskList tasks={summary?.today_tasks || []} onStatusChange={changeStatus} onEdit={(task) => setModal({ task })} onDelete={removeTask} busy={busy} emptyTitle="A clear day ahead" emptyText="Add a task to give your day a little direction." />}
              </article>
              <article className="card week-card">
                <div className="card-heading"><div><div className="section-kicker">UP NEXT</div><h2>Coming up</h2></div><span className="count-pill">{summary?.upcoming ?? 0} tasks</span></div>
                <div className="mini-agenda">{(summary?.upcoming_tasks || []).slice(0, 5).map((task) => <button key={task.task_id} className="agenda-row" onClick={() => { setSelectedDate(task.task_date); setMonth(startOfMonth(new Date(`${task.task_date}T12:00:00`))); setSection("calendar"); }}><span className="agenda-date">{dateLabel(task.task_date, { month: "short", day: "numeric" })}</span><span className="agenda-title">{task.title}</span><span className={`priority-dot ${task.priority.toLowerCase()}`} /></button>)}
                  {!loading && !summary?.upcoming_tasks?.length && <EmptySmall text="No upcoming tasks yet." />}
                  {summary?.overdue_tasks?.length > 0 && <div className="overdue-note"><span className="priority-dot high" />{summary.overdue} overdue {summary.overdue === 1 ? "task" : "tasks"} need attention</div>}
                </div>
              </article>
            </section>
          </>}

          {section === "calendar" && <section className="calendar-layout">
            <article className="card calendar-card">
              <div className="calendar-toolbar"><button className="icon-button" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} aria-label="Previous month"><ArrowLeft size={17} /></button><h2>{month.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</h2><button className="icon-button" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} aria-label="Next month"><ArrowRight size={17} /></button><button className="today-button" onClick={() => { setMonth(startOfMonth(new Date())); setSelectedDate(today); }}>Today</button></div>
              <div className="calendar-grid weekday-row">{["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <div key={day}>{day}</div>)}</div>
              <div className="calendar-grid days-grid">{calendarDays.map((day) => {
                const key = localDate(day);
                const sameMonth = day.getMonth() === month.getMonth();
                const dayTasks = tasksByDate.get(key) || [];
                return <button key={key} className={`day-cell ${sameMonth ? "" : "muted"} ${key === today ? "is-today" : ""} ${key === selectedDate ? "selected" : ""}`} onClick={() => { setSelectedDate(key); if (!sameMonth) setMonth(startOfMonth(day)); }}>
                  <span className="day-number">{day.getDate()}</span>
                  <span className="day-markers">{dayTasks.slice(0, 3).map((task) => <i key={task.task_id} className={`marker ${task.status === "COMPLETED" ? "done" : task.status === "ON_HOLD" ? "hold" : task.priority.toLowerCase()}`} />)}</span>
                  {dayTasks.length > 0 && <span className="day-count">{dayTasks.length} {dayTasks.length === 1 ? "task" : "tasks"}</span>}
                </button>;
              })}</div>
              <div className="calendar-legend"><span><i className="marker high" />High priority</span><span><i className="marker medium" />Medium priority</span><span><i className="marker hold" />On hold</span><span><i className="marker done" />Completed</span></div>
            </article>
            <article className="card selected-day-card">
              <div className="card-heading"><div><div className="section-kicker">SELECTED DAY</div><h2>{dateLabel(selectedDate, { weekday: "long", month: "long", day: "numeric" })}</h2></div><button className="icon-button" aria-label="Add task" disabled={selectedDate < today} onClick={() => setModal({ task: null })}><Plus size={18} /></button></div>
              {selectedDate < today && <p className="past-note">Past dates are read-only for new tasks.</p>}
              <label className="search-field"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find a task" /></label>
              {loading ? <Loading /> : <TaskList tasks={selectedTasks} onStatusChange={changeStatus} onEdit={(task) => setModal({ task })} onDelete={removeTask} busy={busy} emptyTitle="Nothing planned" emptyText="This date is free. Add a task whenever you're ready." />}
            </article>
          </section>}

          {section === "reports" && <section className="card report-card">
            <div className="card-heading report-heading"><div><div className="section-kicker">YOUR ACTIVITY</div><h2>Tasks by scheduled date</h2><p>Choose a date range to see tasks planned during that period.</p></div></div>
            <form className="report-filters" onSubmit={runReport}><label>From<input type="date" value={reportStart} onChange={(e) => setReportStart(e.target.value)} required /></label><label>To<input type="date" value={reportEnd} onChange={(e) => setReportEnd(e.target.value)} required /></label><label>Status<select value={reportStatus} onChange={(e) => setReportStatus(e.target.value)}><option value="">All statuses</option><option value="PENDING">Pending</option><option value="ON_HOLD">On hold</option><option value="COMPLETED">Completed</option></select></label><button className="primary-button" type="submit">Run report <ArrowRight size={16} /></button></form>
            <div className="report-results"><div className="report-result-top"><div><strong>{report.length}</strong> {report.length === 1 ? "task" : "tasks"} found{report.length > 0 && <span className="muted-text"> · {dateLabel(reportStart)} — {dateLabel(reportEnd)}</span>}</div><button className="secondary-button" onClick={exportCsv} disabled={!report.length}><ArrowDownToLine size={16} />Export CSV</button></div>
              {report.length ? <TaskList tasks={report} onStatusChange={changeStatus} onEdit={(task) => setModal({ task })} onDelete={removeTask} busy={busy} emptyTitle="" emptyText="" /> : <EmptyState title="No report results yet" text="Select a date range and run your report." />}
            </div>
          </section>}
        </div>
      </main>

      {modal?.task !== undefined && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setModal(null); }}><form className="task-modal" onSubmit={saveTask}>
        <div className="modal-heading"><div><div className="section-kicker">{modal.task ? "TASK DETAILS" : "MAKE A PLAN"}</div><h2>{modal.task ? "Edit task" : "Create a task"}</h2></div><button type="button" className="icon-button" onClick={() => setModal(null)} aria-label="Close"><X size={18} /></button></div>
        <label>Task title<input name="title" defaultValue={modal.task?.title || ""} placeholder="e.g. Review project proposal" maxLength="160" required autoFocus /></label>
        <label>Description <span className="optional">Optional</span><textarea name="description" defaultValue={modal.task?.description || ""} placeholder="Add a few details..." rows="3" maxLength="2000" /></label>
        <div className="form-row"><label>Date<input name="task_date" type="date" min={modal.task?.task_date < today ? modal.task.task_date : today} defaultValue={modal.task?.task_date || (selectedDate >= today ? selectedDate : today)} required /></label><label>Priority<select name="priority" defaultValue={modal.task?.priority || "MEDIUM"}><option value="LOW">Low</option><option value="MEDIUM">Medium</option><option value="HIGH">High</option></select></label></div>
        <div className="modal-actions"><button type="button" className="secondary-button" onClick={() => setModal(null)}>Cancel</button><button className="primary-button" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}{modal.task ? "Save changes" : "Create task"}</button></div>
      </form></div>}

      {modal?.token && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setModal(null); }}><form className="task-modal token-modal" onSubmit={saveToken}><div className="modal-heading"><div><div className="section-kicker">CONNECTION</div><h2>API access</h2></div><button type="button" className="icon-button" onClick={() => setModal(null)} aria-label="Close"><X size={18} /></button></div><p className="token-help">Enter your API token without the word “Bearer”. We’ll verify it before saving. It stays in this browser tab.</p><label>Access token<input name="token" type="password" defaultValue={token} placeholder="Paste your API token" autoComplete="off" /></label>{tokenError && <div className="token-error" role="alert">{tokenError}</div>}<div className="modal-actions"><button type="button" className="secondary-button" onClick={() => setModal(null)}>Cancel</button><button className="primary-button"><Check size={16} />Verify &amp; Save</button></div></form></div>}
    </div>
  );
}

function StatCard({ title, value, icon, tint, note }) {
  return <article className="card stat-card"><div className={`stat-icon ${tint}`}>{icon}</div><div className="stat-title">{title}</div><div className="stat-value">{value}</div><div className="stat-note">{note}</div></article>;
}

function TaskList({ tasks, onStatusChange, onEdit, onDelete, busy }) {
  if (!tasks.length) return <EmptyState title="A clear day ahead" text="No tasks match this view." />;
  return <div className="task-list">{tasks.map((task) => <article className={`task-row ${task.status === "COMPLETED" ? "completed" : ""} ${task.status === "ON_HOLD" ? "on-hold" : ""}`} key={task.task_id}>
    <button className="task-main" onClick={() => onEdit(task)}><span className="task-title">{task.title}</span><span className="task-meta">{task.description || dateLabel(task.task_date)}<span className={`priority-label ${task.priority.toLowerCase()}`}>{task.priority.toLowerCase()}</span></span></button>
    <select className={`task-status-select ${task.status.toLowerCase()}`} value={task.status} onChange={(event) => onStatusChange(task, event.target.value)} disabled={busy} aria-label={`Status for ${task.title}`}><option value="PENDING">Pending</option><option value="ON_HOLD">On hold</option><option value="COMPLETED">Completed</option></select>
    <button className="icon-button delete-button" onClick={() => onDelete(task)} disabled={busy} aria-label={`Delete ${task.title}`}><Trash2 size={16} /></button>
  </article>)}</div>;
}

function EmptyState({ title, text }) {
  return <div className="empty-state"><span className="empty-icon"><CalendarDays size={20} /></span><strong>{title}</strong><p>{text}</p></div>;
}
function EmptySmall({ text }) { return <div className="empty-small">{text}</div>; }
function Loading() { return <div className="loading-state"><LoaderCircle className="spin" size={19} />Loading tasks...</div>; }

export default App;
