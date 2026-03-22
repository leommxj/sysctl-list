export function formatAvailabilityRange(tags: string[], latestTag: string): string {
  if (!tags.length) {
    return "Unavailable";
  }
  const first = tags[0];
  const last = tags[tags.length - 1];
  if (first === last) {
    return first;
  }
  return `${first}-${last === latestTag ? "latest" : last}`;
}
