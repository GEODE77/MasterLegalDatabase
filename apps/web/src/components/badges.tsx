import { CheckCircle2, CircleAlert, Database, Scale, ShieldCheck, Sparkles } from "lucide-react";
import { confidencePercent, entityTypeLabel } from "@/lib/format";

export function EntityTypeBadge({ type }: { type: string }) {
  return <span className="badge primary">{entityTypeLabel(type)}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const className = status === "current" || status === "Reviewed" ? "badge green" : "badge amber";
  return (
    <span className={className}>
      <CheckCircle2 className="icon" aria-hidden="true" />
      {status}
    </span>
  );
}

export function ConfidenceBadge({ value }: { value: number }) {
  return (
    <span className="badge teal">
      <ShieldCheck className="icon" aria-hidden="true" />
      {confidencePercent(value)}
    </span>
  );
}

export function SourceBackedBadge({ label = "Official source text" }: { label?: string }) {
  return (
    <span className="source-boundary">
      <Scale className="icon" aria-hidden="true" />
      {label}
    </span>
  );
}

export function MetadataBadge() {
  return (
    <span className="source-boundary">
      <Database className="icon" aria-hidden="true" />
      Geode metadata
    </span>
  );
}

export function AiAssistBadge() {
  return (
    <span className="source-boundary ai-note">
      <Sparkles className="icon" aria-hidden="true" />
      AI assist, not authority
    </span>
  );
}

export function ReviewBadge({ label }: { label: string }) {
  const icon = label.includes("Needs") ? CircleAlert : ShieldCheck;
  const Icon = icon;
  return (
    <span className={label.includes("Needs") ? "badge amber" : "badge green"}>
      <Icon className="icon" aria-hidden="true" />
      {label}
    </span>
  );
}
