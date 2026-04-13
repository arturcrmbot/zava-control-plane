export interface AuditEntry {
  action: string;
  details: unknown;
  timestamp: number;
}

export class AuditLogger {
  private entries: AuditEntry[] = [];

  log(entry: AuditEntry): void {
    this.entries.push(entry);
  }

  list(): AuditEntry[] {
    return this.entries.slice();
  }
}
