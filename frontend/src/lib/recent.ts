const STORAGE_KEY_PREFIX = "aicte.command_recent";
const LEGACY_STORAGE_KEY = "aicte.command_recent";
const MAX_ITEMS = 6;

function storageKey(userId: string): string {
  return `${STORAGE_KEY_PREFIX}.${userId}`;
}

export type RecentItemType = "page" | "application" | "institution";

export interface RecentItem {
  type: RecentItemType;
  id: string;
  label: string;
  detail?: string;
  to: string;
}

function isRecentItem(value: unknown): value is RecentItem {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const item = value as Record<string, unknown>;
  return (
    (item.type === "page" ||
      item.type === "application" ||
      item.type === "institution") &&
    typeof item.id === "string" &&
    typeof item.label === "string" &&
    typeof item.to === "string" &&
    (item.detail === undefined || typeof item.detail === "string")
  );
}

export function getRecentItems(userId: string): RecentItem[] {
  try {
    window.localStorage.removeItem(LEGACY_STORAGE_KEY);
    const stored = window.localStorage.getItem(storageKey(userId));
    if (!stored) {
      return [];
    }
    const parsed: unknown = JSON.parse(stored);
    return Array.isArray(parsed) ? parsed.filter(isRecentItem).slice(0, MAX_ITEMS) : [];
  } catch {
    return [];
  }
}

export function rememberRecentItem(userId: string, item: RecentItem): RecentItem[] {
  const next = [
    item,
    ...getRecentItems(userId).filter(
      (existing) => !(existing.type === item.type && existing.id === item.id),
    ),
  ].slice(0, MAX_ITEMS);
  try {
    window.localStorage.setItem(storageKey(userId), JSON.stringify(next));
  } catch {
    // Storage can be unavailable in private mode; recents are optional.
  }
  return next;
}
