export const toTitleCase = (str: string) => {
  if (!str) return "";
  str = str.toLowerCase();
  return str.replace(/\b\w/g, (char) => char.toUpperCase());
};
