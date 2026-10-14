export type ChatPosition = { top: number; bottom: boolean };
export function createChatPositions() {
  const positions = new Map<string, ChatPosition>();
  return {
    get: (id: string) => positions.get(id),
    record: (id: string, top: number, height: number, viewport: number) => {
      if (!id) return;
      if (!positions.has(id) && positions.size >= 100)
        positions.delete(positions.keys().next().value!);
      positions.set(id, {
        top: Math.max(0, top),
        bottom: height - top - viewport < 100,
      });
    },
    clear: () => positions.clear(),
  };
}
