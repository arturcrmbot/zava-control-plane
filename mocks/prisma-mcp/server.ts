// mocks/prisma-mcp/server.ts
//
// Prisma (Mediaocean) media-buying mock — buying orders, supplier invoices,
// and three-way match against the order. In-memory state only; the surface
// mirrors the agency-pack patterns described in
// plan/feature-enterprise-pitch-readiness-1.md (track F).
import express from "express";

type OrderStatus = "open" | "placed" | "delivered" | "reconciled";
type BuyingOrder = {
  id: string;
  vendor_id: string;
  brand: string;
  campaign: string;
  channel: string;
  amount: number;
  currency: string;
  status: OrderStatus;
  created_at: string;
};
type SupplierInvoice = {
  id: string;
  vendor_id: string;
  order_id: string | null;
  amount: number;
  currency: string;
  matched: boolean;
  match_variance?: number;
  submitted_at: string;
};

const now = () => new Date().toISOString();

const seedOrders: BuyingOrder[] = [
  ["bo-001", "vnd-meta",     "Aurora",  "spring-launch",  "social",   42000, "open"],
  ["bo-002", "vnd-google",   "Aurora",  "spring-launch",  "search",   28000, "placed"],
  ["bo-003", "vnd-tiktok",   "Nimbus",  "always-on",      "social",   15000, "delivered"],
  ["bo-004", "vnd-itv",      "Nimbus",  "q2-tv-burst",    "tv",      120000, "reconciled"],
  ["bo-005", "vnd-channel4", "Halo",    "q2-tv-burst",    "tv",       64000, "delivered"],
  ["bo-006", "vnd-spotify",  "Halo",    "podcast-test",   "audio",     8500, "placed"],
  ["bo-007", "vnd-meta",     "Vertex",  "retargeting",    "social",   17500, "open"],
  ["bo-008", "vnd-tradedesk","Vertex",  "programmatic",   "display",  46000, "placed"],
  ["bo-009", "vnd-google",   "Lumen",   "yt-pre-roll",    "video",    33000, "delivered"],
  ["bo-010", "vnd-amazon",   "Lumen",   "amazon-dsp",     "display",  21000, "reconciled"],
  ["bo-011", "vnd-pinterest","Aurora",  "lower-funnel",   "social",    9200, "open"],
  ["bo-012", "vnd-tradedesk","Halo",    "ctv-upper",      "ctv",      55000, "placed"],
].map(([id, vendor_id, brand, campaign, channel, amount, status]) => ({
  id: id as string,
  vendor_id: vendor_id as string,
  brand: brand as string,
  campaign: campaign as string,
  channel: channel as string,
  amount: amount as number,
  currency: "GBP",
  status: status as OrderStatus,
  created_at: now(),
}));

const seedInvoices: SupplierInvoice[] = [
  ["si-001", "vnd-meta",      "bo-001",  42000, true,   0],
  ["si-002", "vnd-google",    "bo-002",  28000, true,   0],
  ["si-003", "vnd-tiktok",    "bo-003",  15750, false,  750],
  ["si-004", "vnd-itv",       "bo-004", 120000, true,   0],
  ["si-005", "vnd-channel4",  "bo-005",  64000, true,   0],
  ["si-006", "vnd-spotify",   null,       8500, false,  0],
  ["si-007", "vnd-tradedesk", "bo-008",  46900, false,  900],
  ["si-008", "vnd-google",    "bo-009",  33000, true,   0],
  ["si-009", "vnd-amazon",    "bo-010",  21000, true,   0],
  ["si-010", "vnd-unknown",   null,       4200, false,  0],
].map(([id, vendor_id, order_id, amount, matched, variance]) => ({
  id: id as string,
  vendor_id: vendor_id as string,
  order_id: order_id as string | null,
  amount: amount as number,
  currency: "GBP",
  matched: matched as boolean,
  match_variance: variance as number,
  submitted_at: now(),
}));

const orders: BuyingOrder[] = [...seedOrders];
const invoices: SupplierInvoice[] = [...seedInvoices];

const app = express();
app.use(express.json());

app.get("/api/health", (_req, res) => res.json({ ok: true, name: "prisma-mcp" }));

app.get("/api/buying-orders", (req, res) => {
  const { vendor_id, status } = req.query as { vendor_id?: string; status?: string };
  let pool = orders;
  if (vendor_id) pool = pool.filter(o => o.vendor_id === vendor_id);
  if (status) pool = pool.filter(o => o.status === status);
  res.json({ orders: pool });
});

app.post("/api/buying-orders", (req, res) => {
  const body = (req.body ?? {}) as Partial<BuyingOrder>;
  if (!body.vendor_id || !body.brand || typeof body.amount !== "number") {
    return res.status(400).json({ error: "missing_fields" });
  }
  const id = `bo-${String(orders.length + 1).padStart(3, "0")}`;
  const order: BuyingOrder = {
    id,
    vendor_id: body.vendor_id,
    brand: body.brand,
    campaign: body.campaign ?? "ad-hoc",
    channel: body.channel ?? "unspecified",
    amount: body.amount,
    currency: body.currency ?? "GBP",
    status: "open",
    created_at: now(),
  };
  orders.push(order);
  res.status(201).json({ id, status: order.status });
});

app.patch("/api/buying-orders/:id", (req, res) => {
  const order = orders.find(o => o.id === req.params.id);
  if (!order) return res.status(404).json({ error: "order_not_found" });
  const next = (req.body ?? {}).status as OrderStatus | undefined;
  const allowed: OrderStatus[] = ["open", "placed", "delivered", "reconciled"];
  if (!next || !allowed.includes(next)) {
    return res.status(400).json({ error: "invalid_status", allowed });
  }
  order.status = next;
  res.json({ id: order.id, status: order.status });
});

app.get("/api/supplier-invoices", (req, res) => {
  const { vendor_id, matched } = req.query as { vendor_id?: string; matched?: string };
  let pool = invoices;
  if (vendor_id) pool = pool.filter(i => i.vendor_id === vendor_id);
  if (matched === "true") pool = pool.filter(i => i.matched);
  if (matched === "false") pool = pool.filter(i => !i.matched);
  res.json({ invoices: pool });
});

app.post("/api/supplier-invoices", (req, res) => {
  const body = (req.body ?? {}) as Partial<SupplierInvoice>;
  if (!body.vendor_id || typeof body.amount !== "number") {
    return res.status(400).json({ error: "missing_fields" });
  }
  const id = `si-${String(invoices.length + 1).padStart(3, "0")}`;
  const inv: SupplierInvoice = {
    id,
    vendor_id: body.vendor_id,
    order_id: body.order_id ?? null,
    amount: body.amount,
    currency: body.currency ?? "GBP",
    matched: false,
    match_variance: 0,
    submitted_at: now(),
  };
  invoices.push(inv);
  res.status(201).json({ id, matched: false });
});

// Three-way match: invoice ↔ buying order ↔ delivery (delivery is implicit
// here — we treat status >= "delivered" as goods-received). Tolerance 1%.
app.post("/api/supplier-invoices/:id/match", (req, res) => {
  const inv = invoices.find(i => i.id === req.params.id);
  if (!inv) return res.status(404).json({ error: "invoice_not_found" });
  const orderId = ((req.body ?? {}).order_id as string | undefined) ?? inv.order_id;
  if (!orderId) return res.status(400).json({ error: "no_order_reference" });
  const order = orders.find(o => o.id === orderId);
  if (!order) return res.status(404).json({ error: "order_not_found" });
  if (order.vendor_id !== inv.vendor_id) {
    return res.status(409).json({ error: "vendor_mismatch" });
  }
  if (order.status !== "delivered" && order.status !== "reconciled") {
    return res.status(409).json({ error: "goods_not_received", order_status: order.status });
  }
  const variance = inv.amount - order.amount;
  const tolerance = order.amount * 0.01;
  const matched = Math.abs(variance) <= tolerance;
  inv.order_id = orderId;
  inv.matched = matched;
  inv.match_variance = variance;
  if (matched) order.status = "reconciled";
  res.json({ id: inv.id, matched, variance, order_status: order.status });
});

app.get("/api/reconciliation-status", (_req, res) => {
  const order_status: Record<OrderStatus, number> = {
    open: 0, placed: 0, delivered: 0, reconciled: 0,
  };
  for (const o of orders) order_status[o.status]++;
  const matched = invoices.filter(i => i.matched).length;
  res.json({
    order_status,
    invoices: { total: invoices.length, matched, unmatched: invoices.length - matched },
  });
});

const port = Number(process.env["PRISMA_MCP_PORT"] ?? 4222);
app.listen(port, () => console.log(`[prisma-mcp] listening on ${port}`));
