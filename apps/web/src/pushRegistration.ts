/** Restore only an already-authorized device for the still-current signed-in account. */
export async function restorePushRegistration(ports: {
  current: () => boolean;
  preferences: () => Promise<{ enabled: boolean; push_enabled: boolean }>;
  device: () => Promise<{ token: string; environment: "sandbox" | "production" }>;
  register: (token: string, environment: "sandbox" | "production") => Promise<{ id: string }>;
  remember: (id: string) => void;
}) {
  const preferences = await ports.preferences();
  if (!ports.current() || !preferences.enabled || !preferences.push_enabled) return;
  const device = await ports.device();
  if (!ports.current()) return;
  const result = await ports.register(device.token, device.environment);
  if (ports.current()) ports.remember(result.id);
}
