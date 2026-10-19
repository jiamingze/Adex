/** Native GET avoids Capacitor's WebView GET proxy; cancellation ignores late native replies. */
type Bridge = {
  request(options: {
    url: string;
    method: string;
    headers: Record<string, string>;
    responseType: "json";
    connectTimeout: number;
    readTimeout: number;
  }): Promise<{
    status: number;
    data: unknown;
    headers: Record<string, string>;
  }>;
};
export async function nativeJsonRead(
  url: string,
  headers: Record<string, string>,
  signal: AbortSignal | undefined,
  bridge: Bridge,
): Promise<Response> {
  if (signal?.aborted) throw new DOMException("Read cancelled", "AbortError");
  let cancel: (() => void) | undefined;
  const cancelled = new Promise<never>((_, reject) => {
    cancel = () => reject(new DOMException("Read cancelled", "AbortError"));
    signal?.addEventListener("abort", cancel, { once: true });
  });
  try {
    const value = await Promise.race([
      bridge.request({
        url,
        method: "GET",
        headers,
        responseType: "json",
        connectTimeout: 10000,
        readTimeout: 20000,
      }),
      cancelled,
    ]);
    return new Response(
      value.status === 204 ? null : JSON.stringify(value.data),
      { status: value.status, headers: { "Content-Type": "application/json" } },
    );
  } finally {
    if (cancel) signal?.removeEventListener("abort", cancel);
  }
}
