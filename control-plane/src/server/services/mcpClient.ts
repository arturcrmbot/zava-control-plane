// src/server/services/mcpClient.ts
export async function callMcp(
  baseUrl: string,
  tool: string,
  args: Record<string, unknown>
): Promise<unknown> {
  const res = await fetch(`${baseUrl}/mcp/call/${tool}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(args)
  });
  if (!res.ok) throw new Error(`mcp ${tool} failed: ${res.status}`);
  return res.json();
}
