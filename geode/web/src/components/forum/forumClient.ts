import type { ForumTag } from "@/lib/forum/types";

const NAME_KEY = "geode.forum.displayName";
const ADJECTIVES = ["Measured", "Clear", "Practical", "Steady", "Exact", "Senior"];
const ROLES = ["Counsel", "Operator", "Advisor", "Strategist", "Reviewer", "Lead"];
const RANKS = ["Operator", "Counsel", "Field lead", "Risk chair", "Expert"];

export function getDisplayName(): string {
  const existing = window.localStorage.getItem(NAME_KEY);

  if (existing) {
    return existing;
  }

  const adjective = ADJECTIVES[Math.floor(Math.random() * ADJECTIVES.length)];
  const role = ROLES[Math.floor(Math.random() * ROLES.length)];
  const displayName = `${adjective} ${role}`;
  window.localStorage.setItem(NAME_KEY, displayName);
  return displayName;
}

export function tagLabel(tag: ForumTag): string {
  return tag.replaceAll("-", " ");
}

export function contributorRank(author: string, signal = 0): string {
  const authorScore = author.split("").reduce((total, letter) => total + letter.charCodeAt(0), 0);
  return RANKS[Math.abs(authorScore + signal) % RANKS.length];
}

export function authorInitials(author: string): string {
  const parts = author.trim().split(/\s+/).filter(Boolean);

  if (parts.length === 0) {
    return "GM";
  }

  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }

  return `${parts[0][0]}${parts.at(-1)?.[0] ?? ""}`.toUpperCase();
}

export function authorBio(author: string, role: string): string {
  return `${author} contributes ${role.toLowerCase()} judgment to public regulatory discussions.`;
}

export function authorProfileHref(author: string): string {
  const slug = author
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");

  return `/profiles/${slug || "geode-member"}`;
}

export function activePresence(seed: string): number {
  const score = seed.split("").reduce((total, letter) => total + letter.charCodeAt(0), 0);
  return 7 + (score % 18);
}

export function relativeTime(value: string): string {
  const diffMs = Date.now() - Date.parse(value);
  const minutes = Math.max(1, Math.floor(diffMs / 60_000));

  if (minutes < 60) {
    return `${minutes} ${minutes === 1 ? "minute" : "minutes"}`;
  }

  const hours = Math.floor(minutes / 60);

  if (hours < 24) {
    return `${hours} ${hours === 1 ? "hour" : "hours"}`;
  }

  const days = Math.floor(hours / 24);
  return `${days} ${days === 1 ? "day" : "days"}`;
}

export function preciseTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
    month: "short",
    timeZone: "America/Denver",
    timeZoneName: "short",
  }).format(new Date(value));
}
