export type ImprovementCategory =
  | "Manager access"
  | "Data pipeline"
  | "Public product"
  | "Manager dashboard"
  | "Trust and safety"
  | "Quality and reliability";

export type ImprovementRecord = {
  audit: string;
  category: ImprovementCategory;
  completed: string;
  furtherAttention: string;
  id: number;
  status: "satisfactory" | "needs_followup";
  title: string;
};

export const IMPROVEMENT_REGISTRY: ImprovementRecord[] = [
  {
    audit: "Admin accounts now show access age, activity status, and review flags in one place.",
    category: "Manager access",
    completed: "Added manager access review signals for inactive, older, and revoked accounts.",
    furtherAttention: "Add calendar reminders when real manager volume grows.",
    id: 1,
    status: "satisfactory",
    title: "Manager access review",
  },
  {
    audit: "First-admin creation is separated from normal invite creation and refuses to run when managers exist.",
    category: "Manager access",
    completed: "Added a controlled first-admin setup path for an empty manager registry.",
    furtherAttention: "Move this into a deployment-only setup screen when hosting is finalized.",
    id: 2,
    status: "satisfactory",
    title: "First admin setup path",
  },
  {
    audit: "The manager dashboard can now report whether the production session secret is present.",
    category: "Manager access",
    completed: "Added a visible production session secret readiness check for manager operations.",
    furtherAttention: "Runtime status is now visible in the publication safety controls.",
    id: 3,
    status: "satisfactory",
    title: "Production session secret checklist",
  },
  {
    audit: "Manager events are visible in the admin screen and exportable as a permanent audit file.",
    category: "Manager access",
    completed: "Expanded manager activity into a clearer review and export record.",
    furtherAttention: "Add filters once the activity log becomes large.",
    id: 4,
    status: "satisfactory",
    title: "Manager action log screen",
  },
  {
    audit: "Public users are routed toward search, library, and source information without a sign-in demand.",
    category: "Public product",
    completed: "Separated public resource paths from verified manager paths.",
    furtherAttention: "Replace remaining marketing language with source-first language over time.",
    id: 5,
    status: "satisfactory",
    title: "Public user path cleanup",
  },
  {
    audit: "Source watcher status is summarized with current, changed, blocked, and review-needed counts.",
    category: "Data pipeline",
    completed: "Added an automated source watcher dashboard summary for managers.",
    furtherAttention: "Connect live network probes for any source still using manual markers.",
    id: 6,
    status: "satisfactory",
    title: "Automated source watcher dashboard",
  },
  {
    audit: "Managers can see the approval boundary before broad downloads proceed.",
    category: "Data pipeline",
    completed: "Added a download approval gate summary with risk, source, and workspace checks.",
    furtherAttention: "Turn approval into a signed action before remote execution is enabled.",
    id: 7,
    status: "satisfactory",
    title: "Download approval gate",
  },
  {
    audit: "Closeout checks now appear as a single release decision instead of scattered notes.",
    category: "Data pipeline",
    completed: "Added a download closeout report covering secrets, downloads, dashboard, and Git.",
    furtherAttention: "Persist one closeout snapshot after each future download.",
    id: 8,
    status: "satisfactory",
    title: "Download closeout report",
  },
  {
    audit: "Queue items can be ranked by age so long-running blockers stop being invisible.",
    category: "Data pipeline",
    completed: "Added blocked item aging fields and priority language to review queue output.",
    furtherAttention: "Queue age now falls back to the real queue generation time when first-seen dates are missing.",
    id: 9,
    status: "satisfactory",
    title: "Blocked item aging",
  },
  {
    audit: "Queue ownership is represented in manager-facing review records.",
    category: "Data pipeline",
    completed: "Added repair ownership fields and manager notes for blocked work.",
    furtherAttention: "Managers can now edit queue owner, status, notes, and source confirmation.",
    id: 10,
    status: "satisfactory",
    title: "Repair queue ownership",
  },
  {
    audit: "Repair records now distinguish official-source confirmation from intake completion.",
    category: "Data pipeline",
    completed: "Added official source confirmation records for repaired documents.",
    furtherAttention: "Require file-level reviewer signoff before replacing official archives.",
    id: 11,
    status: "satisfactory",
    title: "Official source confirmation records",
  },
  {
    audit: "The modern LegiScan repair set is tracked separately from historical archive issues.",
    category: "Data pipeline",
    completed: "Added a modern LegiScan progress summary with repaired, waiting, blocked, and reviewed counts.",
    furtherAttention: "Repair progress is now separated and manager-editable through the review queue.",
    id: 12,
    status: "satisfactory",
    title: "Modern LegiScan repair progress",
  },
  {
    audit: "The public first path now emphasizes search and browsing instead of internal operations.",
    category: "Public product",
    completed: "Added a simpler public homepage path toward usable legal resources.",
    furtherAttention: "Do a full visual redesign after the legal library is populated further.",
    id: 13,
    status: "satisfactory",
    title: "Simple public homepage",
  },
  {
    audit: "Legal layers can be shown as a plain library instead of a file tree.",
    category: "Public product",
    completed: "Added a public legal data library model for all major source layers.",
    furtherAttention: "Add deeper browse pages for each layer.",
    id: 14,
    status: "satisfactory",
    title: "Clear legal data library",
  },
  {
    audit: "Source cards now explain contents, freshness, and confidence at a glance.",
    category: "Public product",
    completed: "Added plain-language source card content for public and manager review.",
    furtherAttention: "Add source-owner logos only after public asset rights are confirmed.",
    id: 15,
    status: "satisfactory",
    title: "Plain-language source cards",
  },
  {
    audit: "Search guidance now prioritizes CRS, CCR, bill, executive order, agency, and topic entries.",
    category: "Public product",
    completed: "Added citation-first search routing language.",
    furtherAttention: "Add autocomplete after citation indexes are optimized.",
    id: 16,
    status: "satisfactory",
    title: "Citation-first search",
  },
  {
    audit: "Freshness status is surfaced with each layer and source decision.",
    category: "Public product",
    completed: "Added freshness warning language for current, stale, blocked, and review-needed results.",
    furtherAttention: "Search results now carry per-result freshness status and detail.",
    id: 17,
    status: "satisfactory",
    title: "Freshness warnings",
  },
  {
    audit: "Result explanations identify citation, agency, topic, or relationship reasons.",
    category: "Public product",
    completed: "Added why-this-result explanation language to the product model.",
    furtherAttention: "Live search results now include a why-this-result explanation.",
    id: 18,
    status: "satisfactory",
    title: "Why am I seeing this explanation",
  },
  {
    audit: "The manager home now centers the four operational signals that matter first.",
    category: "Manager dashboard",
    completed: "Added manager home summary for sources, reviews, downloads, and publication readiness.",
    furtherAttention: "Turn each metric into a direct filtered drilldown.",
    id: 19,
    status: "satisfactory",
    title: "Manager home summary",
  },
  {
    audit: "Manager tasks are grouped into a single inbox-style action list.",
    category: "Manager dashboard",
    completed: "Added a task inbox model for current manager action.",
    furtherAttention: "Queue items now have editable assignment, status, and completion controls.",
    id: 20,
    status: "satisfactory",
    title: "Manager task inbox",
  },
  {
    audit: "Publication now has a plain readiness decision instead of log searching.",
    category: "Manager dashboard",
    completed: "Expanded publication readiness into a final checklist view.",
    furtherAttention: "Require explicit admin approval before production release.",
    id: 21,
    status: "satisfactory",
    title: "Publication readiness screen",
  },
  {
    audit: "Source checks can now be read chronologically by expected and recent activity.",
    category: "Manager dashboard",
    completed: "Added a source operations calendar model.",
    furtherAttention: "A source probe script and source automation schedule are now present.",
    id: 22,
    status: "satisfactory",
    title: "Source operations calendar",
  },
  {
    audit: "Manager note fields are represented on source and queue records.",
    category: "Manager dashboard",
    completed: "Added manager notes for source issues, blocked downloads, and repair items.",
    furtherAttention: "Manager notes are editable and attributed through manager queue actions.",
    id: 23,
    status: "satisfactory",
    title: "Manager notes",
  },
  {
    audit: "Admin account controls now include create, revoke, review, export, and access review signals.",
    category: "Manager dashboard",
    completed: "Expanded admin-only account controls.",
    furtherAttention: "Add role editing and invite resend only after email delivery is added.",
    id: 24,
    status: "satisfactory",
    title: "Admin-only account controls",
  },
  {
    audit: "Secret safety runs before commits and the manager surfaces now show it as a release control.",
    category: "Trust and safety",
    completed: "Kept secret safety visible across commit, push, download, and export controls.",
    furtherAttention: "Add scheduled full-repo scans once automation is enabled.",
    id: 25,
    status: "satisfactory",
    title: "Secret safety everywhere",
  },
  {
    audit: "Sensitive file warnings are represented before staging or publication.",
    category: "Trust and safety",
    completed: "Added sensitive-file warning language to the publication safety model.",
    furtherAttention: "Add a dedicated warning endpoint if browser-based staging is added.",
    id: 26,
    status: "satisfactory",
    title: "Sensitive file warnings",
  },
  {
    audit: "Public release checks now include manager-only and temporary-file boundaries.",
    category: "Trust and safety",
    completed: "Added a public data boundary check.",
    furtherAttention: "Run it automatically before production deploys.",
    id: 27,
    status: "satisfactory",
    title: "Public data boundary check",
  },
  {
    audit: "Raw archive protection is shown as a release rule and pipeline invariant.",
    category: "Trust and safety",
    completed: "Added raw archive protection warnings.",
    furtherAttention: "Add a file watcher once downloads run as hosted jobs.",
    id: 28,
    status: "satisfactory",
    title: "Raw archive protection",
  },
  {
    audit: "Manager exports now include file names, timestamps, exporter identity, and schema version.",
    category: "Trust and safety",
    completed: "Added manager export controls and export audit records.",
    furtherAttention: "Add CSV export only if human reviewers prefer spreadsheet review.",
    id: 29,
    status: "satisfactory",
    title: "Manager export controls",
  },
  {
    audit: "Pipeline state is readable by layer: downloaded, archived, parsed, indexed, crosswalked, and published.",
    category: "Quality and reliability",
    completed: "Added a readable audit dashboard model for pipeline progress.",
    furtherAttention: "Layer audit rows now include exact readable file counts.",
    id: 30,
    status: "satisfactory",
    title: "Readable audit dashboard",
  },
  {
    audit: "Relationship health is summarized for statute, regulation, bill, agency, and rulemaking links.",
    category: "Quality and reliability",
    completed: "Added a crosswalk health screen model.",
    furtherAttention: "Managers can now review crosswalk files with missing-evidence and low-confidence counts.",
    id: 31,
    status: "satisfactory",
    title: "Crosswalk health screen",
  },
  {
    audit: "Confidence can now be summarized by completeness, freshness, validation, and unresolved failures.",
    category: "Quality and reliability",
    completed: "Added a data confidence score model.",
    furtherAttention: "Confidence scoring now includes records, queue issues, stale layers, and relationship issues.",
    id: 32,
    status: "satisfactory",
    title: "Data confidence score",
  },
  {
    audit: "Failures are grouped by source, cause, and next action in the manager view.",
    category: "Quality and reliability",
    completed: "Added pipeline error grouping model.",
    furtherAttention: "Pipeline errors are grouped from the active source queue and surfaced in quality controls.",
    id: 33,
    status: "satisfactory",
    title: "Pipeline error grouping",
  },
  {
    audit: "Known permanent blockers are separated from new failures.",
    category: "Quality and reliability",
    completed: "Added a known blocker registry model.",
    furtherAttention: "Continue reconfirming known blockers on a scheduled basis.",
    id: 34,
    status: "satisfactory",
    title: "Known blocker registry",
  },
  {
    audit: "Validation output can now be presented as plain manager-readable reports.",
    category: "Quality and reliability",
    completed: "Added human-readable validation report summaries.",
    furtherAttention: "Attach each future validation command output to the report.",
    id: 35,
    status: "satisfactory",
    title: "Human-readable validation reports",
  },
];

export function improvementSummary(): {
  completed: number;
  needsFollowup: number;
  satisfactory: number;
  total: number;
} {
  return {
    completed: IMPROVEMENT_REGISTRY.length,
    needsFollowup: IMPROVEMENT_REGISTRY.filter((item) => item.status === "needs_followup").length,
    satisfactory: IMPROVEMENT_REGISTRY.filter((item) => item.status === "satisfactory").length,
    total: IMPROVEMENT_REGISTRY.length,
  };
}

export function improvementsByCategory(): Array<{
  category: ImprovementCategory;
  items: ImprovementRecord[];
}> {
  const categories: ImprovementCategory[] = [
    "Manager access",
    "Data pipeline",
    "Public product",
    "Manager dashboard",
    "Trust and safety",
    "Quality and reliability",
  ];

  return categories.map((category) => ({
    category,
    items: IMPROVEMENT_REGISTRY.filter((item) => item.category === category),
  }));
}
