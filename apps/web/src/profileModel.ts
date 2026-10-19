/** Login identifiers stay stable; display names are text and may be cleared. */
export function accountDisplayName(
  username: string,
  nickname?: string | null,
  guest = false,
) {
  return guest ? "访客" : nickname?.trim() || username;
}
