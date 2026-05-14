// mocks/mediaocean-mcp/server.ts
//
// Mediaocean mock — agency vertical pack (pitch readiness f2). Models the
// media-buying spine: media plans → reconciliations → billings. The agency
// pack populates 6 holding clients × ~10 brands; seed below references that
// id-space (HC-01..HC-06, BR-001..BR-060) so downstream graphs can join.
import express from "express";

type LineItem = { id: string; channel: string; vendor: string; cost: number; impressions: number };
type MediaPlan = {
  id: string; campaign_id: string; brand_id: string; holding_client_id: string;
  name: string; status: "draft" | "approved" | "in_flight" | "closed";
  total_budget: number; currency: string; created_at: string; lines: LineItem[];
};
type Reconciliation = {
  id: string; plan_id: string; period: string; planned: number; actual: number;
  variance: number; status: "pending" | "approved" | "disputed"; submitted_at: string;
};
type Billing = {
  id: string; plan_id: string; vendor: string; amount: number; currency: string;
  status: "draft" | "issued" | "approved" | "paid"; issued_at: string;
};

const channels = ["display", "video", "ctv", "search", "social", "audio"];
const vendors = ["GoogleAds", "Meta", "TheTradeDesk", "AmazonDSP", "YouTube", "Spotify"];
const statuses: MediaPlan["status"][] = ["approved", "in_flight", "in_flight", "closed", "draft", "approved", "in_flight", "closed"];

function plan(i: number): MediaPlan {
  const hc = `HC-0${(i % 6) + 1}`;
  const brand = `BR-${String(((i * 7) % 60) + 1).padStart(3, "0")}`;
  const lines: LineItem[] = Array.from({ length: 3 + (i % 3) }, (_, k) => ({
    id: `LI-${i}-${k}`,
    channel: channels[(i + k) % channels.length]!,
    vendor: vendors[(i + k) % vendors.length]!,
    cost: 10000 + ((i * 1373 + k * 211) % 90000),
    impressions: 500_000 + ((i * 9931 + k * 1117) % 4_500_000),
  }));
  const total = lines.reduce((s, l) => s + l.cost, 0);
  return {
    id: `MP-${String(1000 + i)}`,
    campaign_id: `CMP-${String(2000 + (i % 5))}`,
    brand_id: brand, holding_client_id: hc,
    name: `Q${(i % 4) + 1} ${["Brand Lift", "Always-On", "Launch", "Retention"][i % 4]} — ${brand}`,
    status: statuses[i % statuses.length]!,
    total_budget: total, currency: "USD",
    created_at: new Date(2025, i % 12, ((i * 3) % 27) + 1).toISOString(),
    lines,
  };
}
const plans: MediaPlan[] = Array.from({ length: 8 }, (_, i) => plan(i));

const recons: Reconciliation[] = Array.from({ length: 15 }, (_, i) => {
  const p = plans[i % plans.length]!;
  const planned = p.total_budget;
  const actual = Math.round(planned * (0.88 + ((i * 37) % 25) / 100));
  return {
    id: `RC-${String(3000 + i)}`, plan_id: p.id,
    period: `2025-${String((i % 12) + 1).padStart(2, "0")}`,
    planned, actual, variance: actual - planned,
    status: i < 3 ? "pending" : (i === 7 ? "disputed" : "approved"),
    submitted_at: new Date(2025, i % 12, 15).toISOString(),
  };
});

const billings: Billing[] = Array.from({ length: 20 }, (_, i) => {
  const p = plans[i % plans.length]!;
  const line = p.lines[i % p.lines.length]!;
  return {
    id: `BL-${String(4000 + i)}`, plan_id: p.id, vendor: line.vendor,
    amount: line.cost, currency: p.currency,
    status: i < 4 ? "issued" : (i < 14 ? "approved" : "paid"),
    issued_at: new Date(2025, i % 12, ((i * 5) % 27) + 1).toISOString(),
  };
});

const app = express();
app.use(express.json());

app.get("/api/health", (_req, res) => res.json({ ok: true, name: "mediaocean-mcp" }));

app.get("/api/media-plans", (req, res) => {
  let out = plans;
  const { campaign_id, brand_id, status } = req.query as Record<string, string | undefined>;
  if (campaign_id) out = out.filter(p => p.campaign_id === campaign_id);
  if (brand_id) out = out.filter(p => p.brand_id === brand_id);
  if (status) out = out.filter(p => p.status === status);
  res.json({ plans: out });
});

app.get("/api/media-plans/:id", (req, res) => {
  const p = plans.find(x => x.id === req.params.id);
  return p ? res.json(p) : res.status(404).json({ error: "media_plan_not_found" });
});

app.post("/api/media-plans", (req, res) => {
  const body = (req.body ?? {}) as Partial<MediaPlan>;
  const id = `MP-${String(1000 + plans.length)}`;
  const p: MediaPlan = {
    id, campaign_id: body.campaign_id ?? "CMP-2000",
    brand_id: body.brand_id ?? "BR-001", holding_client_id: body.holding_client_id ?? "HC-01",
    name: body.name ?? `Untitled ${id}`, status: "draft",
    total_budget: body.total_budget ?? 0, currency: body.currency ?? "USD",
    created_at: new Date().toISOString(), lines: body.lines ?? [],
  };
  plans.push(p);
  res.status(201).json({ id, status: "draft" });
});

app.patch("/api/media-plans/:id", (req, res) => {
  const p = plans.find(x => x.id === req.params.id);
  if (!p) return res.status(404).json({ error: "media_plan_not_found" });
  const body = (req.body ?? {}) as Partial<MediaPlan>;
  if (body.status) p.status = body.status;
  if (typeof body.total_budget === "number") p.total_budget = body.total_budget;
  if (body.lines) p.lines = body.lines;
  return res.json(p);
});

app.get("/api/reconciliations", (req, res) => {
  const { plan_id, status } = req.query as Record<string, string | undefined>;
  let out = recons;
  if (plan_id) out = out.filter(r => r.plan_id === plan_id);
  if (status) out = out.filter(r => r.status === status);
  res.json({ reconciliations: out });
});

app.post("/api/reconciliations", (req, res) => {
  const body = (req.body ?? {}) as Partial<Reconciliation>;
  if (!body.plan_id) return res.status(400).json({ error: "missing_plan_id" });
  const planned = body.planned ?? 0;
  const actual = body.actual ?? 0;
  const r: Reconciliation = {
    id: `RC-${String(3000 + recons.length)}`, plan_id: body.plan_id,
    period: body.period ?? new Date().toISOString().slice(0, 7),
    planned, actual, variance: actual - planned,
    status: "pending", submitted_at: new Date().toISOString(),
  };
  recons.push(r);
  res.status(201).json({ id: r.id, status: "pending" });
});

app.get("/api/billings", (req, res) => {
  const { plan_id, status, vendor } = req.query as Record<string, string | undefined>;
  let out = billings;
  if (plan_id) out = out.filter(b => b.plan_id === plan_id);
  if (status) out = out.filter(b => b.status === status);
  if (vendor) out = out.filter(b => b.vendor === vendor);
  res.json({ billings: out });
});

app.post("/api/billings", (req, res) => {
  const body = (req.body ?? {}) as Partial<Billing>;
  if (!body.plan_id || !body.vendor || typeof body.amount !== "number") {
    return res.status(400).json({ error: "missing_fields" });
  }
  const b: Billing = {
    id: `BL-${String(4000 + billings.length)}`, plan_id: body.plan_id,
    vendor: body.vendor, amount: body.amount, currency: body.currency ?? "USD",
    status: "draft", issued_at: new Date().toISOString(),
  };
  billings.push(b);
  return res.status(201).json(b);
});

app.post("/api/billings/:id/approve", (req, res) => {
  const b = billings.find(x => x.id === req.params.id);
  if (!b) return res.status(404).json({ error: "billing_not_found" });
  b.status = "approved";
  return res.json(b);
});

const port = Number(process.env["MEDIAOCEAN_MCP_PORT"] ?? 4221);
app.listen(port, () => console.log(`[mediaocean-mcp] listening on ${port}`));
