// mocks/kinesso-mcp/server.ts
//
// Kinesso (IPG Mediabrands) mock — data clean room + audience surface used
// by the agency vertical pack. Returns aggregate counts only on clean-room
// queries (mirrors the privacy posture of the real product).
import express from "express";
import { randomUUID } from "node:crypto";

type Audience = {
  audience_id: string;
  brand_id: string;
  name: string;
  type: "first_party" | "modelled" | "third_party" | "lookalike";
  size: number;
  freshness_hours: number;
  segments: string[];
};
type CleanRoom = {
  clean_room_id: string;
  name: string;
  parties: [string, string];
  brand_id: string;
  created_at: string;
  approved_query_ids: string[];
};
type CleanRoomQuery = {
  query_id: string;
  clean_room_id: string;
  sql: string;
  submitted_by: string;
  submitted_at: string;
  status: "approved" | "pending" | "denied";
  result?: { row_count: number; aggregate: Record<string, number> };
};

// Seed — ~8 audiences across the agency pack's brand ids, ~3 clean rooms
// (one per top holding client). Brand ids match the b4 generator's
// "brand-<slug>" convention.
const audiences: Audience[] = [
  { audience_id: "aud-001", brand_id: "brand-northwind-grocers", name: "NW Grocers — loyalty repeat 90d", type: "first_party", size: 412_000, freshness_hours: 6, segments: ["loyalty", "grocery", "uk"] },
  { audience_id: "aud-002", brand_id: "brand-northwind-grocers", name: "NW Grocers — lapsed 180d lookalike", type: "lookalike", size: 1_840_000, freshness_hours: 24, segments: ["lapsed", "grocery", "uk"] },
  { audience_id: "aud-003", brand_id: "brand-fabrikam-fashion", name: "Fabrikam — Gen-Z streetwear intent", type: "modelled", size: 2_120_000, freshness_hours: 12, segments: ["gen-z", "fashion", "us"] },
  { audience_id: "aud-004", brand_id: "brand-fabrikam-fashion", name: "Fabrikam — VIP CRM (hashed)", type: "first_party", size: 88_500, freshness_hours: 2, segments: ["vip", "crm", "global"] },
  { audience_id: "aud-005", brand_id: "brand-contoso-finance", name: "Contoso — SMB decision-makers", type: "third_party", size: 540_000, freshness_hours: 48, segments: ["b2b", "smb", "finance"] },
  { audience_id: "aud-006", brand_id: "brand-contoso-finance", name: "Contoso — wealth retention modelled", type: "modelled", size: 215_000, freshness_hours: 18, segments: ["wealth", "retention"] },
  { audience_id: "aud-007", brand_id: "brand-adventure-works", name: "AdventureWorks — outdoor enthusiasts DACH", type: "third_party", size: 980_000, freshness_hours: 36, segments: ["outdoor", "dach", "lifestyle"] },
  { audience_id: "aud-008", brand_id: "brand-tailspin-toys", name: "Tailspin — gifting-season parents", type: "modelled", size: 1_310_000, freshness_hours: 8, segments: ["parents", "seasonal", "us"] },
];

const cleanRooms: CleanRoom[] = [
  { clean_room_id: "cr-001", name: "Zava × Northwind Grocers — loyalty overlap", parties: ["zava-data", "northwind-grocers"], brand_id: "brand-northwind-grocers", created_at: "2026-04-08T09:12:00Z", approved_query_ids: ["q-001", "q-002"] },
  { clean_room_id: "cr-002", name: "Zava × Fabrikam Fashion — measurement", parties: ["zava-data", "fabrikam-fashion"], brand_id: "brand-fabrikam-fashion", created_at: "2026-04-15T14:30:00Z", approved_query_ids: ["q-003"] },
  { clean_room_id: "cr-003", name: "Zava × Contoso Finance — propensity", parties: ["zava-data", "contoso-finance"], brand_id: "brand-contoso-finance", created_at: "2026-04-22T11:05:00Z", approved_query_ids: [] },
];

const queries: CleanRoomQuery[] = [
  { query_id: "q-001", clean_room_id: "cr-001", sql: "SELECT COUNT(*) FROM overlap WHERE loyalty_tier='gold'", submitted_by: "planner@zava.example", submitted_at: "2026-04-08T10:01:00Z", status: "approved", result: { row_count: 1, aggregate: { overlap_count: 38_400 } } },
  { query_id: "q-002", clean_room_id: "cr-001", sql: "SELECT region, COUNT(*) FROM overlap GROUP BY region", submitted_by: "planner@zava.example", submitted_at: "2026-04-09T08:44:00Z", status: "approved", result: { row_count: 4, aggregate: { london: 14_200, manchester: 9_800, leeds: 6_400, glasgow: 8_000 } } },
  { query_id: "q-003", clean_room_id: "cr-002", sql: "SELECT COUNT(*) FROM exposed_buyers WHERE campaign='ss26'", submitted_by: "measurement@zava.example", submitted_at: "2026-04-16T16:20:00Z", status: "approved", result: { row_count: 1, aggregate: { exposed_buyers: 51_200 } } },
];

const app = express();
app.use(express.json());

app.get("/api/health", (_req, res) => res.json({ ok: true, name: "kinesso-mcp" }));

app.get("/api/audiences", (req, res) => {
  const brand = req.query["brand_id"] as string | undefined;
  const type = req.query["type"] as string | undefined;
  let pool = audiences;
  if (brand) pool = pool.filter(a => a.brand_id === brand);
  if (type) pool = pool.filter(a => a.type === type);
  res.json({ audiences: pool });
});

app.get("/api/audiences/:id", (req, res) => {
  const a = audiences.find(x => x.audience_id === req.params.id);
  if (!a) return res.status(404).json({ error: "audience_not_found" });
  res.json(a);
});

app.post("/api/audiences", (req, res) => {
  const b = req.body ?? {};
  if (!b.brand_id || !b.name || !b.type) {
    return res.status(400).json({ error: "missing_fields" });
  }
  const created: Audience = {
    audience_id: "aud-" + randomUUID().slice(0, 8),
    brand_id: String(b.brand_id),
    name: String(b.name),
    type: b.type,
    size: Number(b.size ?? 0),
    freshness_hours: 0,
    segments: Array.isArray(b.segments) ? b.segments.map(String) : [],
  };
  audiences.push(created);
  res.status(201).json(created);
});

app.get("/api/clean-rooms", (_req, res) => res.json({ clean_rooms: cleanRooms }));

app.post("/api/clean-rooms", (req, res) => {
  const b = req.body ?? {};
  if (!Array.isArray(b.parties) || b.parties.length !== 2 || !b.name) {
    return res.status(400).json({ error: "two_parties_and_name_required" });
  }
  const created: CleanRoom = {
    clean_room_id: "cr-" + randomUUID().slice(0, 8),
    name: String(b.name),
    parties: [String(b.parties[0]), String(b.parties[1])],
    brand_id: String(b.brand_id ?? ""),
    created_at: new Date().toISOString(),
    approved_query_ids: [],
  };
  cleanRooms.push(created);
  res.status(201).json(created);
});

app.get("/api/clean-rooms/:id/queries", (req, res) => {
  const cr = cleanRooms.find(x => x.clean_room_id === req.params.id);
  if (!cr) return res.status(404).json({ error: "clean_room_not_found" });
  res.json({ queries: queries.filter(q => q.clean_room_id === cr.clean_room_id) });
});

app.post("/api/clean-rooms/:id/queries", (req, res) => {
  const cr = cleanRooms.find(x => x.clean_room_id === req.params.id);
  if (!cr) return res.status(404).json({ error: "clean_room_not_found" });
  const b = req.body ?? {};
  if (!b.sql || !b.submitted_by) return res.status(400).json({ error: "sql_and_submitter_required" });
  // Always returns aggregate counts only — never row-level data. The mock
  // synthesises a deterministic aggregate so downstream agents can chain.
  const overlap = 1000 + (String(b.sql).length * 137) % 90_000;
  const created: CleanRoomQuery = {
    query_id: "q-" + randomUUID().slice(0, 8),
    clean_room_id: cr.clean_room_id,
    sql: String(b.sql),
    submitted_by: String(b.submitted_by),
    submitted_at: new Date().toISOString(),
    status: "approved",
    result: { row_count: 1, aggregate: { overlap_count: overlap } },
  };
  queries.push(created);
  cr.approved_query_ids.push(created.query_id);
  res.status(201).json(created);
});

app.get("/api/addressability/:audience_id", (req, res) => {
  const a = audiences.find(x => x.audience_id === req.params.audience_id);
  if (!a) return res.status(404).json({ error: "audience_not_found" });
  // Channel breakdown is deterministic per audience id so demos repeat.
  const seed = a.audience_id.split("").reduce((s, c) => s + c.charCodeAt(0), 0);
  const ctv = 35 + (seed % 20);
  const display = 25 + ((seed * 3) % 15);
  const social = 20 + ((seed * 7) % 15);
  const search = Math.max(0, 100 - ctv - display - social);
  const addressable_pct = Math.min(95, 60 + (seed % 30));
  res.json({
    audience_id: a.audience_id,
    addressable_pct,
    addressable_size: Math.round(a.size * (addressable_pct / 100)),
    channels: { ctv, display, social, search },
  });
});

const port = Number(process.env["KINESSO_MCP_PORT"] ?? 4223);
app.listen(port, () => console.log(`[kinesso-mcp] listening on ${port}`));
