// mocks/salesforce-mcp/server.ts
//
// Salesforce CRM mock for the agency vertical pack (pitch-readiness F1).
// REST surface modelled loosely on the SFDC sObjects API but trimmed to the
// handful of objects the pitch-prep flows actually touch: Account,
// Opportunity, Contract, Case, Quote. Hand-crafted per locked decision #4 —
// no shared harness, no auth, in-memory seed.
import express from "express";

type Account = { id: string; name: string; industry: string; tier: string; owner: string; created_at: string };
type Opportunity = { id: string; account_id: string; name: string; stage: string; amount: number; close_date: string; owner: string };
type Contract = { id: string; account_id: string; name: string; status: string; value: number; start_date: string; end_date: string };
type Case = { id: string; account_id: string; subject: string; priority: string; status: string; opened_at: string };
type Quote = { id: string; opportunity_id: string; total: number; status: string; created_at: string };

const now = () => new Date().toISOString();
const mkid = (p: string) => `${p}_${Math.random().toString(36).slice(2, 10)}`;

const accounts: Account[] = [
  { id: "acc_unilever",   name: "Unilever",         industry: "FMCG",         tier: "Holding", owner: "alex.kim",      created_at: "2024-01-12T09:00:00Z" },
  { id: "acc_pepsico",    name: "PepsiCo",          industry: "FMCG",         tier: "Holding", owner: "priya.s",       created_at: "2024-02-04T09:00:00Z" },
  { id: "acc_lvmh",       name: "LVMH",             industry: "Luxury",       tier: "Holding", owner: "marc.dubois",   created_at: "2024-02-19T09:00:00Z" },
  { id: "acc_toyota",     name: "Toyota Motor",     industry: "Automotive",   tier: "Holding", owner: "yuki.tanaka",   created_at: "2024-03-03T09:00:00Z" },
  { id: "acc_hsbc",       name: "HSBC Group",       industry: "Financial",    tier: "Holding", owner: "j.okafor",      created_at: "2024-03-17T09:00:00Z" },
  { id: "acc_pfizer",     name: "Pfizer",           industry: "Pharma",       tier: "Holding", owner: "elena.r",       created_at: "2024-04-02T09:00:00Z" },
];

const opportunities: Opportunity[] = [
  { id: "opp_001", account_id: "acc_unilever", name: "Unilever Q3 Brand Refresh",     stage: "Qualify",   amount:  450000, close_date: "2026-09-30", owner: "alex.kim"    },
  { id: "opp_002", account_id: "acc_unilever", name: "Dove EMEA Always-On",            stage: "Propose",   amount: 1200000, close_date: "2026-08-15", owner: "alex.kim"    },
  { id: "opp_003", account_id: "acc_pepsico",  name: "Pepsi Super Bowl 2027",          stage: "Negotiate", amount: 3500000, close_date: "2026-12-01", owner: "priya.s"     },
  { id: "opp_004", account_id: "acc_pepsico",  name: "Gatorade Olympics Activation",   stage: "Won",       amount: 2100000, close_date: "2026-05-20", owner: "priya.s"     },
  { id: "opp_005", account_id: "acc_lvmh",     name: "Dior Holiday Campaign",          stage: "Propose",   amount: 1800000, close_date: "2026-10-10", owner: "marc.dubois" },
  { id: "opp_006", account_id: "acc_lvmh",     name: "Tiffany Bridal Relaunch",        stage: "Qualify",   amount:  900000, close_date: "2026-11-15", owner: "marc.dubois" },
  { id: "opp_007", account_id: "acc_toyota",   name: "Toyota EV Launch APAC",          stage: "Negotiate", amount: 2700000, close_date: "2026-09-01", owner: "yuki.tanaka" },
  { id: "opp_008", account_id: "acc_toyota",   name: "Lexus Print Refresh",            stage: "Lost",      amount:  300000, close_date: "2026-04-12", owner: "yuki.tanaka" },
  { id: "opp_009", account_id: "acc_hsbc",     name: "HSBC Wealth UK Always-On",       stage: "Won",       amount: 1500000, close_date: "2026-06-01", owner: "j.okafor"    },
  { id: "opp_010", account_id: "acc_hsbc",     name: "HSBC Sponsorship Strategy",      stage: "Propose",   amount:  650000, close_date: "2026-08-22", owner: "j.okafor"    },
  { id: "opp_011", account_id: "acc_pfizer",   name: "Pfizer DTC Vaccine Push",        stage: "Qualify",   amount: 1100000, close_date: "2026-10-30", owner: "elena.r"     },
  { id: "opp_012", account_id: "acc_pfizer",   name: "Pfizer Rare Disease Awareness",  stage: "Lost",      amount:  400000, close_date: "2026-03-18", owner: "elena.r"     },
];

const contracts: Contract[] = [
  { id: "ctr_001", account_id: "acc_unilever", name: "Unilever MSA 2026",   status: "active",    value: 4500000, start_date: "2026-01-01", end_date: "2026-12-31" },
  { id: "ctr_002", account_id: "acc_unilever", name: "Dove SOW Q3",         status: "draft",     value: 1200000, start_date: "2026-07-01", end_date: "2026-09-30" },
  { id: "ctr_003", account_id: "acc_pepsico",  name: "PepsiCo Master 2026", status: "active",    value: 8000000, start_date: "2026-01-01", end_date: "2026-12-31" },
  { id: "ctr_004", account_id: "acc_lvmh",     name: "LVMH Roster 2026",    status: "active",    value: 6200000, start_date: "2026-01-01", end_date: "2026-12-31" },
  { id: "ctr_005", account_id: "acc_lvmh",     name: "Dior Holiday SOW",    status: "in_review", value: 1800000, start_date: "2026-09-01", end_date: "2026-12-15" },
  { id: "ctr_006", account_id: "acc_toyota",   name: "Toyota APAC MSA",     status: "active",    value: 5400000, start_date: "2026-02-01", end_date: "2027-01-31" },
  { id: "ctr_007", account_id: "acc_hsbc",     name: "HSBC Wealth SOW",     status: "draft",     value: 1500000, start_date: "2026-06-01", end_date: "2026-12-31" },
  { id: "ctr_008", account_id: "acc_pfizer",   name: "Pfizer 2025 Renewal", status: "expired",   value: 3200000, start_date: "2025-01-01", end_date: "2025-12-31" },
];

const cases: Case[] = [
  { id: "case_001", account_id: "acc_unilever", subject: "Creative review SLA missed", priority: "High",   status: "open",   opened_at: "2026-04-18T09:30:00Z" },
  { id: "case_002", account_id: "acc_pepsico",  subject: "Media plan reconciliation",  priority: "Medium", status: "closed", opened_at: "2026-03-22T11:00:00Z" },
];

const quotes: Quote[] = [
  { id: "qte_001", opportunity_id: "opp_002", total: 1200000, status: "sent",     created_at: "2026-05-01T10:00:00Z" },
  { id: "qte_002", opportunity_id: "opp_005", total: 1800000, status: "draft",    created_at: "2026-05-10T10:00:00Z" },
];

const app = express();
app.use(express.json());

app.get("/api/health", (_req, res) => res.json({ ok: true, name: "salesforce-mcp" }));

app.get("/api/accounts", (req, res) => {
  let pool = accounts;
  const { industry, tier } = req.query as { industry?: string; tier?: string };
  if (industry) pool = pool.filter(a => a.industry === industry);
  if (tier) pool = pool.filter(a => a.tier === tier);
  res.json({ accounts: pool });
});
app.get("/api/accounts/:id", (req, res) => {
  const a = accounts.find(x => x.id === req.params.id);
  if (!a) return res.status(404).json({ error: "not_found" });
  res.json(a);
});
app.post("/api/accounts", (req, res) => {
  const { name, industry, tier, owner } = req.body ?? {};
  if (!name) return res.status(400).json({ error: "missing_name" });
  const a: Account = { id: mkid("acc"), name, industry: industry ?? "Unknown", tier: tier ?? "Standard", owner: owner ?? "unassigned", created_at: now() };
  accounts.push(a);
  res.status(201).json({ id: a.id });
});

app.get("/api/opportunities", (req, res) => {
  let pool = opportunities;
  const { stage, account_id } = req.query as { stage?: string; account_id?: string };
  if (stage) pool = pool.filter(o => o.stage === stage);
  if (account_id) pool = pool.filter(o => o.account_id === account_id);
  res.json({ opportunities: pool });
});
app.get("/api/opportunities/:id", (req, res) => {
  const o = opportunities.find(x => x.id === req.params.id);
  if (!o) return res.status(404).json({ error: "not_found" });
  res.json(o);
});
app.post("/api/opportunities", (req, res) => {
  const { account_id, name, stage, amount, close_date, owner } = req.body ?? {};
  if (!account_id || !name) return res.status(400).json({ error: "missing_fields" });
  const o: Opportunity = { id: mkid("opp"), account_id, name, stage: stage ?? "Qualify", amount: Number(amount ?? 0), close_date: close_date ?? "", owner: owner ?? "unassigned" };
  opportunities.push(o);
  res.status(201).json({ id: o.id });
});
app.patch("/api/opportunities/:id", (req, res) => {
  const o = opportunities.find(x => x.id === req.params.id);
  if (!o) return res.status(404).json({ error: "not_found" });
  const { stage, amount, close_date } = req.body ?? {};
  if (stage !== undefined) o.stage = stage;
  if (amount !== undefined) o.amount = Number(amount);
  if (close_date !== undefined) o.close_date = close_date;
  res.json(o);
});

app.get("/api/contracts", (_req, res) => res.json({ contracts }));
app.post("/api/contracts", (req, res) => {
  const { account_id, name, value, start_date, end_date } = req.body ?? {};
  if (!account_id || !name) return res.status(400).json({ error: "missing_fields" });
  const c: Contract = { id: mkid("ctr"), account_id, name, status: "draft", value: Number(value ?? 0), start_date: start_date ?? "", end_date: end_date ?? "" };
  contracts.push(c);
  res.status(201).json({ id: c.id, status: c.status });
});

app.get("/api/cases", (_req, res) => res.json({ cases }));
app.post("/api/cases", (req, res) => {
  const { account_id, subject, priority } = req.body ?? {};
  if (!account_id || !subject) return res.status(400).json({ error: "missing_fields" });
  const c: Case = { id: mkid("case"), account_id, subject, priority: priority ?? "Medium", status: "open", opened_at: now() };
  cases.push(c);
  res.status(201).json({ id: c.id });
});

app.get("/api/quotes/:id", (req, res) => {
  const q = quotes.find(x => x.id === req.params.id);
  if (!q) return res.status(404).json({ error: "not_found" });
  res.json(q);
});
app.post("/api/quotes", (req, res) => {
  const { opportunity_id, total } = req.body ?? {};
  if (!opportunity_id) return res.status(400).json({ error: "missing_opportunity_id" });
  const q: Quote = { id: mkid("qte"), opportunity_id, total: Number(total ?? 0), status: "draft", created_at: now() };
  quotes.push(q);
  res.status(201).json({ id: q.id });
});

const port = Number(process.env["SALESFORCE_MCP_PORT"] ?? 4200);
app.listen(port, () => console.log(`[salesforce-mcp] listening on ${port}`));
