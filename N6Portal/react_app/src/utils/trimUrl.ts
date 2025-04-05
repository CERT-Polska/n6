export function trimUrl(trimLength: number, url: string): string {
  const str = String(url);

  if (str.length <= trimLength) {
    return str;
  }
  if (trimLength <= 0) {
    return '...';
  }
  return `${str.substring(0, trimLength)}...`;
}
