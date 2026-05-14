import { describe, it, expect } from "vitest";
import {
  aggregateCities,
  applyLod,
  AGGREGATION_THRESHOLD,
  LOD_DISTANCE_THRESHOLD,
  type AggregatableCity,
  type AggregatedCity,
} from "../cityAggregation";

function person(id: string, department: string): AggregatableCity {
  return { id, kind: "person_row", label: id, entity_kind: "Person", department } as AggregatableCity;
}

function org(id: string, subkind: string): AggregatableCity {
  return { id, kind: "org_row", label: id, entity_kind: "Organisation", subkind } as AggregatableCity;
}

describe("aggregateCities", () => {
  it("returns small input unchanged (no aggregation under the threshold)", () => {
    const cities: AggregatableCity[] = [
      person("p1", "Finance"),
      person("p2", "Finance"),
      person("p3", "HR"),
    ];
    const out = aggregateCities(cities);
    expect(out).toHaveLength(3);
    expect(out.every((c) => !("aggregated" in c))).toBe(true);
  });

  it("groups large Person input by department", () => {
    const finance = Array.from({ length: AGGREGATION_THRESHOLD + 5 }, (_, i) =>
      person(`pf${i}`, "Finance"),
    );
    const hr = Array.from({ length: 3 }, (_, i) => person(`ph${i}`, "HR"));
    const out = aggregateCities([...finance, ...hr]);

    const aggregated = out.filter((c): c is AggregatedCity => "aggregated" in c && c.aggregated);
    expect(aggregated).toHaveLength(1);
    expect(aggregated[0].id).toBe("agg:Person/Finance");
    expect(aggregated[0].label).toMatch(/Finance Team \(\d+\)/);
    expect(aggregated[0].members).toHaveLength(finance.length);

    // HR group stayed individual — under threshold.
    const hrCities = out.filter((c) => !("aggregated" in c) || !(c as AggregatedCity).aggregated);
    expect(hrCities).toHaveLength(3);
  });

  it("groups large Organisation input by kind", () => {
    const vendors = Array.from({ length: AGGREGATION_THRESHOLD + 1 }, (_, i) =>
      org(`v${i}`, "vendor"),
    );
    const out = aggregateCities(vendors);
    const aggregated = out.filter((c): c is AggregatedCity => "aggregated" in c && c.aggregated);
    expect(aggregated).toHaveLength(1);
    expect(aggregated[0].id).toBe("agg:Organisation/vendor");
    expect(aggregated[0].label).toMatch(/Vendors \(\d+\)/);
  });

  it("leaves unsupported kinds unchanged regardless of size", () => {
    const decisions: AggregatableCity[] = Array.from(
      { length: AGGREGATION_THRESHOLD + 10 },
      (_, i) => ({ id: `d${i}`, kind: "decision_row", label: `d${i}`, entity_kind: "Decision" } as AggregatableCity),
    );
    const out = aggregateCities(decisions);
    expect(out).toHaveLength(decisions.length);
    expect(out.every((c) => !("aggregated" in c))).toBe(true);
  });
});

describe("applyLod", () => {
  it("passes everything through when the camera is close", () => {
    const cities: AggregatableCity[] = Array.from({ length: 100 }, (_, i) => ({
      id: `c${i}`,
      kind: "x",
      label: `c${i}`,
      recent_activity_per_min: i,
    }));
    const out = applyLod(cities, LOD_DISTANCE_THRESHOLD - 0.1);
    expect(out).toHaveLength(100);
  });

  it("keeps only the top-N most-active cities when zoomed out", () => {
    const cities: AggregatableCity[] = Array.from({ length: 100 }, (_, i) => ({
      id: `c${i}`,
      kind: "x",
      label: `c${i}`,
      recent_activity_per_min: i,
    }));
    const out = applyLod(cities, LOD_DISTANCE_THRESHOLD + 5, 10);
    expect(out).toHaveLength(10);
    // Highest-activity ids should be present (c95..c99 etc.).
    expect(out.map((c) => c.id).sort()).toContain("c99");
  });
});
