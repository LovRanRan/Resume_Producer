// API 客户端：base URL 来自 NEXT_PUBLIC_API_URL，token（云端部署用）存 localStorage。

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("resume_api_token") ?? "";
}

export function setToken(token: string) {
  localStorage.setItem("resume_api_token", token);
}

function headers(json = true): HeadersInit {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  const token = getToken();
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

async function check(resp: Response): Promise<Response> {
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      detail = (await resp.json()).detail ?? detail;
    } catch {}
    throw new Error(detail);
  }
  return resp;
}

export async function apiGet<T>(path: string): Promise<T> {
  return (await check(await fetch(`${API_BASE}${path}`, { headers: headers(false) }))).json();
}

export async function apiGetText(path: string): Promise<string> {
  return (await check(await fetch(`${API_BASE}${path}`, { headers: headers(false) }))).text();
}

export async function apiSend<T>(path: string, method: string, body: unknown): Promise<T> {
  return (
    await check(
      await fetch(`${API_BASE}${path}`, { method, headers: headers(), body: JSON.stringify(body) })
    )
  ).json();
}

/** 文件类 URL（iframe/下载用）：token 走查询参数。 */
export function fileUrl(path: string): string {
  const token = getToken();
  return `${API_BASE}${path}${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}

export type TailorEvent =
  | { type: "progress"; message: string }
  | ({ type: "result" } & RunSummary)
  | { type: "error"; message: string };

export interface RunSummary {
  run_id: string;
  role_title: string;
  company: string | null;
  pages: number;
  projects: number;
  experience: number;
  bullets: number;
  trimmed: number;
  fallbacks: number;
  keywords_covered: number;
  keywords_total: number;
  cost_usd: number;
  llm_calls: number;
}

/** tailor SSE 流：逐事件回调，直到 result/error。 */
export async function tailorStream(
  candidateId: string,
  body: { jd_text?: string; jd_url?: string },
  onEvent: (e: TailorEvent) => void
): Promise<void> {
  const resp = await check(
    await fetch(`${API_BASE}/api/candidates/${candidateId}/tailor`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(body),
    })
  );
  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)));
      }
    }
  }
}

export interface CandidateSummary {
  id: string;
  name: string;
  education: number;
  experience: number;
  projects: number;
  bullets: number;
}

export interface RunListItem {
  run_id: string;
  role_title?: string;
  company?: string | null;
}
