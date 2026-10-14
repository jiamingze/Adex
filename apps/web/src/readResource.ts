/** A session-local UI projection, never durable task state or a write retry queue. */
export function createReadResource<T>(
  read: (signal: AbortSignal) => Promise<T>,
  { timeoutMs = 8000, freshMs = 15000 } = {},
) {
  type Snapshot = { data: T | null; loading: boolean; error: unknown };
  let snapshot: Snapshot = { data: null, loading: false, error: null };
  let epoch = 0;
  let loadedAt = 0;
  let pending: Promise<T> | null = null;
  let controller: AbortController | null = null;
  const listeners = new Set<() => void>();
  const publish = (next: Snapshot) => {
    snapshot = next;
    listeners.forEach((listener) => listener());
  };
  function invalidate(keepData = false) {
    epoch++;
    controller?.abort();
    controller = null;
    pending = null;
    loadedAt = 0;
    publish({
      data: keepData ? snapshot.data : null,
      loading: false,
      error: null,
    });
  }
  function load(force = false): Promise<T> {
    if (pending) return pending;
    if (!force && snapshot.data !== null && Date.now() - loadedAt < freshMs)
      return Promise.resolve(snapshot.data);
    const attempt = epoch;
    const abort = new AbortController();
    controller = abort;
    publish({ ...snapshot, loading: true, error: null });
    let timer: ReturnType<typeof setTimeout>;
    let onAbort: () => void;
    // Race also bounds native transports which ignore AbortSignal. Late responses
    // cannot commit after an auth change, invalidation or expired read deadline.
    const deadline = new Promise<never>((_, reject) => {
      onAbort = () => reject(new Error("READ_CANCELLED"));
      abort.signal.addEventListener("abort", onAbort, { once: true });
      timer = setTimeout(() => {
        reject(new Error("READ_TIMEOUT"));
        abort.abort();
      }, timeoutMs);
    });
    pending = Promise.race([
      Promise.resolve().then(() => read(abort.signal)),
      deadline,
    ])
      .then((data) => {
        if (attempt !== epoch) throw new Error("READ_CANCELLED");
        loadedAt = Date.now();
        publish({ data, loading: false, error: null });
        return data;
      })
      .catch((error) => {
        if (attempt === epoch) publish({ ...snapshot, loading: false, error });
        throw error;
      })
      .finally(() => {
        clearTimeout(timer);
        abort.signal.removeEventListener("abort", onAbort);
        if (attempt === epoch) {
          pending = null;
          controller = null;
        }
      });
    return pending;
  }
  return {
    /** Only call with an authoritative response, never an optimistic write. */
    accept: (data: T) => {
      invalidate(true);
      loadedAt = Date.now();
      publish({ data, loading: false, error: null });
    },
    getSnapshot: () => snapshot,
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    load,
    invalidate,
    reset: () => invalidate(false),
  };
}
