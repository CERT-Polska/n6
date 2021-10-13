export const trimUrl = (trimLength: number, url: string): string => {
  if (url.length <= trimLength) return url;
  return `${url.substring(0, trimLength)}...`;
};
