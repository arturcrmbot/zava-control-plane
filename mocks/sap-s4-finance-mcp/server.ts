// mocks/sap-s4-finance-mcp/server.ts
//
// SAP S/4 HANA Finance mock — hand-crafted REST surface covering the
// agency-pack workflows (ap-invoice, treasury-fx, intercompany-recharge,
// month-end accruals). Style mirrors mocks/concur-mcp/server.ts but uses
// SAP's idiomatic REST shape (no OAuth on /api — kept demo-simple).
import express from "express";

type Vendor = {
  id: string; name: string; country: string; status: "active" | "blocked";
  payment_terms: string; tax_id: string;
  banking: { iban: string; swift: string; currency: string };
};
type Invoice = {
  id: string; vendor_id: string; currency: string; amount: number;
  posting_status: "pending" | "posted"; created_at: string;
  description: string; gl_doc_id?: string;
};
type GLDoc = { id: string; invoice_id: string; posted_at: string; debit_account: string; credit_account: string; amount: number; currency: string };
type Recharge = { id: string; from_company: string; to_company: string; amount: number; currency: string; memo: string; created_at: string };
type Accrual = { id: string; period: string; account: string; amount: number; currency: string; memo: string; posted_at: string };

const now = () => new Date().toISOString();
const iso = (d: string) => new Date(d).toISOString();

const vendors: Vendor[] = [
  { id: "V-1001", name: "Brightline Studios Ltd", country: "GB", status: "active", payment_terms: "NET30", tax_id: "GB123456789", banking: { iban: "GB29NWBK60161331926819", swift: "NWBKGB2L", currency: "GBP" } },
  { id: "V-1002", name: "Aurora Print & Pack GmbH", country: "DE", status: "active", payment_terms: "NET45", tax_id: "DE811234567", banking: { iban: "DE89370400440532013000", swift: "COBADEFFXXX", currency: "EUR" } },
  { id: "V-1003", name: "Kanto Logistics KK", country: "JP", status: "active", payment_terms: "NET30", tax_id: "JP1234567890123", banking: { iban: "JP00BANK0001234567", swift: "BOTKJPJT", currency: "JPY" } },
  { id: "V-1004", name: "Mumbai Media Services Pvt", country: "IN", status: "active", payment_terms: "NET60", tax_id: "INAAACM1234A", banking: { iban: "IN00ICIC0001234567", swift: "ICICINBB", currency: "INR" } },
  { id: "V-1005", name: "Nordic Cloud AB", country: "SE", status: "active", payment_terms: "NET30", tax_id: "SE556677889901", banking: { iban: "SE3550000000054910000003", swift: "ESSESESS", currency: "EUR" } },
  { id: "V-1006", name: "Pacific Talent LLC", country: "US", status: "active", payment_terms: "NET15", tax_id: "US12-3456789", banking: { iban: "US00CHAS0001234567", swift: "CHASUS33", currency: "USD" } },
  { id: "V-1007", name: "Iberia Translations SL", country: "ES", status: "active", payment_terms: "NET45", tax_id: "ESB12345678", banking: { iban: "ES9121000418450200051332", swift: "CAIXESBB", currency: "EUR" } },
  { id: "V-1008", name: "Toronto Creative Co", country: "CA", status: "blocked", payment_terms: "NET30", tax_id: "CA123456789RT0001", banking: { iban: "CA00ROYC0001234567", swift: "ROYCCAT2", currency: "USD" } },
  { id: "V-1009", name: "Sao Paulo Production Ltda", country: "BR", status: "active", payment_terms: "NET60", tax_id: "BR12.345.678/0001-99", banking: { iban: "BR9700360305000010009795493P1", swift: "ITAUBRSP", currency: "USD" } },
  { id: "V-1010", name: "Sydney Outdoor Media Pty", country: "AU", status: "active", payment_terms: "NET30", tax_id: "AU12345678901", banking: { iban: "AU00CTBA0001234567", swift: "CTBAAU2S", currency: "USD" } },
];

const invoices: Invoice[] = [
  { id: "INV-9001", vendor_id: "V-1001", currency: "GBP", amount: 12450.00, posting_status: "posted", created_at: iso("2026-04-02"), description: "Q1 brand campaign — production", gl_doc_id: "GL-7001" },
  { id: "INV-9002", vendor_id: "V-1002", currency: "EUR", amount: 8800.50, posting_status: "posted", created_at: iso("2026-04-05"), description: "Print run — DE catalogue", gl_doc_id: "GL-7002" },
  { id: "INV-9003", vendor_id: "V-1003", currency: "JPY", amount: 1_240_000, posting_status: "posted", created_at: iso("2026-04-07"), description: "Tokyo launch — logistics", gl_doc_id: "GL-7003" },
  { id: "INV-9004", vendor_id: "V-1004", currency: "INR", amount: 540_000, posting_status: "pending", created_at: iso("2026-04-10"), description: "APAC social retainer" },
  { id: "INV-9005", vendor_id: "V-1005", currency: "EUR", amount: 4200.00, posting_status: "posted", created_at: iso("2026-04-11"), description: "Cloud — analytics tier", gl_doc_id: "GL-7005" },
  { id: "INV-9006", vendor_id: "V-1006", currency: "USD", amount: 18_750.00, posting_status: "pending", created_at: iso("2026-04-15"), description: "Talent agency — Q2 retainer" },
  { id: "INV-9007", vendor_id: "V-1007", currency: "EUR", amount: 2150.75, posting_status: "posted", created_at: iso("2026-04-16"), description: "Translations — ES/PT", gl_doc_id: "GL-7007" },
  { id: "INV-9008", vendor_id: "V-1009", currency: "USD", amount: 9_900.00, posting_status: "pending", created_at: iso("2026-04-18"), description: "Sao Paulo shoot — half day" },
  { id: "INV-9009", vendor_id: "V-1010", currency: "USD", amount: 6_500.00, posting_status: "posted", created_at: iso("2026-04-19"), description: "OOH — Sydney CBD", gl_doc_id: "GL-7009" },
  { id: "INV-9010", vendor_id: "V-1001", currency: "GBP", amount: 3_200.00, posting_status: "posted", created_at: iso("2026-04-22"), description: "Edit revisions — round 2", gl_doc_id: "GL-7010" },
  { id: "INV-9011", vendor_id: "V-1002", currency: "EUR", amount: 1_180.00, posting_status: "pending", created_at: iso("2026-04-24"), description: "Reprint — DE catalogue v2" },
  { id: "INV-9012", vendor_id: "V-1005", currency: "EUR", amount: 8_400.00, posting_status: "posted", created_at: iso("2026-04-25"), description: "Cloud — overage", gl_doc_id: "GL-7012" },
  { id: "INV-9013", vendor_id: "V-1003", currency: "JPY", amount: 480_000, posting_status: "pending", created_at: iso("2026-04-27"), description: "Tokyo — warehousing" },
  { id: "INV-9014", vendor_id: "V-1006", currency: "USD", amount: 12_000.00, posting_status: "pending", created_at: iso("2026-04-28"), description: "Talent — extension fee" },
  { id: "INV-9015", vendor_id: "V-1007", currency: "EUR", amount: 970.00, posting_status: "posted", created_at: iso("2026-04-29"), description: "Translations — legal", gl_doc_id: "GL-7015" },
];

const glDocs: GLDoc[] = invoices
  .filter(i => i.posting_status === "posted")
  .map(i => ({ id: i.gl_doc_id!, invoice_id: i.id, posted_at: i.created_at, debit_account: "5000-EXPENSE", credit_account: "2000-AP", amount: i.amount, currency: i.currency }));

const fxRates: Record<string, number> = {
  "USD/EUR": 0.92, "USD/GBP": 0.79, "USD/JPY": 154.30, "USD/INR": 83.45,
  "EUR/USD": 1.087, "EUR/GBP": 0.859, "GBP/USD": 1.266, "GBP/EUR": 1.164,
  "JPY/USD": 0.00648, "INR/USD": 0.01198,
};

const recharges: Recharge[] = [
  { id: "IC-5001", from_company: "ZAVA-UK", to_company: "ZAVA-DE", amount: 14_200.00, currency: "EUR", memo: "Shared agency — Q1 split", created_at: iso("2026-04-03") },
  { id: "IC-5002", from_company: "ZAVA-US", to_company: "ZAVA-JP", amount: 22_500.00, currency: "USD", memo: "Tokyo launch — central support", created_at: iso("2026-04-12") },
  { id: "IC-5003", from_company: "ZAVA-DE", to_company: "ZAVA-ES", amount: 4_800.00, currency: "EUR", memo: "Translation services pass-through", created_at: iso("2026-04-20") },
];

const accruals: Accrual[] = [];

let invSeq = invoices.length + 1, glSeq = 8000, icSeq = recharges.length + 1, accSeq = 1;

const app = express();
app.use(express.json());

app.get("/api/health", (_req, res) => res.json({ ok: true, name: "sap-s4-finance-mcp" }));

app.get("/api/vendors", (req, res) => {
  let pool = vendors;
  const status = req.query["status"] as string | undefined;
  const country = req.query["country"] as string | undefined;
  if (status) pool = pool.filter(v => v.status === status);
  if (country) pool = pool.filter(v => v.country === country);
  res.json({ vendors: pool });
});

app.get("/api/vendors/:id", (req, res) => {
  const v = vendors.find(x => x.id === req.params.id);
  if (!v) return res.status(404).json({ error: "vendor_not_found" });
  res.json(v);
});

app.get("/api/invoices", (req, res) => {
  let pool = invoices;
  const vendor_id = req.query["vendor_id"] as string | undefined;
  const status = req.query["status"] as string | undefined;
  if (vendor_id) pool = pool.filter(i => i.vendor_id === vendor_id);
  if (status) pool = pool.filter(i => i.posting_status === status);
  res.json({ invoices: pool });
});

app.post("/api/invoices", (req, res) => {
  const { vendor_id, currency, amount, description } = (req.body ?? {}) as Partial<Invoice>;
  if (!vendor_id || !currency || typeof amount !== "number") {
    return res.status(400).json({ error: "missing_fields", required: ["vendor_id", "currency", "amount"] });
  }
  if (!vendors.find(v => v.id === vendor_id)) {
    return res.status(404).json({ error: "vendor_not_found" });
  }
  const id = `INV-${9000 + invSeq++}`;
  const inv: Invoice = { id, vendor_id, currency, amount, description: description ?? "", posting_status: "pending", created_at: now() };
  invoices.push(inv);
  res.status(201).json({ id, posting_status: inv.posting_status });
});

app.post("/api/invoices/:id/post", (req, res) => {
  const inv = invoices.find(i => i.id === req.params.id);
  if (!inv) return res.status(404).json({ error: "invoice_not_found" });
  if (inv.posting_status === "posted") return res.status(409).json({ error: "already_posted", gl_doc_id: inv.gl_doc_id });
  const gl_doc_id = `GL-${glSeq++}`;
  inv.posting_status = "posted";
  inv.gl_doc_id = gl_doc_id;
  glDocs.push({ id: gl_doc_id, invoice_id: inv.id, posted_at: now(), debit_account: "5000-EXPENSE", credit_account: "2000-AP", amount: inv.amount, currency: inv.currency });
  res.json({ gl_doc_id });
});

app.get("/api/gl-documents/:id", (req, res) => {
  const g = glDocs.find(x => x.id === req.params.id);
  if (!g) return res.status(404).json({ error: "gl_doc_not_found" });
  res.json(g);
});

app.get("/api/fx-rates", (_req, res) => res.json({ as_of: now(), rates: fxRates }));

app.post("/api/intercompany-recharges", (req, res) => {
  const { from_company, to_company, amount, currency, memo } = (req.body ?? {}) as Partial<Recharge>;
  if (!from_company || !to_company || typeof amount !== "number" || !currency) {
    return res.status(400).json({ error: "missing_fields", required: ["from_company", "to_company", "amount", "currency"] });
  }
  const id = `IC-${5000 + icSeq++}`;
  const rec: Recharge = { id, from_company, to_company, amount, currency, memo: memo ?? "", created_at: now() };
  recharges.push(rec);
  res.status(201).json(rec);
});

app.post("/api/accruals", (req, res) => {
  const { period, account, amount, currency, memo } = (req.body ?? {}) as Partial<Accrual>;
  if (!period || !account || typeof amount !== "number" || !currency) {
    return res.status(400).json({ error: "missing_fields", required: ["period", "account", "amount", "currency"] });
  }
  const id = `ACC-${6000 + accSeq++}`;
  const acc: Accrual = { id, period, account, amount, currency, memo: memo ?? "", posted_at: now() };
  accruals.push(acc);
  res.status(201).json(acc);
});

const port = Number(process.env["SAP_S4_FINANCE_MCP_PORT"] ?? 4224);
app.listen(port, () => console.log(`[sap-s4-finance-mcp] listening on ${port}`));
