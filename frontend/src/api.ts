const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface JobSubmitted {
  job_id: string;
  session_id: string;
  status: string;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  escalated: boolean;
  awaiting_confirmation: boolean;
  tool_calls: string[];
  blocked: boolean;
  block_reason: string;
}

export interface JobResult {
  job_id: string;
  status: "queued" | "in_progress" | "complete" | "not_found" | "failed";
  result?: ChatResponse;
  error?: string;
}

function authHeaders(apiKey: string): Record<string, string> {
  return {
    "Content-Type": "application/json",
    ...(apiKey ? { "X-Api-Key": apiKey } : {}),
  };
}

export async function sendMessage(
  message: string,
  sessionId: string | null,
  apiKey: string
): Promise<JobSubmitted> {
  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: authHeaders(apiKey),
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function pollResult(jobId: string, apiKey: string): Promise<JobResult> {
  const res = await fetch(`${API_BASE_URL}/result/${jobId}`, {
    headers: authHeaders(apiKey),
  });
  if (!res.ok) throw new Error(`Poll failed: ${res.status}`);
  return res.json();
}

/** Poll until the job is complete or failed, with a configurable max-wait. */
export async function waitForResult(
  jobId: string,
  apiKey: string,
  intervalMs = 1000,
  maxMs = 90_000
): Promise<JobResult> {
  const deadline = Date.now() + maxMs;
  while (Date.now() < deadline) {
    const result = await pollResult(jobId, apiKey);
    if (result.status === "complete" || result.status === "failed" || result.status === "not_found") {
      return result;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Timed out waiting for agent response");
}

/** Synchronous path — used for quick dev/testing without a worker running. */
export async function sendMessageSync(
  message: string,
  sessionId: string | null,
  apiKey: string
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE_URL}/chat/sync`, {
    method: "POST",
    headers: authHeaders(apiKey),
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function mintToken(userId: string, tenantId: string, apiKey: string): Promise<string> {
  const res = await fetch(`${API_BASE_URL}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, tenant_id: tenantId, scopes: ["chat"], api_key: apiKey }),
  });
  if (!res.ok) throw new Error(`Token request failed: ${res.status}`);
  const data = await res.json();
  return data.access_token;
}
