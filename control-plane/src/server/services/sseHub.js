export class SSEHub {
    clients = new Map();
    subscribe(topic, res) {
        res.setHeader("Content-Type", "text/event-stream");
        res.setHeader("Cache-Control", "no-cache");
        res.setHeader("Connection", "keep-alive");
        res.flushHeaders();
        const set = this.clients.get(topic) ?? new Set();
        set.add(res);
        this.clients.set(topic, set);
        res.on("close", () => set.delete(res));
    }
    broadcast(topic, data) {
        const s = this.clients.get(topic);
        if (!s)
            return;
        const payload = `data: ${JSON.stringify(data)}\n\n`;
        for (const r of s) {
            try {
                r.write(payload);
            }
            catch { /* drop */ }
        }
    }
}
