export function replaceOrAppendById<T extends { id: string }>(
  items: T[],
  item: T,
): T[] {
  const index = items.findIndex((current) => current.id === item.id);
  if (index < 0) return [...items, item];
  return items.map((current, currentIndex) =>
    currentIndex === index ? item : current,
  );
}
