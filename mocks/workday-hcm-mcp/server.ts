// mocks/workday-hcm-mcp/server.ts — Agency vertical pack: Workday HCM (broad surface).
// Distinct from the POC2 mocks/workday-hr-mcp (positions + JML) and the POC1
// mocks/workday-mcp (vendor master + expense). Default port 4225, matching the
// agency pack 4200-4299 numbering; override with WORKDAY_HCM_MCP_PORT to
// coexist with the POC2 ServiceNow mock when both packs run side by side.
import express from "express";

type Employee = {
  id: string;
  name: string;
  email: string;
  department: string;
  title: string;
  level: string;
  manager_id: string | null;
  status: "active" | "on_leave" | "terminated";
  comp_band_gbp: { min: number; midpoint: number; max: number };
  base_salary_gbp: number;
  start_date: string;
};
type Transfer = {
  transfer_id: string;
  employee_id: string;
  from_department: string;
  to_department: string;
  to_manager_id: string;
  effective_date: string;
  status: "pending_approval" | "approved" | "rejected";
  submitted_at: string;
  approved_at?: string;
  approved_by?: string;
};
type CompLetter = {
  letter_id: string;
  employee_id: string;
  reason: "new_hire" | "promotion" | "merit" | "retention";
  new_base_salary_gbp: number;
  effective_date: string;
  generated_at: string;
};
type OooEntry = {
  ooo_id: string;
  employee_id: string;
  start_date: string;
  end_date: string;
  reason: "vacation" | "sick" | "parental" | "other";
};
type LearningRecord = {
  record_id: string;
  employee_id: string;
  course_code: string;
  course_name: string;
  completed_at: string;
  score: number;
};

const today = new Date().toISOString().slice(0, 10);
const ago = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
};

const employees: Employee[] = [
  { id: "EMP-001", name: "Priya Shah", email: "priya.shah@zava.example", department: "Creative", title: "ECD", level: "L7", manager_id: null, status: "active", comp_band_gbp: { min: 140000, midpoint: 170000, max: 200000 }, base_salary_gbp: 172000, start_date: "2019-04-01" },
  { id: "EMP-002", name: "Marcus Lin", email: "marcus.lin@zava.example", department: "Creative", title: "Creative Director", level: "L6", manager_id: "EMP-001", status: "active", comp_band_gbp: { min: 110000, midpoint: 130000, max: 150000 }, base_salary_gbp: 128000, start_date: "2020-09-14" },
  { id: "EMP-003", name: "Sara Okafor", email: "sara.okafor@zava.example", department: "Creative", title: "Senior Copywriter", level: "L4", manager_id: "EMP-002", status: "active", comp_band_gbp: { min: 60000, midpoint: 72000, max: 84000 }, base_salary_gbp: 70000, start_date: "2022-02-07" },
  { id: "EMP-004", name: "Jin Park", email: "jin.park@zava.example", department: "Creative", title: "Art Director", level: "L4", manager_id: "EMP-002", status: "on_leave", comp_band_gbp: { min: 60000, midpoint: 72000, max: 84000 }, base_salary_gbp: 71500, start_date: "2021-08-23" },
  { id: "EMP-005", name: "Helena Brandt", email: "helena.brandt@zava.example", department: "Strategy", title: "Head of Strategy", level: "L6", manager_id: "EMP-001", status: "active", comp_band_gbp: { min: 110000, midpoint: 130000, max: 150000 }, base_salary_gbp: 134000, start_date: "2018-11-05" },
  { id: "EMP-006", name: "Diego Ramos", email: "diego.ramos@zava.example", department: "Strategy", title: "Strategy Director", level: "L5", manager_id: "EMP-005", status: "active", comp_band_gbp: { min: 85000, midpoint: 100000, max: 115000 }, base_salary_gbp: 99000, start_date: "2021-01-18" },
  { id: "EMP-007", name: "Aiko Tanaka", email: "aiko.tanaka@zava.example", department: "Media", title: "Head of Media", level: "L6", manager_id: "EMP-001", status: "active", comp_band_gbp: { min: 110000, midpoint: 130000, max: 150000 }, base_salary_gbp: 131000, start_date: "2017-06-12" },
  { id: "EMP-008", name: "Tom Whittaker", email: "tom.whittaker@zava.example", department: "Media", title: "Programmatic Lead", level: "L5", manager_id: "EMP-007", status: "active", comp_band_gbp: { min: 85000, midpoint: 100000, max: 115000 }, base_salary_gbp: 102000, start_date: "2020-03-30" },
  { id: "EMP-009", name: "Naledi Mokoena", email: "naledi.mokoena@zava.example", department: "Media", title: "Media Planner", level: "L3", manager_id: "EMP-008", status: "active", comp_band_gbp: { min: 45000, midpoint: 55000, max: 65000 }, base_salary_gbp: 53000, start_date: "2023-05-15" },
  { id: "EMP-010", name: "Lukas Becker", email: "lukas.becker@zava.example", department: "Finance", title: "CFO", level: "L8", manager_id: null, status: "active", comp_band_gbp: { min: 180000, midpoint: 220000, max: 260000 }, base_salary_gbp: 225000, start_date: "2016-10-01" },
  { id: "EMP-011", name: "Yara Haddad", email: "yara.haddad@zava.example", department: "Finance", title: "Financial Controller", level: "L5", manager_id: "EMP-010", status: "active", comp_band_gbp: { min: 85000, midpoint: 100000, max: 115000 }, base_salary_gbp: 97000, start_date: "2021-07-19" },
  { id: "EMP-012", name: "Owen Pritchard", email: "owen.pritchard@zava.example", department: "People", title: "CHRO", level: "L8", manager_id: null, status: "active", comp_band_gbp: { min: 170000, midpoint: 210000, max: 250000 }, base_salary_gbp: 212000, start_date: "2017-02-20" },
  { id: "EMP-013", name: "Mei Chen", email: "mei.chen@zava.example", department: "People", title: "HR Business Partner", level: "L4", manager_id: "EMP-012", status: "active", comp_band_gbp: { min: 60000, midpoint: 72000, max: 84000 }, base_salary_gbp: 73500, start_date: "2022-09-05" },
  { id: "EMP-014", name: "Rafael Ortiz", email: "rafael.ortiz@zava.example", department: "Tech", title: "CTO", level: "L8", manager_id: null, status: "active", comp_band_gbp: { min: 180000, midpoint: 220000, max: 260000 }, base_salary_gbp: 230000, start_date: "2015-08-11" },
  { id: "EMP-015", name: "Anya Volkov", email: "anya.volkov@zava.example", department: "Tech", title: "Principal Engineer", level: "L6", manager_id: "EMP-014", status: "active", comp_band_gbp: { min: 120000, midpoint: 140000, max: 160000 }, base_salary_gbp: 145000, start_date: "2019-12-02" },
];

const transfers: Transfer[] = [];
const compLetters: CompLetter[] = [
  { letter_id: "CL-0001", employee_id: "EMP-003", reason: "merit", new_base_salary_gbp: 70000, effective_date: ago(60), generated_at: ago(75) + "T09:12:00Z" },
  { letter_id: "CL-0002", employee_id: "EMP-008", reason: "promotion", new_base_salary_gbp: 102000, effective_date: ago(120), generated_at: ago(130) + "T15:40:00Z" },
  { letter_id: "CL-0003", employee_id: "EMP-015", reason: "retention", new_base_salary_gbp: 145000, effective_date: ago(30), generated_at: ago(45) + "T11:05:00Z" },
];
const ooo: OooEntry[] = [
  { ooo_id: "OOO-0001", employee_id: "EMP-004", start_date: ago(14), end_date: ago(-90), reason: "parental" },
  { ooo_id: "OOO-0002", employee_id: "EMP-006", start_date: today, end_date: today, reason: "sick" },
];
const learning: LearningRecord[] = [
  { record_id: "LR-0001", employee_id: "EMP-003", course_code: "GDPR-101", course_name: "GDPR Foundations", completed_at: ago(200) + "T10:00:00Z", score: 0.92 },
  { record_id: "LR-0002", employee_id: "EMP-009", course_code: "MEDIA-200", course_name: "Programmatic Buying Basics", completed_at: ago(60) + "T14:30:00Z", score: 0.88 },
  { record_id: "LR-0003", employee_id: "EMP-015", course_code: "SEC-300", course_name: "Secure Coding", completed_at: ago(45) + "T09:00:00Z", score: 0.95 },
];

let transferSeq = 1;
let letterSeq = compLetters.length + 1;
let oooSeq = ooo.length + 1;
let learningSeq = learning.length + 1;
let empSeq = employees.length + 1;
const pad4 = (n: number) => String(n).padStart(4, "0");
const pad3 = (n: number) => String(n).padStart(3, "0");

const app = express();
app.use(express.json());

app.get("/api/health", (_req, res) => res.json({ ok: true, name: "workday-hcm-mcp" }));

app.get("/api/employees", (req, res) => {
  const { department, manager_id, status } = req.query as Record<string, string | undefined>;
  let pool = employees;
  if (department) pool = pool.filter(e => e.department === department);
  if (manager_id) pool = pool.filter(e => e.manager_id === manager_id);
  if (status) pool = pool.filter(e => e.status === status);
  res.json({ employees: pool });
});

app.get("/api/employees/:id", (req, res) => {
  const e = employees.find(x => x.id === req.params.id);
  if (!e) return res.status(404).json({ error: "employee_not_found" });
  const manager = e.manager_id ? employees.find(m => m.id === e.manager_id) ?? null : null;
  const employee_ooo = ooo.filter(o => o.employee_id === e.id);
  res.json({ ...e, manager, ooo: employee_ooo });
});

app.post("/api/employees", (req, res) => {
  const b = req.body ?? {};
  if (!b.name || !b.department) return res.status(400).json({ error: "missing_fields" });
  const id = b.id ?? `EMP-${pad3(empSeq++)}`;
  const emp: Employee = {
    id, name: b.name, email: b.email ?? `${String(b.name).toLowerCase().replace(/\s+/g, ".")}@zava.example`,
    department: b.department, title: b.title ?? "Associate", level: b.level ?? "L3",
    manager_id: b.manager_id ?? null, status: b.status ?? "active",
    comp_band_gbp: b.comp_band_gbp ?? { min: 45000, midpoint: 55000, max: 65000 },
    base_salary_gbp: b.base_salary_gbp ?? 55000,
    start_date: b.start_date ?? today,
  };
  employees.push(emp);
  res.status(201).json(emp);
});

app.patch("/api/employees/:id", (req, res) => {
  const e = employees.find(x => x.id === req.params.id);
  if (!e) return res.status(404).json({ error: "employee_not_found" });
  Object.assign(e, req.body ?? {});
  res.json(e);
});

app.post("/api/employees/:id/transfer", (req, res) => {
  const e = employees.find(x => x.id === req.params.id);
  if (!e) return res.status(404).json({ error: "employee_not_found" });
  const b = req.body ?? {};
  if (!b.to_department || !b.to_manager_id) return res.status(400).json({ error: "missing_fields" });
  const t: Transfer = {
    transfer_id: `TR-${pad4(transferSeq++)}`,
    employee_id: e.id,
    from_department: e.department,
    to_department: b.to_department,
    to_manager_id: b.to_manager_id,
    effective_date: b.effective_date ?? today,
    status: "pending_approval",
    submitted_at: new Date().toISOString(),
  };
  transfers.push(t);
  res.status(201).json({ transfer_id: t.transfer_id, status: t.status });
});

app.post("/api/transfers/:id/approve", (req, res) => {
  const t = transfers.find(x => x.transfer_id === req.params.id);
  if (!t) return res.status(404).json({ error: "transfer_not_found" });
  if (t.status !== "pending_approval") return res.status(409).json({ error: "already_resolved", status: t.status });
  t.status = "approved";
  t.approved_at = new Date().toISOString();
  t.approved_by = (req.body && req.body.approver_id) ?? "EMP-012";
  const e = employees.find(x => x.id === t.employee_id);
  if (e) { e.department = t.to_department; e.manager_id = t.to_manager_id; }
  res.json(t);
});

app.get("/api/comp-letters/:id", (req, res) => {
  const cl = compLetters.find(x => x.letter_id === req.params.id);
  if (!cl) return res.status(404).json({ error: "comp_letter_not_found" });
  res.json(cl);
});

app.post("/api/comp-letters", (req, res) => {
  const b = req.body ?? {};
  if (!b.employee_id || typeof b.new_base_salary_gbp !== "number") {
    return res.status(400).json({ error: "missing_fields" });
  }
  if (!employees.find(e => e.id === b.employee_id)) return res.status(404).json({ error: "employee_not_found" });
  const cl: CompLetter = {
    letter_id: `CL-${pad4(letterSeq++)}`,
    employee_id: b.employee_id,
    reason: b.reason ?? "merit",
    new_base_salary_gbp: b.new_base_salary_gbp,
    effective_date: b.effective_date ?? today,
    generated_at: new Date().toISOString(),
  };
  compLetters.push(cl);
  res.status(201).json(cl);
});

app.get("/api/ooo-calendar", (req, res) => {
  const on_date = (req.query["on_date"] as string | undefined) ?? today;
  const out = ooo.filter(o => o.start_date <= on_date && on_date <= o.end_date);
  res.json({ on_date, entries: out });
});

app.post("/api/ooo-calendar", (req, res) => {
  const b = req.body ?? {};
  if (!b.employee_id || !b.start_date || !b.end_date) return res.status(400).json({ error: "missing_fields" });
  const o: OooEntry = {
    ooo_id: `OOO-${pad4(oooSeq++)}`,
    employee_id: b.employee_id,
    start_date: b.start_date,
    end_date: b.end_date,
    reason: b.reason ?? "other",
  };
  ooo.push(o);
  res.status(201).json(o);
});

app.get("/api/learning-records/:employee_id", (req, res) => {
  const out = learning.filter(l => l.employee_id === req.params.employee_id);
  res.json({ employee_id: req.params.employee_id, records: out });
});

app.post("/api/learning-records", (req, res) => {
  const b = req.body ?? {};
  if (!b.employee_id || !b.course_code) return res.status(400).json({ error: "missing_fields" });
  const lr: LearningRecord = {
    record_id: `LR-${pad4(learningSeq++)}`,
    employee_id: b.employee_id,
    course_code: b.course_code,
    course_name: b.course_name ?? b.course_code,
    completed_at: b.completed_at ?? new Date().toISOString(),
    score: typeof b.score === "number" ? b.score : 1.0,
  };
  learning.push(lr);
  res.status(201).json(lr);
});

const port = Number(process.env["WORKDAY_HCM_MCP_PORT"] ?? 4225);
app.listen(port, () => console.log(`[workday-hcm-mcp] listening on ${port}`));
