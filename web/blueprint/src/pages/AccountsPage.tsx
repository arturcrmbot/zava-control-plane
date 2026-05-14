import { useEffect, useState } from "react";

interface AccountRow {
  id: string;
  code: string;
  name: string;
  type: string;
  total_gbp: number;
  row_count: number;
  cost_centres: string[];
}

interface SummaryResponse {
  accounts: AccountRow[];
}

interface BrandRow {
  brand_id: string;
  brand_name: string;
  client_name: string | null;
  total_gbp: number;
  row_count: number;
}

interface BrandSummary {
  brands: BrandRow[];
}

const fmtGBP = (n: number) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 }).format(n);

export function AccountsPage() {
  const [data, setData] = useState<SummaryResponse | null>(null);
  const [brandData, setBrandData] = useState<BrandSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/accounts/summary")
      .then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
      .then(d => { if (!cancelled) setData(d); })
      .catch(e => { if (!cancelled) setError(String(e)); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/accounts/by-brand")
      .then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
      .then(d => { if (!cancelled) setBrandData(d); })
      .catch(() => { /* tile is optional — silent fail keeps page usable */ });
    return () => { cancelled = true; };
  }, []);

  if (error) return <div className="accounts-page__error">accounts unavailable: {error}</div>;
  if (!data) return <div className="accounts-page__loading">loading…</div>;

  const grouped: Record<string, AccountRow[]> = {};
  for (const a of data.accounts) {
    (grouped[a.type] ??= []).push(a);
  }

  return (
    <div className="accounts-page">
      <header className="accounts-page__header">
        <div className="accounts-page__eyebrow">live ledger</div>
        <h1>Accounts</h1>
      </header>
      {brandData?.brands?.length ? (
        <section className="accounts-page__group">
          <h2 className="accounts-page__group-title">Spend by brand</h2>
          <table className="accounts-page__table">
            <thead>
              <tr><th>Brand</th><th>Client</th><th className="num">Rows</th><th className="num">Total</th></tr>
            </thead>
            <tbody>
              {brandData.brands.map(b => (
                <tr key={b.brand_id}>
                  <td>{b.brand_name}</td>
                  <td>{b.client_name ?? "—"}</td>
                  <td className="num">{b.row_count}</td>
                  <td className="num">{fmtGBP(b.total_gbp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
      {(["revenue", "expense", "intercompany", "other"] as const).map(t => (
        grouped[t]?.length ? (
          <section key={t} className="accounts-page__group">
            <h2 className="accounts-page__group-title">
              {t === "revenue" ? "Revenue" : t === "expense" ? "Expenses" : t === "intercompany" ? "Intercompany" : "Other"}
            </h2>
            <table className="accounts-page__table">
              <thead>
                <tr><th>Code</th><th>Account</th><th className="num">Rows</th><th className="num">Total</th></tr>
              </thead>
              <tbody>
                {grouped[t].map(a => (
                  <tr key={a.id}>
                    <td className="mono">{a.code}</td>
                    <td>{a.name}</td>
                    <td className="num">{a.row_count}</td>
                    <td className="num">{fmtGBP(a.total_gbp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : null
      ))}
    </div>
  );
}
