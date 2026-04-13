import { EventEmitter } from "node:events";
export class EventBus {
    emitter = new EventEmitter();
    constructor() { this.emitter.setMaxListeners(100); }
    on(type, handler) {
        this.emitter.on(type, handler);
        return () => this.emitter.off(type, handler);
    }
    onAny(handler) {
        this.emitter.on("*", handler);
        return () => this.emitter.off("*", handler);
    }
    emit(e) {
        this.emitter.emit(e.type, e);
        this.emitter.emit("*", e);
    }
}
