import { describe, expect, it } from "vitest";
import { mapWorldScene } from "../worldScene";

describe("mapWorldScene", () => {
  it("maps configured collections into positioned actor tokens and journal animations", () => {
    const scene = {
      version: "1",
      title: "Operations map",
      locations: [
        { id: "north-yard", label: "North Yard", x: 0.1, y: 0.2 },
        { id: "south-yard", label: "South Yard", x: 0.9, y: 0.8 },
      ],
      actor_bindings: [
        {
          collection: "units",
          kind: "unit",
          id_field: "unitId",
          state_field: "condition",
          position: { location_field: "siteId" },
        },
        {
          collection: "sensors",
          kind: "sensor",
          id_field: "id",
          state_field: "mode",
          position: { x_field: "mapX", y_field: "mapY" },
        },
        {
          collection: "shipments",
          kind: "shipment",
          id_field: "id",
          state_field: "status",
          position: { route_field: "route", progress_field: "progress" },
        },
      ],
      event_mappings: [
        { event_type: "shipment.departed", animation_type: "depart", actor_id_field: "actor_id" },
      ],
    };

    const result = mapWorldScene(scene, {
      units: [{ unitId: "unit-17", label: "Unit Seventeen", condition: "ready", siteId: "north-yard" }],
      sensors: [{ id: "sensor-2", name: "Sensor Two", mode: "active", mapX: 0.42, mapY: 0.58 }],
      shipments: [{ id: "shipment-8", label: "Shipment Eight", status: "moving", route: ["north-yard", "south-yard"], progress: 0.25 }],
    }, [
      {
        seq: 4,
        event_id: "event-4",
        type: "shipment.departed",
        actor_id: "shipment-8",
        target_id: null,
        payload: {},
      },
    ]);

    expect(result.locations).toEqual(scene.locations);
    expect(result.actors).toEqual([
      expect.objectContaining({
        id: "unit-17", label: "Unit Seventeen", kind: "unit", state: "ready",
        locationId: "north-yard", x: 0.1, y: 0.2,
      }),
      expect.objectContaining({
        id: "sensor-2", label: "Sensor Two", kind: "sensor", state: "active",
        x: 0.42, y: 0.58,
      }),
      expect.objectContaining({
        id: "shipment-8", label: "Shipment Eight", kind: "shipment", state: "moving",
        route: ["north-yard", "south-yard"], progress: 0.25, x: 0.3, y: 0.35,
      }),
    ]);
    expect(result.animations).toEqual([
      { eventId: "event-4", actorId: "shipment-8", animation: "depart", seq: 4 },
    ]);
  });

  it("separates co-located actor tokens without changing their location identity", () => {
    const scene = {
      version: "1",
      title: "Operations map",
      locations: [{ id: "home", label: "Operations hub", x: 0.5, y: 0.5 }],
      actor_bindings: [
        {
          collection: "bookings",
          kind: "booking",
          id_field: "id",
          state_field: "status",
          position: { location_field: "current_location_id" },
        },
        {
          collection: "workflows",
          kind: "workflow",
          id_field: "id",
          state_field: "status",
          position: { location_field: "current_location_id" },
        },
        {
          collection: "parties",
          kind: "party",
          id_field: "id",
          state_field: "status",
          position: { location_field: "current_location_id" },
        },
      ],
      event_mappings: [],
    };
    const snapshot = {
      bookings: [{ id: "BKG-4", status: "reaccommodated", current_location_id: "home" }],
      workflows: [{ id: "fdr-evt-157", status: "completed", current_location_id: "home" }],
      parties: [{ id: "PTY-4", status: "reaccommodated", current_location_id: "home" }],
    };

    const first = mapWorldScene(scene, snapshot, []);
    const second = mapWorldScene(scene, snapshot, []);
    const positions = first.actors.map((actor) => `${actor.x},${actor.y}`);

    expect(first.actors.every((actor) => actor.locationId === "home")).toBe(true);
    expect(new Set(positions).size).toBe(3);
    expect(second.actors).toEqual(first.actors);
  });
});
