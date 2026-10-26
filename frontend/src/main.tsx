import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Bell,
  Boxes,
  Cable,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  FileText,
  History,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Moon,
  Plus,
  Radio,
  RefreshCw,
  Route,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sun,
  Users,
  X,
} from "lucide-react";
import { api, Row } from "./api";
import "./styles.css";

const client = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});
let displayTimezone: string | undefined;
const date = (value: number) =>
  value
    ? new Date(value * 1000).toLocaleString(undefined, {
        timeZone: displayTimezone,
      })
    : "—";
const titleCase = (s: string) =>
  s.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
const sampleEvent = {
  environment: "production",
  severity: "CRITICAL",
  title: "Database replication lag",
  message: "Replication lag exceeded the threshold.",
  category: "database",
  tags: ["postgresql"],
  metadata: { lag_seconds: 120 },
};

export function Badge({ value }: { value: string }) {
  return (
    <span className={"badge " + value?.toLowerCase()}>
      {value?.replaceAll("_", " ")}
    </span>
  );
}
function Field({
  label,
  value,
  onChange,
  type = "text",
  required = false,
  help,
}: {
  label: string;
  value: any;
  onChange: (v: any) => void;
  type?: string;
  required?: boolean;
  help?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {type === "textarea" ? (
        <textarea
          aria-label={label}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          required={required}
        />
      ) : type === "checkbox" ? (
        <input
          aria-label={label}
          type="checkbox"
          checked={!!value}
          onChange={(e) => onChange(e.target.checked)}
        />
      ) : (
        <input
          aria-label={label}
          type={type}
          value={value ?? ""}
          onChange={(e) =>
            onChange(
              type === "number" ? Number(e.target.value) : e.target.value,
            )
          }
          required={required}
        />
      )}{" "}
      {help && <small>{help}</small>}
    </label>
  );
}
function JsonField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: any;
  onChange: (v: any) => void;
}) {
  const [text, setText] = useState(JSON.stringify(value, null, 2));
  const [error, setError] = useState("");
  useEffect(
    () => setText(JSON.stringify(value, null, 2)),
    [JSON.stringify(value)],
  );
  return (
    <label className="field">
      <span>{label}</span>
      <textarea
        className="code"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          try {
            onChange(JSON.parse(e.target.value));
            setError("");
            e.target.setCustomValidity("");
          } catch {
            setError("Enter valid JSON");
            e.target.setCustomValidity("Enter valid JSON");
          }
        }}
      />
      {error && <small className="error">{error}</small>}
    </label>
  );
}
function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const controls = () =>
      Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled),input:not(:disabled),textarea,select,a[href]",
        ) || [],
      ).filter((el) => el.getClientRects().length > 0);
    controls()[0]?.focus();
    const listener = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") {
        const items = controls(),
          first = items[0],
          last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    window.addEventListener("keydown", listener);
    return () => {
      window.removeEventListener("keydown", listener);
      previous?.focus();
    };
  }, []);
  return (
    <div className="overlay" onClick={onClose}>
      <section
        ref={dialogRef}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="section-head">
          <h2>{title}</h2>
          <button className="icon" aria-label="Close dialog" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
function ErrorBox({ error }: { error: unknown }) {
  return error ? (
    <div className="error-box" role="alert">
      {error instanceof Error ? error.message : String(error)}
    </div>
  ) : null;
}
function Brand() {
  return (
    <div className="brand">
      <span className="brand-icon">
        <Bell size={22} />
      </span>
      <span>
        NotiDeck<small>CONSOLE</small>
      </span>
    </div>
  );
}

export function Setup({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0),
    [token, setToken] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [tested, setTested] = useState(false);
  const [value, setValue] = useState<Row>({
    database: { engine: "sqlite" },
    username: "",
    full_name: "",
    email: "",
    password: "",
    confirm_password: "",
    app_name: "NotiDeck",
    base_url: location.origin,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    retention_days: 90,
    max_attempts: 5,
    retry_base: 10,
  });
  const set = (key: string, v: any) => setValue({ ...value, [key]: v });
  const db = (key: string, v: any) => {
    setValue({ ...value, database: { ...value.database, [key]: v } });
    setTested(false);
  };
  const steps = [
    "Welcome",
    "Database",
    "Administrator",
    "Application",
    "Finish",
  ];
  async function next(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (step === 0) {
      const cleanToken = token.trim();
      if (!cleanToken) {
        setError("Enter the bootstrap token from this installation.");
        return;
      }
      if (cleanToken.startsWith("nd_")) {
        setError(
          "That is a source API key. Setup requires the bootstrap.token file from the running installation.",
        );
        return;
      }
      setBusy(true);
      try {
        await api("/setup/verify", "POST", {}, cleanToken);
        setToken(cleanToken);
        setTested(false);
        setStep(1);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
      return;
    }
    if (step === 1 && !tested) {
      setError("Test the database connection before continuing.");
      return;
    }
    if (step === 2 && value.password !== value.confirm_password) {
      setError("Passwords do not match.");
      return;
    }
    if (step < 4) {
      setStep(step + 1);
      return;
    }
    setBusy(true);
    try {
      await api("/setup", "POST", value, token);
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="setup-shell">
      <aside>
        <Brand />
        <div>
          <span className="eyebrow">YOUR NOTIFICATIONS, CONNECTED</span>
          <h1>
            One Platform.
            <br />
            Every Notification.
          </h1>
          <p>
            A clear path from the events that matter to the people who need to
            know.
          </p>
        </div>
        <small>Self-hosted. Open source. Yours.</small>
      </aside>
      <main>
        <div className="setup-steps">
          {steps.map((s, i) => (
            <span key={s} className={i === step ? "active" : ""}>
              {i < step ? <Check size={14} /> : i + 1} {s}
            </span>
          ))}
        </div>
        <form onSubmit={next}>
          <span className="eyebrow">STEP {step + 1} OF 5</span>
          <h1>
            {
              [
                "Welcome to NotiDeck",
                "Connect your database",
                "Create your administrator",
                "Make it your own",
                "Ready to connect",
              ][step]
            }
          </h1>
          <p className="muted">
            {
              [
                "Let’s set up your notification workspace. Version 0.1.0rc2.",
                "Your notifications and delivery queue live here.",
                "No default credentials. This account will manage your workspace.",
                "Choose the defaults for your installation.",
                "Review your choices, then initialize your workspace.",
              ][step]
            }
          </p>
          {step === 0 && (
            <>
              <div className="callout">
                <ShieldCheck />
                <div>
                  <strong>Protected local setup</strong>
                  <p>
                    Read the bootstrap.token file at the private path printed in
                    your server terminal, then paste its contents below. The
                    token is never printed in logs.
                  </p>
                </div>
              </div>
              <label className="field">
                <span>Bootstrap token</span>
                <input
                  aria-label="Bootstrap token"
                  name="notideck-bootstrap-token"
                  type="password"
                  autoComplete="off"
                  autoCapitalize="none"
                  spellCheck={false}
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  required
                />
                <small>
                  This is not your source API key or administrator password. For
                  Docker, use /data/bootstrap.token in the web container.
                </small>
              </label>
            </>
          )}
          {step === 1 && (
            <>
              <label className="field">
                <span>Database engine</span>
                <select
                  value={value.database.engine}
                  onChange={(e) => {
                    setValue({
                      ...value,
                      database: e.target.value === "postgresql" ? {engine: "postgresql", tls_enabled: true, tls: {sslmode: "verify-full"}} : { engine: e.target.value },
                    });
                    setTested(false);
                  }}
                >
                  {["sqlite", "postgresql", "mysql", "oracle"].map((x) => (
                    <option key={x} value={x}>
                      {x === "sqlite"
                        ? "SQLite · simple local installation"
                        : titleCase(x)}
                    </option>
                  ))}
                </select>
              </label>
              {value.database.engine === "sqlite" ? (
                <Field
                  label="Database file (optional)"
                  value={value.database.path}
                  onChange={(v) => db("path", v || undefined)}
                  help="Leave blank to use the secure application data directory."
                />
              ) : (
                <>
                  <div className="form-grid">
                    {[
                      "host",
                      "port",
                      "database",
                      "username",
                      "password",
                      ...(value.database.engine === "postgresql"
                        ? ["schema_name"]
                        : []),
                    ].map((k) => (
                      <Field
                        key={k}
                        label={
                          k === "database"
                            ? "Database / Oracle service name"
                            : titleCase(k)
                        }
                        value={value.database[k]}
                        onChange={(v) => db(k, v)}
                        type={
                          k === "password"
                            ? "password"
                            : k === "port"
                              ? "number"
                              : "text"
                        }
                        required={!["port", "schema_name"].includes(k)}
                      />
                    ))}
                  </div>
                  {value.database.engine === "postgresql" && <>
                    <Field label="Use TLS/SSL" type="checkbox" value={value.database.tls_enabled !== false}
                      onChange={(enabled) => {setValue({...value, database:{...value.database,tls_enabled:enabled,tls:enabled?{sslmode:"verify-full"}:{}}});setTested(false);}}
                      help="Uncheck for a PostgreSQL server that does not use TLS. Enabled connections never silently fall back to plaintext." />
                    {value.database.tls_enabled !== false && <label className="field"><span>TLS verification</span>
                      <select value={value.database.tls?.sslmode || "verify-full"} onChange={e=>db("tls",{...value.database.tls,sslmode:e.target.value})}>
                        <option value="verify-full">Verify certificate and hostname (recommended)</option>
                        <option value="verify-ca">Verify certificate authority</option>
                        <option value="require">Encryption only (no hostname verification)</option>
                      </select></label>}
                  </>}
                  {(value.database.engine !== "postgresql" || value.database.tls_enabled !== false) && <JsonField
                    label="Advanced TLS parameters (optional)"
                    value={value.database.tls || {}}
                    onChange={(v) => db("tls", v)}
                  />}
                </>
              )}
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api("/setup/test", "POST", value.database, token);
                    setTested(true);
                    setError("");
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {tested ? <Check size={16} /> : <Cable size={16} />}{" "}
                {tested ? "Connection verified" : "Test connection"}
              </button>
            </>
          )}
          {step === 2 && (
            <div className="form-grid">
              {[
                "full_name",
                "username",
                "email",
                "password",
                "confirm_password",
              ].map((k) => (
                <Field
                  key={k}
                  label={titleCase(k)}
                  value={value[k]}
                  onChange={(v) => set(k, v)}
                  type={
                    k.includes("password")
                      ? "password"
                      : k === "email"
                        ? "email"
                        : "text"
                  }
                  required
                  help={
                    k === "password"
                      ? "At least 12 characters, including letters and nonletters."
                      : undefined
                  }
                />
              ))}
            </div>
          )}
          {step === 3 && (
            <div className="form-grid">
              {[
                "app_name",
                "base_url",
                "timezone",
                "retention_days",
                "max_attempts",
                "retry_base",
              ].map((k) => (
                <Field
                  key={k}
                  label={titleCase(k)}
                  value={value[k]}
                  onChange={(v) => set(k, v)}
                  type={typeof value[k] === "number" ? "number" : "text"}
                  required
                />
              ))}
            </div>
          )}
          {step === 4 && (
            <div className="review-list">
              <p>
                <span>Workspace</span>
                <strong>{value.app_name}</strong>
              </p>
              <p>
                <span>Database</span>
                <strong>{value.database.engine}</strong>
              </p>
              <p>
                <span>Administrator</span>
                <strong>{value.username}</strong>
              </p>
              <p>
                <span>Retention</span>
                <strong>{value.retention_days} days</strong>
              </p>
              <p>
                Initialization applies migrations and creates your account.
                Existing installations cannot be overwritten.
              </p>
            </div>
          )}
          <ErrorBox error={error} />
          <div className="form-footer">
            {step > 0 && (
              <button
                type="button"
                className="secondary"
                onClick={() => setStep(step - 1)}
              >
                Back
              </button>
            )}
            <button disabled={busy}>
              {busy
                ? "Connecting…"
                : step === 4
                  ? "Initialize workspace"
                  : "Continue"}
              <ArrowRight size={16} />
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
function Login({ onDone }: { onDone: () => void }) {
  const [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <div className="login">
      <form
        className="card"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await api("/auth/login", "POST", { username, password });
            onDone();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Brand />
        <h1>Welcome back.</h1>
        <p className="muted">Sign in to your notification workspace.</p>
        <Field
          label="Username"
          value={username}
          onChange={setUsername}
          required
        />
        <Field
          label="Password"
          value={password}
          type="password"
          onChange={setPassword}
          required
        />
        <ErrorBox error={error} />
        <button disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
          <ArrowRight size={16} />
        </button>
      </form>
    </div>
  );
}
const navigation = [
  ["Overview", LayoutDashboard],
  ["Notifications", Bell],
  ["Queue", Boxes],
  ["Channels", Cable],
  ["Routing rules", Route],
  ["Sources", Radio],
  ["Recipients", Users],
  ["Groups", Users],
  ["Templates", FileText],
  ["Users", ShieldCheck],
  ["Audit logs", History],
  ["Settings", Settings],
] as const;
const endpoints: Record<string, string> = {
  Notifications: "/notifications",
  Queue: "/queue",
  Channels: "/channels",
  "Routing rules": "/routes",
  Sources: "/sources",
  Recipients: "/resources/recipients",
  Groups: "/resources/groups",
  Templates: "/resources/templates",
  Users: "/users",
  "Audit logs": "/audits",
};
const descriptions: Record<string, string> = {
  Overview: "A live view of your notification workspace.",
  Notifications: "Every event, every destination, one clear history.",
  Queue: "Monitor dispatch, recover failures, and control your backlog.",
  Channels: "Connect the services your team already uses.",
  "Routing rules": "Send the right events to the right destinations.",
  Sources: "Secure entry points for your applications and services.",
  Recipients: "Reusable delivery addresses for your team.",
  Groups: "Bring recipients together for shared routing.",
  Templates: "Consistent messages, with safe variable interpolation.",
  Users: "Manage workspace access and permissions.",
  "Audit logs": "A record of significant administrative activity.",
  Settings: "Configure your workspace and delivery defaults.",
};
const defaults: Record<string, Row> = {
  Channels: {
    name: "",
    provider: "webhook",
    enabled: true,
    rate_per_minute: 60,
    config: { url: "" },
  },
  "Routing rules": {
    name: "",
    description: "",
    enabled: true,
    priority: 100,
    conditions: [
      { field: "environment", op: "equals", value: "production" },
      { field: "severity", op: "gte", value: "ERROR" },
    ],
    targets: [],
    stop: false,
    template_id: null,
  },
  Sources: {
    name: "",
    description: "",
    environment: "production",
    enabled: true,
    rate_limit: 120,
    networks: [],
    tags: [],
  },
  Recipients: { name: "", addresses: { email: "" } },
  Groups: { name: "", members: [] },
  Templates: {
    name: "",
    title: "{{ notification.title }}",
    text: "{{ notification.message }}",
    html: "",
  },
  Users: {
    username: "",
    full_name: "",
    email: "",
    password: "",
    role: "VIEWER",
    enabled: true,
  },
};

function Editor({
  page,
  initial,
  onClose,
  onSave,
}: {
  page: string;
  initial?: Row;
  onClose: () => void;
  onSave: () => void;
}) {
  const keys = Object.keys(defaults[page]);
  const [value, setValue] = useState<Row>(
    initial
      ? Object.fromEntries(
          keys.map((k) => [k, initial[k] ?? defaults[page][k]]),
        )
      : structuredClone(defaults[page]),
  );
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: () => api("/providers"),
  });
  const channels = useQuery({
    queryKey: ["channel-options"],
    queryFn: () => api("/channels?limit=100"),
    enabled: page === "Routing rules",
  });
  const templates = useQuery({
    queryKey: ["template-options"],
    queryFn: () => api("/resources/templates?limit=100"),
    enabled: page === "Routing rules",
  });
  const recipients = useQuery({
    queryKey: ["recipient-options"],
    queryFn: () => api("/resources/recipients?limit=100"),
    enabled: page === "Groups",
  });
  const set = (k: string, v: any) => setValue((old) => ({ ...old, [k]: v }));
  return (
    <Modal
      title={(initial?.id ? "Edit " : "Create ") + page.toLowerCase()}
      onClose={onClose}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            const body = { ...value };
            if (page === "Users" && !body.password) delete body.password;
            await api(
              endpoints[page] + (initial?.id ? "/" + initial.id : ""),
              initial?.id ? "PATCH" : "POST",
              body,
            );
            onSave();
            onClose();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {keys
          .filter(
            (k) => !["config", "targets", "conditions", "members"].includes(k),
          )
          .map((k) => {
            if (k === "provider" || k === "role")
              return (
                <label className="field" key={k}>
                  <span>{titleCase(k)}</span>
                  <select
                    value={value[k]}
                    onChange={(e) => {
                      set(k, e.target.value);
                      if (k === "provider") set("config", {});
                    }}
                  >
                    {(k === "role"
                      ? ["ADMIN", "OPERATOR", "VIEWER"]
                      : (providers.data || []).map((p: Row) => p.id)
                    ).map((x: string) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </label>
              );
            if (k === "template_id")
              return (
                <label className="field" key={k}>
                  <span>Notification template</span>
                  <select
                    value={value[k] || ""}
                    onChange={(e) => set(k, e.target.value || null)}
                  >
                    <option value="">Original event message</option>
                    {value[k] &&
                      !templates.data?.items.some(
                        (t: Row) => t.id === value[k],
                      ) && (
                        <option value={value[k]}>
                          Current template ({value[k]})
                        </option>
                      )}
                    {(templates.data?.items || []).map((t: Row) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                  <ErrorBox error={templates.error} />
                </label>
              );
            if (typeof value[k] === "object" && value[k] !== null)
              return (
                <JsonField
                  key={k}
                  label={titleCase(k)}
                  value={value[k]}
                  onChange={(v) => set(k, v)}
                />
              );
            return (
              <Field
                key={k}
                label={titleCase(k)}
                value={value[k]}
                onChange={(v) => set(k, v)}
                type={
                  typeof value[k] === "boolean"
                    ? "checkbox"
                    : typeof value[k] === "number"
                      ? "number"
                      : k === "password"
                        ? "password"
                        : ["description", "text", "html"].includes(k)
                          ? "textarea"
                          : "text"
                }
                required={["name", "username", "full_name", "email"].includes(
                  k,
                )}
              />
            );
          })}
        {page === "Channels" && (
          <>
            <div className="divider">Provider configuration</div>
            {Object.entries(
              providers.data?.find((p: Row) => p.id === value.provider)?.schema
                .properties || {},
            ).map(([key, meta]: [string, any]) =>
              ["headers", "components", "payload"].includes(key) ? (
                <JsonField
                  key={value.provider + key}
                  label={titleCase(key)}
                  value={value.config[key] || (key === "components" ? [] : {})}
                  onChange={(v) => set("config", { ...value.config, [key]: v })}
                />
              ) : (
                <Field
                  key={key}
                  label={titleCase(key)}
                  value={value.config[key]}
                  type={meta.secret ? "password" : "text"}
                  onChange={(v) => set("config", { ...value.config, [key]: v })}
                  help={
                    key === "tls"
                      ? "starttls (default), tls, or none"
                      : key === "timeout"
                        ? "1–30 seconds; default 15"
                        : undefined
                  }
                />
              ),
            )}
          </>
        )}
        {page === "Routing rules" && (
          <>
            <div className="divider">Match conditions</div>
            <p className="muted">
              All conditions must match. Use metadata.field for structured
              values; severity supports gte / lte.
            </p>
            {value.conditions.map((c: Row, i: number) => (
              <div className="condition" key={i}>
                <input
                  aria-label="Condition field"
                  value={c.field}
                  onChange={(e) =>
                    set(
                      "conditions",
                      value.conditions.map((v: Row, j: number) =>
                        j === i ? { ...v, field: e.target.value } : v,
                      ),
                    )
                  }
                />
                <select
                  aria-label="Condition operator"
                  value={c.op}
                  onChange={(e) =>
                    set(
                      "conditions",
                      value.conditions.map((v: Row, j: number) =>
                        j === i ? { ...v, op: e.target.value } : v,
                      ),
                    )
                  }
                >
                  {[
                    "equals",
                    "not_equals",
                    "in",
                    "not_in",
                    "contains",
                    "exists",
                    "greater",
                    "less",
                    "gte",
                    "lte",
                  ].map((op) => (
                    <option key={op}>{op}</option>
                  ))}
                </select>
                <input
                  aria-label="Condition value"
                  value={
                    typeof c.value === "object"
                      ? JSON.stringify(c.value)
                      : String(c.value ?? "")
                  }
                  onChange={(e) => {
                    let v: any = e.target.value;
                    try {
                      v = JSON.parse(v);
                    } catch {
                      /* String value */
                    }
                    set(
                      "conditions",
                      value.conditions.map((x: Row, j: number) =>
                        j === i ? { ...x, value: v } : x,
                      ),
                    );
                  }}
                />
                <button
                  type="button"
                  className="icon"
                  aria-label="Remove condition"
                  onClick={() =>
                    set(
                      "conditions",
                      value.conditions.filter(
                        (_: unknown, j: number) => i !== j,
                      ),
                    )
                  }
                >
                  <X size={16} />
                </button>
              </div>
            ))}
            <button
              type="button"
              className="secondary"
              onClick={() =>
                set("conditions", [
                  ...value.conditions,
                  { field: "environment", op: "equals", value: "" },
                ])
              }
            >
              <Plus size={14} />
              Add condition
            </button>
            <div className="divider">Destination channels</div>
            {channels.data?.items.map((c: Row) => (
              <label className="check-row" key={c.id}>
                <input
                  type="checkbox"
                  checked={value.targets.some(
                    (t: Row) => t.channel_id === c.id,
                  )}
                  onChange={(e) =>
                    set(
                      "targets",
                      e.target.checked
                        ? [...value.targets, { channel_id: c.id }]
                        : value.targets.filter(
                            (t: Row) => t.channel_id !== c.id,
                          ),
                    )
                  }
                />
                {c.name}
                <Badge value={c.provider} />
              </label>
            ))}
            <JsonField
              label="Advanced targets (optional recipient_id / group_id)"
              value={value.targets}
              onChange={(v) => set("targets", v)}
            />
          </>
        )}
        {page === "Groups" && (
          <>
            <div className="divider">Recipients</div>
            {recipients.data?.items.map((r: Row) => (
              <label className="check-row" key={r.id}>
                <input
                  type="checkbox"
                  checked={value.members.includes(r.id)}
                  onChange={(e) =>
                    set(
                      "members",
                      e.target.checked
                        ? [...value.members, r.id]
                        : value.members.filter((id: string) => id !== r.id),
                    )
                  }
                />
                {r.name}
              </label>
            ))}
          </>
        )}
        <ErrorBox error={error} />
        <div className="form-footer">
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button disabled={busy}>{busy ? "Saving…" : "Save changes"}</button>
        </div>
      </form>
    </Modal>
  );
}

function Overview() {
  const q = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api("/dashboard"),
    refetchInterval: 5000,
  });
  const data = q.data;
  if (!data) return <ErrorBox error={q.error} />;
  const states = data.deliveries;
  return (
    <>
      <div className="welcome-banner">
        <div>
          <span className="eyebrow">WORKSPACE PULSE</span>
          <h2>
            Every important event.
            <br />
            In the right hands.
          </h2>
          <p>Your notification activity, without the noise.</p>
        </div>
        <div className="pulse-art">
          <Radio size={74} />
          <span className="pulse-dot" />
        </div>
      </div>
      <div className="metrics">
        {[
          ["Notifications", data.notifications, Bell],
          ["Provider accepted", states.SENT || 0, Check],
          [
            "Awaiting dispatch",
            (states.PENDING || 0) + (states.RETRY_SCHEDULED || 0),
            Boxes,
          ],
          [
            "Needs attention",
            (states.FAILED || 0) + (states.DEAD_LETTER || 0),
            Activity,
          ],
        ].map(([label, value, Icon]: any) => (
          <div className="metric" key={label}>
            <div>
              <span>{label}</span>
              <Icon size={18} />
            </div>
            <strong>{value.toLocaleString()}</strong>
            <small>Across your workspace</small>
          </div>
        ))}
      </div>
      <div className="card">
        <div className="section-head">
          <h2>Latest notifications</h2>
          <span className="live-dot">Live · refreshes every 5s</span>
        </div>
        <EventTable rows={data.recent} />
      </div>
      <div className="card">
        <h2>Severity breakdown</h2>
        <div className="severity-bars">
          {["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"].map((s) => (
            <div key={s}>
              <Badge value={s} />
              <div className="bar">
                <span
                  style={{
                    width:
                      (100 * (data.severity[s] || 0)) /
                        Math.max(1, data.notifications) +
                      "%",
                  }}
                />
              </div>
              <strong>{data.severity[s] || 0}</strong>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
function EventTable({
  rows,
  onSelect,
}: {
  rows: Row[];
  onSelect?: (row: Row) => void;
}) {
  return rows.length ? (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Notification</th>
            <th>Severity</th>
            <th>Environment</th>
            <th>Status</th>
            <th>Received</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                <button
                  className="text-button"
                  onClick={() => onSelect?.(row)}
                  disabled={!onSelect}
                >
                  {row.title}
                </button>
                <small>{row.category || row.id.slice(0, 8)}</small>
              </td>
              <td>
                <Badge value={row.severity} />
              </td>
              <td>{row.environment}</td>
              <td>
                <Badge value={row.status} />
              </td>
              <td className="muted nowrap">{date(row.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty
      text="No notifications yet"
      detail="Register a source, configure a route, and submit your first event."
    />
  );
}
function Empty({ text, detail }: { text: string; detail: string }) {
  return (
    <div className="empty">
      <Bell size={28} />
      <h3>{text}</h3>
      <p>{detail}</p>
    </div>
  );
}
function Detail({ row, onClose }: { row: Row; onClose: () => void }) {
  const q = useQuery({
    queryKey: ["detail", row.id],
    queryFn: () => api("/notifications/" + row.id + "/deliveries"),
    refetchInterval: 5000,
  });
  return (
    <Modal title={row.title} onClose={onClose}>
      <div className="tag-line">
        <Badge value={row.severity} />
        <Badge value={row.status} />
        <span>{row.environment}</span>
      </div>
      <p className="message">{row.message}</p>
      <pre>{JSON.stringify(row.metadata, null, 2)}</pre>
      <h3>Delivery timeline</h3>
      <ErrorBox error={q.error} />
      {q.data?.map((d: Row) => (
        <div className="delivery" key={d.id}>
          <Badge value={d.status} />
          <p>
            Channel {d.channel_id} {d.recipient && "→ " + d.recipient}
          </p>
          {d.accepted_at && (
            <small>
              Provider accepted {date(d.accepted_at)}. This does not confirm
              recipient delivery.
            </small>
          )}
          {d.attempt_history.map((a: Row) => (
            <p key={a.id}>
              Attempt {a.number} · {date(a.created_at)} ·{" "}
              {Math.round(a.duration_ms)} ms ·{" "}
              {a.success ? "Accepted" : a.error}
            </p>
          ))}
        </div>
      ))}
      {q.data?.length === 0 && (
        <p className="muted">No destinations matched this event.</p>
      )}
    </Modal>
  );
}
function QueueHeader({
  onAction,
}: {
  onAction: (action: string, filters?: Row) => void;
}) {
  const q = useQuery({
    queryKey: ["queue-stats"],
    queryFn: () => api("/queue/stats"),
    refetchInterval: 5000,
  });
  if (!q.data) return <ErrorBox error={q.error} />;
  return (
    <>
      <div className="metrics compact">
        {[
          "PENDING",
          "IN_PROGRESS",
          "RETRY_SCHEDULED",
          "DEAD_LETTER",
          "FAILED",
        ].map((s) => (
          <div className="metric" key={s}>
            <span>{titleCase(s)}</span>
            <strong>{q.data.counts[s] || 0}</strong>
          </div>
        ))}
      </div>
      <div className="queue-strip">
        <span className="live-dot">
          {q.data.paused ? "Dispatch paused" : "Dispatch enabled"}
        </span>
        <span>{q.data.dispatch_per_minute} attempts / min</span>
        <span>
          Oldest pending: {Math.round(q.data.oldest_pending_seconds / 60)} min
        </span>
        <span>
          {q.data.workers.filter((w: Row) => w.healthy).length} healthy workers
        </span>
        <button
          className="secondary"
          onClick={() => onAction(q.data.paused ? "resume" : "pause")}
        >
          {q.data.paused ? "Resume dispatch" : "Pause dispatch"}
        </button>
      </div>
    </>
  );
}
function SettingsPage() {
  const q = useQuery({
    queryKey: ["settings"],
    queryFn: () => api("/settings"),
  });
  const [value, setValue] = useState<Row | null>(null),
    [message, setMessage] = useState("");
  useEffect(() => {
    if (q.data)
      setValue(
        Object.fromEntries(
          [
            "app_name",
            "base_url",
            "timezone",
            "retention_days",
            "retention_enabled",
            "max_attempts",
            "retry_base",
          ].map((k) => [k, q.data[k]]),
        ),
      );
  }, [q.data]);
  if (!value) return <ErrorBox error={q.error} />;
  return (
    <div className="card settings-card">
      <h2>Workspace settings</h2>
      <p className="muted">
        Database: {q.data?.database} · Version {q.data?.version}
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await api("/settings", "PATCH", value);
            setMessage("Settings saved.");
          } catch (e) {
            setMessage((e as Error).message);
          }
        }}
      >
        <div className="form-grid">
          {Object.entries(value).map(([k, v]) => (
            <Field
              key={k}
              label={titleCase(k)}
              value={v}
              type={typeof v === "boolean" ? "checkbox" : typeof v === "number" ? "number" : "text"}
              onChange={(x) => setValue({ ...value, [k]: x })}
            />
          ))}
        </div>
        <button>Save settings</button>
      </form>
      <p role="status">{message}</p>
      <div className="divider">Retention maintenance</div>
      <p className="muted">
        Deletes up to 500 expired terminal notifications per batch. Audit
        history is retained. Deleting a notification also expires its
        idempotency key.
      </p>
      <button
        className="secondary"
        onClick={async () => {
          try {
            const preview = await api("/retention", "POST", {});
            if (
              window.confirm(
                `Permanently delete ${preview.affected} expired notifications? This cannot be undone.`,
              )
            ) {
              const r = await api("/retention", "POST", { confirm: true });
              setMessage(`Deleted ${r.affected} expired notifications.`);
            }
          } catch (e) {
            setMessage((e as Error).message);
          }
        }}
      >
        Preview retention cleanup
      </button>
    </div>
  );
}
export function Console({
  user,
  onLogout,
}: {
  user: Row;
  onLogout: () => void;
}) {
  const qc = useQueryClient();
  const [page, setPage] = useState("Overview"),
    [offset, setOffset] = useState(0),
    [filter, setFilter] = useState(""),
    [search, setSearch] = useState(""),
    [environment, setEnvironment] = useState("");
  const [editor, setEditor] = useState<Row | undefined | null>(null),
    [detail, setDetail] = useState<Row | null>(null),
    [dialog, setDialog] = useState<Row | null>(null),
    [notice, setNotice] = useState(""),
    [error, setError] = useState(""),
    [selected, setSelected] = useState<string[]>([]),
    [dark, setDark] = useState(localStorage.getItem("nd-theme") === "dark");
  const [sample, setSample] = useState<Row>(sampleEvent),
    [simulation, setSimulation] = useState<Row | null>(null);
  const display = useQuery({
    queryKey: ["display"],
    queryFn: () => api("/system/display"),
  });
  displayTimezone = display.data?.timezone;
  const canEdit = user.role !== "VIEWER",
    isAdmin = user.role === "ADMIN";
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("nd-theme", dark ? "dark" : "light");
  }, [dark]);
  const params = new URLSearchParams({ offset: String(offset), limit: "20" });
  if (filter)
    params.set(page === "Notifications" ? "severity" : "status", filter);
  if (search && page === "Notifications") params.set("search", search);
  if (environment && ["Notifications", "Queue"].includes(page))
    params.set("environment", environment);
  const endpoint = endpoints[page];
  const q = useQuery({
    queryKey: [page, params.toString()],
    queryFn: () => api(endpoint + "?" + params),
    enabled: !!endpoint,
    refetchInterval: 5000,
  });
  function refresh() {
    qc.invalidateQueries();
  }
  async function perform(fn: () => Promise<any>) {
    setError("");
    try {
      await fn();
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  function changePage(name: string) {
    setPage(name);
    setOffset(0);
    setFilter("");
    setSearch("");
    setEnvironment("");
    setSelected([]);
    setNotice("");
    setError("");
  }
  async function queueAction(action: string, filters: Row = {}) {
    await perform(async () => {
      if (["pause", "resume"].includes(action)) {
        await api("/queue/" + action, "POST", filters);
        return;
      }
      const body = {
        ...filters,
        ...(environment ? { environment } : {}),
        ...(filter ? { status: filter } : {}),
        ...(selected.length ? { ids: selected } : {}),
      };
      const result = await api("/queue/" + action, "POST", body);
      setDialog({ kind: "confirm", action, body, result });
    });
  }
  async function edit(row: Row) {
    await perform(async () => {
      setEditor(page === "Channels" ? await api("/channels/" + row.id) : row);
    });
  }
  async function duplicate(row: Row) {
    await perform(async () => {
      if (page === "Channels") {
        const copy = await api(
          "/channels/" + row.id + "/duplicate",
          "POST",
          {},
        );
        setEditor(await api("/channels/" + copy.id));
      } else {
        setEditor({ ...row, id: undefined, name: row.name + " (copy)" });
      }
    });
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <div className="workspace">
          <span>N</span>
          <div>
            <strong>{display.data?.app_name || "Your workspace"}</strong>
            <small>Self-hosted installation</small>
          </div>
          <ShieldCheck size={16} />
        </div>
        <span className="nav-label">WORKSPACE</span>
        <nav>
          {navigation
            .filter(
              ([name]) =>
                isAdmin || !["Users", "Audit logs", "Settings"].includes(name),
            )
            .map(([name, Icon]) => (
              <button
                key={name}
                className={name === page ? "active" : ""}
                onClick={() => changePage(name)}
              >
                <Icon size={18} />
                {name}
                {name === "Queue" && <span className="nav-dot" />}
              </button>
            ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-note">
            <ShieldCheck size={16} />
            <span>
              Your infrastructure.
              <br />
              Your notifications.
            </span>
          </div>
          <button onClick={() => setDark(!dark)}>
            {dark ? <Sun size={17} /> : <Moon size={17} />}{" "}
            {dark ? "Light appearance" : "Dark appearance"}
          </button>
          <button
            onClick={() =>
              perform(async () => {
                await api("/auth/logout", "POST");
                qc.clear();
                onLogout();
              })
            }
          >
            <LogOut size={17} />
            Sign out
          </button>
          <button
            className="text-button"
            onClick={() =>
              setDialog({
                kind: "password",
                value: { current_password: "", password: "" },
              })
            }
          >
            Change password
          </button>
          <div className="user-chip">
            <span>{user.full_name[0]}</span>
            <div>
              <strong>{user.full_name}</strong>
              <small>{titleCase(user.role)}</small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-area">
        <header>
          <div className="breadcrumb">
            Workspace <ChevronRight size={14} />
            <strong>{page}</strong>
          </div>
          <span className="version">
            <span /> NotiDeck 0.1.0rc2
          </span>
          <div className="mobile-tools">
            <button
              className="icon"
              aria-label="Toggle theme"
              onClick={() => setDark(!dark)}
            >
              <Moon size={17} />
            </button>
            <button
              className="icon"
              aria-label="Change password"
              onClick={() =>
                setDialog({
                  kind: "password",
                  value: { current_password: "", password: "" },
                })
              }
            >
              <KeyRound size={17} />
            </button>
            <button
              className="icon"
              aria-label="Sign out"
              onClick={() =>
                perform(async () => {
                  await api("/auth/logout", "POST");
                  qc.clear();
                  onLogout();
                })
              }
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <span className="eyebrow">NOTIDECK CONSOLE</span>
              <h1>{page}</h1>
              <p>{descriptions[page]}</p>
            </div>
            <div className="actions">
              <button
                className="secondary"
                aria-label="Refresh data"
                onClick={refresh}
              >
                <RefreshCw size={16} />
              </button>
              {page === "Routing rules" && canEdit && (
                <button
                  className="secondary"
                  onClick={() => {
                    setSimulation(null);
                    setDialog({ kind: "simulate" });
                  }}
                >
                  Simulate event
                </button>
              )}
              {defaults[page] &&
                canEdit &&
                (!["Sources", "Users"].includes(page) || isAdmin) && (
                  <button onClick={() => setEditor(undefined)}>
                    <Plus size={17} />
                    Create{" "}
                    {page === "Routing rules"
                      ? "rule"
                      : page.toLowerCase().replace(/s$/, "")}
                  </button>
                )}
            </div>
          </div>
          {notice && (
            <div className="notice" role="status">
              {notice}
              <button
                className="icon"
                aria-label="Dismiss notice"
                onClick={() => setNotice("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          <ErrorBox error={error || q.error} />
          {page === "Overview" ? (
            <Overview />
          ) : page === "Settings" ? (
            <SettingsPage />
          ) : (
            <>
              {page === "Queue" && (
                <QueueHeader
                  onAction={
                    canEdit
                      ? queueAction
                      : () => setError("Operator permission required")
                  }
                />
              )}
              <section className="card data-card">
                <div className="toolbar">
                  <div className="actions">
                    {page === "Notifications" && (
                      <div className="search">
                        <Search size={16} />
                        <input
                          aria-label="Search notifications"
                          placeholder="Search notifications…"
                          value={search}
                          onChange={(e) => {
                            setSearch(e.target.value);
                            setOffset(0);
                          }}
                        />
                      </div>
                    )}
                    {["Notifications", "Queue"].includes(page) && (
                      <>
                        <select
                          aria-label="Filter by severity or status"
                          value={filter}
                          onChange={(e) => {
                            setFilter(e.target.value);
                            setOffset(0);
                          }}
                        >
                          <option value="">
                            {page === "Notifications"
                              ? "All severities"
                              : "All statuses"}
                          </option>
                          {(page === "Notifications"
                            ? ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
                            : [
                                "PENDING",
                                "IN_PROGRESS",
                                "RETRY_SCHEDULED",
                                "SENT",
                                "FAILED",
                                "DEAD_LETTER",
                                "CANCELLED",
                              ]
                          ).map((v) => (
                            <option key={v}>{v}</option>
                          ))}
                        </select>
                        <input
                          aria-label="Filter environment"
                          placeholder="All environments"
                          value={environment}
                          onChange={(e) => {
                            setEnvironment(e.target.value);
                            setOffset(0);
                          }}
                        />
                      </>
                    )}
                  </div>
                  {page === "Queue" && canEdit && (
                    <div className="actions">
                      <button
                        className="secondary"
                        onClick={() => queueAction("retry")}
                      >
                        Retry {selected.length ? "selected" : "eligible"}
                      </button>
                      {isAdmin && (
                        <button
                          className="danger"
                          onClick={() => queueAction("clear")}
                        >
                          Cancel {selected.length ? "selected" : "eligible"}
                        </button>
                      )}
                    </div>
                  )}
                  <span className="muted">{q.data?.total ?? 0} records</span>
                </div>
                {q.isLoading ? (
                  <p className="empty">Loading…</p>
                ) : page === "Notifications" ? (
                  <EventTable rows={q.data?.items || []} onSelect={setDetail} />
                ) : !q.data?.items.length ? (
                  <Empty
                    text={"No " + page.toLowerCase() + " yet"}
                    detail={
                      defaults[page]
                        ? "Create your first record to get started."
                        : "Activity will appear here as notifications are processed."
                    }
                  />
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          {page === "Queue" && <th>Select</th>}
                          <th>
                            {page === "Audit logs"
                              ? "Operation"
                              : page === "Queue"
                                ? "Delivery"
                                : "Name"}
                          </th>
                          <th>{page === "Audit logs" ? "Actor" : "Details"}</th>
                          <th>{page === "Audit logs" ? "Context" : "State"}</th>
                          <th>Created</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {q.data.items.map((row: Row) => (
                          <tr key={row.id}>
                            {page === "Queue" && (
                              <td>
                                <input
                                  type="checkbox"
                                  aria-label={"Select " + row.id}
                                  checked={selected.includes(row.id)}
                                  onChange={(e) =>
                                    setSelected(
                                      e.target.checked
                                        ? [...selected, row.id]
                                        : selected.filter(
                                            (id) => id !== row.id,
                                          ),
                                    )
                                  }
                                />
                              </td>
                            )}
                            <td>
                              <strong>
                                {row.name ||
                                  row.full_name ||
                                  row.operation ||
                                  row.id.slice(0, 8)}
                              </strong>
                              <small className="record-id" title={row.id}>
                                {row.id.slice(0, 8)}
                              </small>
                            </td>
                            <td>
                              {row.provider ||
                                row.environment ||
                                row.role ||
                                row.actor ||
                                (row.priority !== undefined
                                  ? "Priority " + row.priority
                                  : row.channel_id?.slice(0, 8)) ||
                                (row.addresses
                                  ? Object.keys(row.addresses).join(", ")
                                  : row.members
                                    ? row.members.length + " recipients"
                                    : "—")}
                            </td>
                            <td>
                              {row.status ? (
                                <Badge value={row.status} />
                              ) : row.enabled !== undefined ? (
                                <Badge
                                  value={row.enabled ? "ENABLED" : "DISABLED"}
                                />
                              ) : row.details ? (
                                <span className="audit-detail">
                                  {JSON.stringify(row.details)}
                                </span>
                              ) : (
                                "—"
                              )}
                            </td>
                            <td className="muted nowrap">
                              {date(row.created_at)}
                            </td>
                            <td>
                              <div className="row-actions">
                                {defaults[page] &&
                                  canEdit &&
                                  (!["Sources", "Users"].includes(page) ||
                                    isAdmin) && (
                                    <button
                                      className="text-button"
                                      onClick={() => edit(row)}
                                    >
                                      Edit
                                    </button>
                                  )}
                                {["Channels", "Routing rules"].includes(page) &&
                                  canEdit && (
                                    <button
                                      className="text-button"
                                      onClick={() => duplicate(row)}
                                    >
                                      Duplicate
                                    </button>
                                  )}
                                {page === "Channels" && canEdit && (
                                  <>
                                    <button
                                      className="text-button"
                                      onClick={() => {
                                        setDialog({ kind: "test", row });
                                      }}
                                    >
                                      Test
                                    </button>
                                    <button
                                      className="text-button"
                                      onClick={() =>
                                        queueAction(
                                          row.paused ? "resume" : "pause",
                                          { channel_id: row.id },
                                        )
                                      }
                                    >
                                      {row.paused ? "Resume" : "Pause"}
                                    </button>
                                  </>
                                )}
                                {page === "Sources" && isAdmin && (
                                  <button
                                    className="text-button"
                                    onClick={() =>
                                      perform(async () => {
                                        const keys = await api(
                                          "/sources/" + row.id + "/keys",
                                        );
                                        setDialog({ kind: "keys", row, keys });
                                      })
                                    }
                                  >
                                    <KeyRound size={13} />
                                    Keys
                                  </button>
                                )}
                                {page === "Queue" && (
                                  <button
                                    className="text-button"
                                    onClick={() =>
                                      perform(async () =>
                                        setDetail(
                                          await api(
                                            "/notifications/" +
                                              row.notification_id,
                                          ),
                                        ),
                                      )
                                    }
                                  >
                                    History
                                  </button>
                                )}
                                {page === "Templates" && canEdit && (
                                  <button
                                    className="text-button"
                                    onClick={() => {
                                      setDialog({ kind: "template", row });
                                      setSimulation(null);
                                    }}
                                  >
                                    Preview
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <div className="pagination">
                  <span>
                    Showing {q.data?.total ? offset + 1 : 0}–
                    {Math.min(offset + 20, q.data?.total || 0)} of{" "}
                    {q.data?.total || 0}
                  </span>
                  <div>
                    <button
                      className="secondary"
                      aria-label="Previous page"
                      disabled={!offset}
                      onClick={() => setOffset(Math.max(0, offset - 20))}
                    >
                      <ChevronLeft size={16} />
                    </button>
                    <button
                      className="secondary"
                      aria-label="Next page"
                      disabled={offset + 20 >= (q.data?.total || 0)}
                      onClick={() => setOffset(offset + 20)}
                    >
                      <ChevronRight size={16} />
                    </button>
                  </div>
                </div>
              </section>
              {page === "Queue" && (
                <p className="footnote">
                  <CircleHelp size={14} />
                  Cancellation preserves notification history. A send already in
                  progress cannot always be recalled.
                </p>
              )}
            </>
          )}
          <footer>
            NotiDeck <span>One Platform. Every Notification.</span>
            <a href="/api/openapi.json" target="_blank" rel="noreferrer">
              API schema
            </a>
          </footer>
        </main>
      </div>
      {editor !== null && (
        <Editor
          page={page}
          initial={editor}
          onClose={() => setEditor(null)}
          onSave={refresh}
        />
      )}
      {detail && <Detail row={detail} onClose={() => setDetail(null)} />}
      {dialog && (
        <Modal
          title={
            dialog.kind === "password"
              ? "Change your password"
              : dialog.kind === "confirm"
                ? "Confirm queue operation"
                : dialog.kind === "keys"
                  ? "Source API keys"
                  : dialog.kind === "simulate"
                    ? "Simulate routing"
                    : dialog.kind === "template"
                      ? "Template preview"
                      : "Test channel"
          }
          onClose={() => setDialog(null)}
        >
          {dialog.kind === "password" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                perform(async () => {
                  await api("/auth/password", "POST", dialog.value);
                  qc.clear();
                  onLogout();
                });
              }}
            >
              {["current_password", "password"].map((k) => (
                <Field
                  key={k}
                  label={k === "password" ? "New password" : "Current password"}
                  type="password"
                  value={dialog.value[k]}
                  onChange={(v) =>
                    setDialog({ ...dialog, value: { ...dialog.value, [k]: v } })
                  }
                  required
                />
              ))}
              <p className="muted">
                Changing your password signs you out of every session.
              </p>
              <button>Change password</button>
            </form>
          )}
          {dialog.kind === "confirm" && (
            <>
              <p>
                This will {dialog.action === "retry" ? "retry" : "cancel"}{" "}
                <strong>{dialog.result.affected}</strong> eligible deliveries.
                The count may change if workers claim jobs before confirmation.
              </p>
              <p className="muted">{dialog.result.note}</p>
              <Field
                label="Reason (optional)"
                value={dialog.body.reason || ""}
                onChange={(v) =>
                  setDialog({ ...dialog, body: { ...dialog.body, reason: v } })
                }
              />
              <button
                onClick={() =>
                  perform(async () => {
                    const result = await api(
                      "/queue/" + dialog.action,
                      "POST",
                      { ...dialog.body, confirm: true },
                    );
                    setNotice(`${result.affected} deliveries updated.`);
                    setDialog(null);
                    setSelected([]);
                  })
                }
              >
                Confirm {dialog.action}
              </button>
            </>
          )}
          {dialog.kind === "test" && (
            <>
              <p>
                Send a real test notification to{" "}
                <strong>{dialog.row.name}</strong>? Provider charges may apply.
              </p>
              <button
                onClick={() =>
                  perform(async () => {
                    const result = await api(
                      "/channels/" + dialog.row.id + "/test",
                      "POST",
                      {},
                    );
                    setNotice(
                      result.success
                        ? "Test accepted by provider."
                        : `Test failed: ${result.error} (${result.code || "transport"})`,
                    );
                    setDialog(null);
                  })
                }
              >
                <Send size={16} />
                Send test
              </button>
            </>
          )}
          {dialog.kind === "keys" && (
            <>
              <p className="muted">
                Keys are scoped to this source and shown only at creation.
                Create a replacement before revoking the old key to rotate
                safely.
              </p>
              {dialog.keys.map((k: Row) => (
                <div className="key-row" key={k.id}>
                  <span>
                    {k.name} · {k.prefix}… {k.revoked ? "(revoked)" : ""}
                  </span>
                  {!k.revoked && (
                    <button
                      className="text-button"
                      onClick={() =>
                        perform(async () => {
                          await api("/keys/" + k.id + "/revoke", "POST", {});
                          setDialog({
                            ...dialog,
                            keys: await api(
                              "/sources/" + dialog.row.id + "/keys",
                            ),
                          });
                        })
                      }
                    >
                      Revoke
                    </button>
                  )}
                </div>
              ))}
              {dialog.secret && (
                <div className="secret">
                  <strong>Copy now. This value will not be shown again.</strong>
                  <code>{dialog.secret}</code>
                </div>
              )}
              <div className="actions">
                <button
                  onClick={() =>
                    perform(async () => {
                      const result = await api(
                        "/sources/" + dialog.row.id + "/keys",
                        "POST",
                        { name: "Console key" },
                      );
                      setDialog({
                        ...dialog,
                        secret: result.key,
                        keys: await api("/sources/" + dialog.row.id + "/keys"),
                      });
                    })
                  }
                >
                  Create API key
                </button>
                <button
                  className="secondary"
                  onClick={() =>
                    perform(async () => {
                      const result = await api(
                        "/sources/" + dialog.row.id + "/webhook-secret",
                        "POST",
                        {},
                      );
                      setDialog({ ...dialog, secret: result.secret });
                    })
                  }
                >
                  Rotate webhook secret
                </button>
              </div>
            </>
          )}
          {["simulate", "template"].includes(dialog.kind) && (
            <>
              <JsonField
                label="Sample event"
                value={sample}
                onChange={setSample}
              />
              <button
                onClick={() =>
                  perform(async () => {
                    setSimulation(
                      await api(
                        dialog.kind === "simulate"
                          ? "/routes/simulate"
                          : "/templates/preview",
                        "POST",
                        dialog.kind === "simulate"
                          ? sample
                          : { template: dialog.row.text, event: sample },
                      ),
                    );
                  })
                }
              >
                Run preview
              </button>
              {simulation && <pre>{JSON.stringify(simulation, null, 2)}</pre>}
            </>
          )}
          <ErrorBox error={error} />
        </Modal>
      )}
    </div>
  );
}
function App() {
  const [revision, setRevision] = useState(0);
  const status = useQuery({
    queryKey: ["setup", revision],
    queryFn: () => api("/setup/status"),
  });
  const me = useQuery({
    queryKey: ["me", revision],
    queryFn: () => api("/auth/me"),
    enabled: status.data?.initialized === true,
  });
  const reload = () => setRevision((r) => r + 1);
  if (status.isLoading)
    return (
      <div className="loading">
        <Brand />
        <p>Opening your workspace…</p>
      </div>
    );
  if (status.error)
    return (
      <div className="loading">
        <ErrorBox error={status.error} />
        <button onClick={() => status.refetch()}>Retry connection</button>
      </div>
    );
  if (!status.data?.initialized) return <Setup onDone={reload} />;
  if (me.isLoading)
    return <div className="loading">Loading your workspace…</div>;
  if (!me.data) return <Login onDone={reload} />;
  return <Console user={me.data} onLogout={reload} />;
}
const root = document.getElementById("root");
if (root)
  createRoot(root).render(
    <React.StrictMode>
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>
    </React.StrictMode>,
  );
