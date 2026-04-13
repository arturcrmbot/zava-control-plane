export class AuditLogger {
    entries = [];
    log(entry) {
        this.entries.push(entry);
    }
    list() {
        return this.entries.slice();
    }
}
