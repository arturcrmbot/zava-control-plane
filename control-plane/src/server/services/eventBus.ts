import { EventEmitter } from "node:events";
import type { FleetEvent, FleetEventType } from "@shared/events";

export class EventBus {
  private emitter = new EventEmitter();
  constructor() { this.emitter.setMaxListeners(100); }

  on<T extends FleetEventType>(
    type: T,
    handler: (e: Extract<FleetEvent, { type: T }>) => void
  ): () => void {
    this.emitter.on(type, handler as (e: FleetEvent) => void);
    return () => this.emitter.off(type, handler as (e: FleetEvent) => void);
  }

  onAny(handler: (e: FleetEvent) => void): () => void {
    this.emitter.on("*", handler);
    return () => this.emitter.off("*", handler);
  }

  emit(e: FleetEvent): void {
    this.emitter.emit(e.type, e);
    this.emitter.emit("*", e);
  }
}
