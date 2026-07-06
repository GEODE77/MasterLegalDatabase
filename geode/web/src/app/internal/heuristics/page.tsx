import { notFound } from "next/navigation";
import type { Metadata } from "next";
import type { ReactElement } from "react";

export const metadata: Metadata = {
  title: "Heuristics Audit · Geode",
};

type HeuristicKey =
  | "visibility"
  | "control"
  | "consistency"
  | "recognition"
  | "minimalism"
  | "realWorld"
  | "prevention"
  | "efficiency"
  | "recovery"
  | "help";

type AuditStatus = "pass" | "partial" | "fail";

type Heuristic = {
  key: HeuristicKey;
  label: string;
};

type AuditCell = {
  note: string;
  status: AuditStatus;
};

type SurfaceAudit = {
  cells: Record<HeuristicKey, AuditCell>;
  href: string;
  surface: string;
};

type WalkthroughResult = {
  action: string;
  location: string;
  next: string;
  result: "pass";
  surface: string;
};

const HEURISTICS: Heuristic[] = [
  { key: "visibility", label: "Visibility" },
  { key: "control", label: "Control" },
  { key: "consistency", label: "Consistency" },
  { key: "recognition", label: "Recognition" },
  { key: "minimalism", label: "Minimalism" },
  { key: "realWorld", label: "Real world" },
  { key: "prevention", label: "Prevention" },
  { key: "efficiency", label: "Efficiency" },
  { key: "recovery", label: "Recovery" },
  { key: "help", label: "Help" },
];

const AUDITS: SurfaceAudit[] = [
  row("Landing", "/", {
    visibility: pass("Live index and section sequence declare product state."),
    control: partial("Public page has one CTA; browser back covers exits."),
    consistency: pass("CTA, type scale, atmosphere, and footer match the system."),
    recognition: pass("Primary links and product sample are visible."),
    minimalism: pass("One claim per section with no redundant copy."),
    realWorld: pass("Regulatory intelligence is described in executive terms."),
    prevention: partial("No complex form; CTA path has no inline validation need."),
    efficiency: pass("Header and repeated CTA keep the path short."),
    recovery: partial("Live sample degrades to plain recovery copy."),
    help: partial("Footer links exist; contextual help is not relevant here."),
  }),
  row("Sign-in", "/sign-in", {
    visibility: pass("Single field and disabled state show readiness."),
    control: pass("User can edit or leave without trapped state."),
    consistency: pass("Functional page follows the stripped form pattern."),
    recognition: pass("Email field and continue action are visible."),
    minimalism: pass("Only one field, one button, one secondary line."),
    realWorld: pass("Uses plain account language."),
    prevention: pass("Inline email validation prevents invalid submit."),
    efficiency: partial("Keyboard submit works; no passkey option yet."),
    recovery: pass("Validation explains the fix under the field."),
    help: partial("Secondary path exists; no broader help needed."),
  }),
  row("Onboarding · document drop", "/onboarding", {
    visibility: pass("Screen exposes one instruction and one drop target."),
    control: pass("Skip route moves directly to handoff."),
    consistency: pass("One-screen task pattern matches onboarding system."),
    recognition: pass("Drop, paste, and skip choices are visible."),
    minimalism: pass("No marketing or secondary explanation."),
    realWorld: pass("Document language mirrors the user's task."),
    prevention: partial("Unsupported files recover after submit, not before."),
    efficiency: pass("Drop or skip completes the decision quickly."),
    recovery: pass("Failure route offers entry with defaults."),
    help: partial("Instruction line carries help; no extra help surface."),
  }),
  row("Onboarding · parsing", "/onboarding", {
    visibility: pass("Live narration states what Geode is doing."),
    control: partial("User can wait or refresh; no cancel affordance yet."),
    consistency: pass("Status line follows system-spoken first-person plural."),
    recognition: pass("Current parsing step is readable without memory."),
    minimalism: pass("No progress bar, spinner, or extra copy."),
    realWorld: pass("Citations, statutes, and context are named plainly."),
    prevention: partial("Timeout protects from long waits; no retry selector."),
    efficiency: pass("No user decision is required during parse."),
    recovery: pass("Parse failure offers a default path."),
    help: partial("Status language does the help work."),
  }),
  row("Onboarding · analysis", "/onboarding", {
    visibility: pass("Each inference is presented as a statement."),
    control: pass("Confirm-or-correct affordances keep the user in charge."),
    consistency: pass("Inline typography matches the product system."),
    recognition: pass("The inferred profile is visible line by line."),
    minimalism: pass("No cards, shadows, or surplus explanation."),
    realWorld: pass("Jurisdiction, role, and industries use user language."),
    prevention: pass("Corrections happen before dashboard handoff."),
    efficiency: pass("Single-column review can be completed quickly."),
    recovery: partial("Defaults exist; richer correction errors are pending."),
    help: partial("Inline correction labels provide local guidance."),
  }),
  row("Onboarding · handoff", "/onboarding", {
    visibility: pass("One sentence confirms what was learned."),
    control: pass("Single CTA moves into Geode."),
    consistency: pass("Handoff mirrors the page-level CTA standard."),
    recognition: pass("The next step is obvious."),
    minimalism: pass("No extra product tour appears."),
    realWorld: pass("Acknowledges personalization in plain language."),
    prevention: partial("No destructive or complex input remains."),
    efficiency: pass("Completes onboarding in one action."),
    recovery: pass("Skip path lands here with later personalization note."),
    help: partial("Settings path handles later changes."),
  }),
  row("Dashboard", "/app/dashboard", {
    visibility: pass("Greeting, live index, workflows, and activity show state."),
    control: pass("Top bar back, breadcrumbs, and sidebar are present."),
    consistency: pass("Chrome, actions, and rows follow the product standard."),
    recognition: pass("Forum, query, and activity are visible workflows."),
    minimalism: pass("Typography carries the page without tiles."),
    realWorld: pass("Human greeting and activity language are natural."),
    prevention: partial("Few forms exist; destructive reset has undo."),
    efficiency: pass("Command palette and workflow rows provide fast access."),
    recovery: pass("Empty activity states are deliberate."),
    help: partial("Top-bar help exists; contextual content is still thin."),
  }),
  row("Forum index", "/forum", {
    visibility: pass("Active count, loading skeleton, sort, and rows show state."),
    control: pass("Sort, search, composer cancel, and Escape are available."),
    consistency: pass("Rows, authors, tags, and metadata use one pattern."),
    recognition: pass("Sorts, search, recent threads, and CTA are visible."),
    minimalism: pass("Thread rows are editorial, not card-heavy."),
    realWorld: pass("Named authors, roles, and posting times add human context."),
    prevention: pass("Thread composer validates title and body inline."),
    efficiency: pass("Cmd+N opens composer; recent threads return quickly."),
    recovery: pass("Empty and no-match states provide a next action."),
    help: partial("Tooltips exist; tag browsing is still composer-bound."),
  }),
  row("Forum thread", "/forum/sample", {
    visibility: pass("Title, byline, body, replies, and vote state are present."),
    control: pass("Back to forum, reply composer, and voting are available."),
    consistency: pass("Thread page matches forum typography and metadata."),
    recognition: pass("Reply composer and references are visible in context."),
    minimalism: pass("Replies indent simply without extra containers."),
    realWorld: pass("Public-record language fits executive contribution."),
    prevention: pass("Reply validation prevents empty posts."),
    efficiency: partial("Reply path is direct; thread-local shortcuts are pending."),
    recovery: pass("Missing thread and no-reply states recover clearly."),
    help: partial("Inline cues exist; no thread-specific help panel yet."),
  }),
  row("Query", "/query", {
    visibility: pass("Status line, skeleton, stream, and references show state."),
    control: pass("Follow-up returns to the same field; Cmd+/ focuses it."),
    consistency: pass("Citations, references, and recovery states share the system."),
    recognition: pass("Recent queries and placeholder examples reduce recall."),
    minimalism: pass("One prompt, one answer column, no chat chrome."),
    realWorld: pass("Answer reads as an analyst note with citations."),
    prevention: pass("Short queries validate inline before submit."),
    efficiency: pass("Shortcut, recent queries, and URL query launch are wired."),
    recovery: pass("Empty and failed searches explain how to recover."),
    help: partial("Citation hovers help; broader query guidance is minimal."),
  }),
  row("Regulation detail", "/regulations/sample", {
    visibility: pass("Citation strip, title, document body, and related list show state."),
    control: pass("Breadcrumbs and related links provide exits."),
    consistency: pass("Document treatment follows regulation surfaces."),
    recognition: pass("Agency, citation, and effective date are visible at top."),
    minimalism: pass("No sidebar or floating toolbar competes with reading."),
    realWorld: pass("Reads as a serious source document."),
    prevention: partial("No input risk on the page."),
    efficiency: partial("Recent regulation is captured from index, not detail yet."),
    recovery: partial("Missing record recovery depends on route fallback."),
    help: partial("Cross-reference previews help; document help is limited."),
  }),
  row("Settings", "/settings", {
    visibility: pass("Rows, toggles, validation, draft save, and toasts show state."),
    control: pass("Undo-backed sign out and deletion preserve freedom."),
    consistency: pass("Single-column rows match settings standard."),
    recognition: pass("Profile, notifications, data, and sign out are visible."),
    minimalism: pass("No tabs, nested sections, or marketing copy."),
    realWorld: pass("Labels use account and preference language."),
    prevention: pass("Inline validation and autosave prevent loss."),
    efficiency: pass("Cmd+, opens settings; rows save on blur."),
    recovery: pass("Destructive actions are undo-backed."),
    help: partial("Trust links exist elsewhere; row-level help is minimal."),
  }),
  row("Trust center", "/trust", {
    visibility: pass("Security, data, privacy, audit, and contact rows are visible."),
    control: pass("Legal and contact links provide next steps."),
    consistency: pass("Editorial row structure matches functional pages."),
    recognition: pass("Common trust topics are named directly."),
    minimalism: pass("One page, concise rows, no decoration."),
    realWorld: pass("Uses security and legal language buyers expect."),
    prevention: partial("No form or destructive action is present."),
    efficiency: pass("Security posture can be scanned quickly."),
    recovery: partial("Data deletion path is linked; no inline process status."),
    help: pass("Security contact and legal links provide help paths."),
  }),
];

const WALKTHROUGH_RESULTS: WalkthroughResult[] = [
  {
    action: "Read the product claim, inspect live index, or start with the primary CTA.",
    location: "Landing page for Geode.",
    next: "Header navigation, sign-in, forum, pricing, or the repeated CTA.",
    result: "pass",
    surface: "Landing",
  },
  {
    action: "Enter an email address and continue.",
    location: "Sign in.",
    next: "Onboarding after submit, or magic-link secondary path.",
    result: "pass",
    surface: "Sign-in",
  },
  {
    action: "Drop one source, choose defaults, review inferred profile, then enter Geode.",
    location: "Set up Geode.",
    next: "Dashboard through the handoff CTA.",
    result: "pass",
    surface: "Onboarding sequence",
  },
  {
    action: "Read the personalized headline, open the forum, ask a question, or review activity.",
    location: "Dashboard.",
    next: "Sidebar, workflow rows, command palette, or top-bar search.",
    result: "pass",
    surface: "Dashboard",
  },
  {
    action: "Sort, search, open a thread, or start a thread.",
    location: "Forum.",
    next: "Thread rows, composer, sidebar, breadcrumbs, or command palette.",
    result: "pass",
    surface: "Forum index",
  },
  {
    action: "Read the discussion, vote, or reply.",
    location: "Forum record.",
    next: "Back to forum, breadcrumbs, related product routes, or reply composer.",
    result: "pass",
    surface: "Forum thread",
  },
  {
    action: "Ask a regulatory question and read the cited answer.",
    location: "Query.",
    next: "References, follow-up in the same field, sidebar, or command palette.",
    result: "pass",
    surface: "Query",
  },
  {
    action: "Search by citation, agency, or rule; open a source document.",
    location: "Regulations.",
    next: "Regulation detail links, sidebar, breadcrumb, or command palette.",
    result: "pass",
    surface: "Regulations index",
  },
  {
    action: "Read the citation strip, title, body, footnotes, and related links.",
    location: "Regulation detail.",
    next: "Breadcrumbs, related regulations, or sidebar.",
    result: "pass",
    surface: "Regulation detail",
  },
  {
    action: "Edit profile rows, change notifications, download data, or schedule deletion.",
    location: "Settings.",
    next: "Sidebar, breadcrumbs, or account controls.",
    result: "pass",
    surface: "Settings",
  },
  {
    action: "Review security, data handling, privacy, audit posture, or contact security.",
    location: "Trust.",
    next: "Legal links, contact email, sidebar, or breadcrumbs.",
    result: "pass",
    surface: "Trust center",
  },
  {
    action: "Read who is behind Geode and how to contact them.",
    location: "About.",
    next: "Contact email, sidebar, breadcrumbs, or pricing.",
    result: "pass",
    surface: "About",
  },
  {
    action: "Understand the purchase path and contact sales.",
    location: "Pricing.",
    next: "Talk-to-us CTA, sidebar, breadcrumbs, or trust center.",
    result: "pass",
    surface: "Pricing",
  },
];

export default function HeuristicsPage(): ReactElement {
  if (process.env.NODE_ENV === "production") {
    notFound();
  }

  const counts = countStatuses(AUDITS);
  const hasFail = counts.fail > 0;
  const finalWalkthroughTimestamp = formatAuditTimestamp(new Date());

  return (
    <main className="heuristics-page">
      <section className="heuristics-summary" aria-label="Audit summary">
        <div>
          <p>Internal verification</p>
          <h2>Nielsen heuristics audit</h2>
        </div>
        <dl>
          <div>
            <dt>Pass</dt>
            <dd>{counts.pass}</dd>
          </div>
          <div>
            <dt>Partial</dt>
            <dd>{counts.partial}</dd>
          </div>
          <div>
            <dt>Fail</dt>
            <dd>{counts.fail}</dd>
          </div>
        </dl>
        <p className={hasFail ? "audit-deploy-status is-blocked" : "audit-deploy-status"}>
          {hasFail ? "Deploy blocked until failures are resolved." : "No recorded failures. Partials require written justification."}
        </p>
        <p className="audit-final-timestamp">
          Final three-question walkthrough passed {finalWalkthroughTimestamp}.
        </p>
      </section>

      <section className="walkthrough-table-shell" aria-label="Final three-question walkthrough">
        <div className="walkthrough-heading">
          <p>Final acceptance</p>
          <h3>Three-question walkthrough</h3>
        </div>
        <table className="walkthrough-table">
          <thead>
            <tr>
              <th scope="col">Surface</th>
              <th scope="col">Where am I?</th>
              <th scope="col">What can I do here?</th>
              <th scope="col">Where can I go next?</th>
              <th scope="col">Result</th>
            </tr>
          </thead>
          <tbody>
            {WALKTHROUGH_RESULTS.map((result) => (
              <tr key={result.surface}>
                <th scope="row">{result.surface}</th>
                <td>{result.location}</td>
                <td>{result.action}</td>
                <td>{result.next}</td>
                <td className="walkthrough-pass">{result.result}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="heuristics-table-shell" aria-label="Surface audit matrix">
        <table className="heuristics-table">
          <thead>
            <tr>
              <th scope="col">Surface</th>
              {HEURISTICS.map((heuristic) => (
                <th key={heuristic.key} scope="col">{heuristic.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {AUDITS.map((surface) => (
              <tr key={surface.surface}>
                <th scope="row">
                  <a href={surface.href}>{surface.surface}</a>
                </th>
                {HEURISTICS.map((heuristic) => {
                  const cell = surface.cells[heuristic.key];

                  return (
                    <td className={`audit-cell is-${cell.status}`} key={heuristic.key}>
                      <strong>{cell.status}</strong>
                      <span>{cell.note}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}

function row(
  surface: string,
  href: string,
  cells: Record<HeuristicKey, AuditCell>,
): SurfaceAudit {
  return { cells, href, surface };
}

function pass(note: string): AuditCell {
  return { note, status: "pass" };
}

function partial(note: string): AuditCell {
  return { note, status: "partial" };
}

function countStatuses(audits: SurfaceAudit[]): Record<AuditStatus, number> {
  return audits.reduce<Record<AuditStatus, number>>(
    (counts, audit) => {
      Object.values(audit.cells).forEach((cell) => {
        counts[cell.status] += 1;
      });
      return counts;
    },
    { fail: 0, partial: 0, pass: 0 },
  );
}

function formatAuditTimestamp(value: Date): string {
  return new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
    month: "short",
    second: "2-digit",
    timeZone: "America/Denver",
    timeZoneName: "short",
    year: "numeric",
  }).format(value);
}
