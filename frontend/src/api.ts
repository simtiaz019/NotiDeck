export type Row = Record<string, any>;
export function csrfToken() {
  return (
    document.cookie
      .split("; ")
      .find((x) => x.startsWith("nd_csrf="))
      ?.split("=")
      .slice(1)
      .join("=") || ""
  );
}
export async function api(
  path: string,
  method = "GET",
  body?: unknown,
  token?: string,
) {
  const response = await fetch("/api/v1" + path, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken(),
      ...(token ? { "X-Bootstrap-Token": token } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.error?.message +
        (data.error?.fields
          ? ": " +
            data.error.fields
              .map((f: Row) => f.location.join(".") + " " + f.message)
              .join("; ")
          : ""),
    );
  return data;
}
