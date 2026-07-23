const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export async function apiRequest<T>(
  path: string,
  method: string = "GET",
  token?: string,
  body?: unknown,
  isForm: boolean = false
): Promise<T> {
  const headers: Record<string, string> = {};
  if (!isForm) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${apiBase}${path}`, {
    method,
    headers,
    body: body ? (isForm ? (body as BodyInit) : JSON.stringify(body)) : undefined
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export function asJsonObject(input: string): Record<string, unknown> {
  if (!input.trim()) {
    return {};
  }
  return JSON.parse(input) as Record<string, unknown>;
}
