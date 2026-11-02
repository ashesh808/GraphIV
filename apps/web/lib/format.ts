/** Display helpers shared by the library and report reader. */
export function cleanTitle(value: string): string {
  return value
    .replace(/\$([^$]*)\$/g, "$1")
    .replace(/\\(?:text|mathrm|mathbf|emph|textit|textbf|underline)\{([^}]*)\}/g, "$1")
    .replace(/[{}\\]/g, "")
    .trim();
}

export function formatDate(value: string, options?: Intl.DateTimeFormatOptions): string {
  if (!value) return "Date unavailable";
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00Z` : value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "UTC",
        ...options,
      }).format(date);
}

export function capitalize(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "Unspecified";
}

export function formatAuthors(value: string): string {
  const authors = cleanTitle(value).split(/,\s*|\s+and\s+/).filter(Boolean);
  return authors.length > 3 ? `${authors.slice(0, 3).join(", ")} et al.` : authors.join(", ");
}

export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "Not recorded";
  const rounded = Math.round(seconds);
  return rounded < 60 ? `${rounded}s` : `${Math.floor(rounded / 60)}m ${rounded % 60}s`;
}

export function formatIntentConfidence(score?: number): string {
  if (score === undefined || !Number.isFinite(score) || score < 0 || score > 1) return "";
  const percentage = new Intl.NumberFormat("en", { style: "percent", maximumFractionDigits: 1 }).format(score);
  return `${percentage} confidence · precomputed prediction`;
}
