interface ValidationIssue {
  msg?: string;
}

interface ErrorBody {
  detail?: string | ValidationIssue[];
}

export function errorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") {
    return fallback;
  }
  const detail = (body as ErrorBody).detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const message = detail.find((issue) => typeof issue?.msg === "string")?.msg;
    if (message) {
      return message;
    }
  }
  return fallback;
}
