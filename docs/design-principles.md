# Geode Design Principles

This document is the canonical reference for every design and frontend decision in Geode. Codex reads it at the start of every session before touching any file. Every principle below is grounded in documented usability research and proven patterns from high-performing B2B intelligence products. None of it is opinion.

When a decision conflicts with this document, this document wins. When the document is silent, defer to the documented patterns of Linear, Notion, Stripe, and Hebbia in that order.

---

## Part One — Foundational Principles

### 1. Visibility of System Status

Users must always know where they are, what is happening, and what just happened.

**Timing standards.**
- Under 0.1 seconds: feels instant, no feedback needed.
- 0.1 to 1 second: show a loading state.
- 1 to 10 seconds: show progress with percentage.
- Over 10 seconds: show detailed progress and estimated time remaining.

**Required elements.**
- A persistent indicator of current location on every page (active sidebar item, breadcrumb, page title).
- Skeleton placeholders that match the final layout on every data fetch. Never blank screens. Never generic spinners.
- Toast confirmations after every successful action: "Thread posted," "Settings saved," "Vote recorded."
- A precise timestamp on every live data anchor, updated on each backend poll. Format: "Updated 14:32:18 MT."

---

### 2. User Control and Freedom (the Back Button Principle)

Users make mistakes. They need clearly marked exits from every state.

**Required elements.**
- A back chevron in the top-left of every page below the dashboard root, sized 44×44 pixels for hit target.
- Breadcrumbs in the top bar showing the full path from sidebar root to current page. Every segment is clickable.
- Undo toasts after every destructive action, persisting for 10 seconds. "Post deleted · Undo."
- Cancel as a secondary text button on every form and modal. Never just an X icon.
- Escape closes any modal, dialog, or overlay.
- Browser-back behavior works correctly on every route.

---

### 3. Consistency and Standards

Same icon means same thing. Same word means same action. Same pattern in same location every time.

**Required elements.**
- A magnifying glass means search everywhere. A trash can means delete everywhere. A gear means settings everywhere.
- Primary actions on the right of forms and modals. Cancel on the left.
- Account access in the top right of the top bar.
- Form submission at the bottom of the form.
- Sidebar navigation when the product has six or more primary sections.
- Top bar for global context: search, account, notifications, breadcrumb.

---

### 4. Recognition Rather Than Recall

Minimize the user's memory load. Make options, actions, and information visible.

**Required elements.**
- The sidebar always shows every primary section. No hamburger menus on desktop.
- The top bar shows the user's name and current workspace at all times.
- Recent regulations, recent queries, and followed threads appear in dedicated rails on the dashboard.
- Autocomplete on every search input, with recent searches and suggested completions.

---

### 5. Aesthetic and Minimalist Design (Proportion, Not Cramping)

Minimal does not mean cramped. Hierarchy, spacing, and rhythm are non-negotiable.

**Typographic scale.** Use only these sizes: 12, 14, 16, 20, 24, 32, 48, 64. No font sizes between these values.

**Vertical rhythm.** 8-pixel baseline. Every margin and padding is a multiple of 8. Section spacing is 64 pixels minimum. Paragraph spacing is 16 pixels. List item spacing is 12 pixels.

**Display type.** 64-pixel display type is reserved for one anchor element per page maximum.

**Body type.** 16 pixels with 1.6 line height for reading.

**Metadata.** 12 pixels in monospace with letter-spacing 0.06em, uppercase.

**Numbers in live data displays.** Sized proportionally to information value. The headline metric at 64 pixels. Variant metrics at 24 pixels. Sparkline value labels at 14 pixels monospace. No oversized numbers as decoration.

---

### 6. Match Between System and the Real World (Human Elements)

The interface acknowledges that humans are using it and humans are behind the content.

**Required elements.**
- Every forum thread shows author full name, role, initials avatar in a 32px circle, and a precise posting time.
- Activity feed entries are written as natural-language sentences with full attribution: "Sarah Chen replied to your thread *Worker Compensation Updates* 12 minutes ago."
- Active-user count on the forum index: "47 active now" in monospace metadata.
- The dashboard greets the signed-in user by first name in display type.
- Onboarding parsing narration uses first-person plural: "We're identifying citations" rather than "Identifying citations."
- Plain-language confirmations: "Your thread is live" rather than "Action completed."
- Real numbers in real formats: "1,247 regulations" rather than "1.247K."

---

### 7. Wayfinding (the Three-Question Test)

Every page must answer three questions within five seconds of landing.

1. Where am I?
2. What can I do here?
3. Where can I go next?

**Where am I.** Page title in display type at the top of the content area. Breadcrumb in the top bar. Active sidebar item highlighted with a 3-pixel left accent border and 8 percent background fill.

**What can I do here.** Primary actions visible above the fold. No hidden affordances behind hover or right-click. A primary CTA always visible on the index of every section.

**Where can I go next.** Sidebar always shows all primary destinations. Breadcrumb always shows the path back. Related content rails appear at the bottom of detail pages.

---

### 8. Flexibility and Efficiency

Power users get shortcuts. New users get clear paths.

**Required elements.**
- Keyboard shortcuts on every primary action, surfaced in tooltips: Cmd+K opens search, Cmd+N starts a thread, Escape closes modals.
- A command palette available on Cmd+K from anywhere in the product.
- Recently used items prominent in autocompletes.
- The default action on every page is the most common action, primary CTA visible.

---

### 9. Error Prevention and Recovery

Help users avoid mistakes; when mistakes happen, recovery is one tap.

**Required elements.**
- Inline validation as the user types. Errors appear below the field in error color with a short, plain-language explanation.
- Successful validation shows a subtle check.
- Destructive actions are visually distinct (accent in error color) and either require confirmation or produce an undo toast.
- Form fields preserve content across navigation; drafts auto-save every 5 seconds.
- Plain-language errors: "We couldn't reach the server. Retrying." Never error codes alone.

---

### 10. Help and Documentation

Help is task-oriented and reachable, never required.

**Required elements.**
- A help icon in the top bar opens contextual help for the current page.
- Tooltips on every icon-only button explaining what the button does.
- An onboarding sequence that introduces the product without overwhelming.
- Documentation links in the footer.

---

## Part Two — Layout Architecture

### Public Resource Pattern

Public Geode pages are intentionally separate from the manager workspace. A public user should be
able to search, browse, read, and review public resources without signing in.

**Public page specifications.**
- Use the shared public navigation on Home, Search, Library, Forum, Trust, About, Pricing,
  Regulations, and public legal record pages.
- Keep the public visual system black and white: white surfaces, black text, thin gray borders,
  and restrained hover states.
- Do not use manager sidebar chrome on public pages.
- Do not suggest that public users need a manager account to use public resources.
- Legal record detail pages must include a clearly marked back path to the relevant public index.

The sidebar and top bar pattern below applies to the verified manager workspace and other signed-in
product surfaces, not to public resource pages.

### The Sidebar + Top Bar Pattern

Geode uses the proven dual-rail navigation pattern from Linear, Notion, Stripe, Vercel, and Hebbia.

**Sidebar specifications.**
- 256 pixels wide when expanded.
- 64 pixels wide when collapsed (icon-only).
- 200ms ease-in-out transition between states, no content reflow.
- Primary destinations top to bottom: Forum, Query, Regulations, Activity. Settings at the bottom.
- Each item is 36 pixels tall with 12 pixels horizontal padding.
- Active item: 3-pixel left accent border, 8 percent background fill in the accent color.
- Hover: 200ms background fade.
- The user's name and workspace at the top of the sidebar.
- Collapse toggle at the bottom of the sidebar.

**Top bar specifications.**
- 56 pixels tall.
- Persistent across every page below the dashboard root.
- Left to right: back chevron (44×44), breadcrumb, search input (400 pixels centered), notifications bell, help icon, user avatar.
- Background sits 1 pixel above the page content, with a hairline rule beneath.

**Content area specifications.**
- Maximum width 1200 pixels for most surfaces.
- Reading surfaces (regulation detail, forum thread) constrained to 720 pixels for line length.
- Horizontal padding 32 pixels on viewports above 1024 pixels, 16 pixels below.

---

### The Page Structure Standard

Every page below the dashboard root is composed in this order:

1. **Top bar** — persistent, as specified above.
2. **Page header** — page title in display type, optional one-sentence description, primary CTA on the right.
3. **Page content** — the main work surface.
4. **Related rail** — optional, at the bottom of detail pages.

The page header is the single most important wayfinding element. It answers "Where am I" definitively. It is never omitted, even on simple pages.

---

## Part Three — Visual Atmosphere

The atmospheric foundation from the prior design phases is preserved as the finish. It sits beneath the navigation infrastructure, not in place of it.

**Allowed atmospheric elements.**
- A slow-drifting gradient field behind the page content.
- A fine-grain noise overlay at very low opacity.
- A single accent bloom on the landing and dashboard.
- Sparklines and live data charts on data anchors.
- Subtle elevation on the most important content surfaces.

**Disallowed atmospheric elements.**
- Atmospheric backgrounds that obscure navigation chrome.
- Atmospheric effects that compete with content hierarchy.
- Atmospheric motion that delays or distracts from primary actions.
- Atmospheric elements that have no functional purpose.

Atmosphere is permitted only where it does not violate any principle in Part One.

---

## Part Four — Interaction Standards

**Hit targets.** Every interactive element has a minimum 44×44 pixel hit target. This is the MIT Touch Lab standard reflected in iOS, Android, and WCAG guidance.

**Focus states.** Every interactive element has a visible focus state when reached by keyboard: a 2-pixel accent outline with a 2-pixel offset.

**Hover states.** Subtle elevation or background shift over 200ms. Never a transform that displaces the element.

**Active states.** 1-pixel depression on press. Subtle accent glow on completion.

**Transitions.** Page transitions use the View Transitions API. Duration 240ms with the easing curve `cubic-bezier(0.2, 0.8, 0.2, 1)`.

**Reduced motion.** Every animation has an instant-state fallback. The `prefers-reduced-motion: reduce` media query disables all motion above 0ms.

---

## Part Five — Empty and Loading States

**Loading states.**
- Skeleton placeholders that match the final layout exactly.
- Appear within 100 milliseconds of fetch initiation.
- Subtle 1.5-second shimmer in the accent color at 8 percent opacity.
- Never a centered spinner alone.

**Empty states.**
- One illustrative element (not a generic icon).
- One sentence explaining why the state is empty.
- One CTA inviting the action that would fill it.
- Example for the forum's empty state: "No threads in your feed yet. Follow some tags to get started" with a Browse tags CTA.

**Error states.**
- Plain-language explanation.
- A specific action the user can take to recover.
- Never a stack trace, never an error code alone.

---

## Part Six — Human Elements Required Throughout

**Forum thread row.**
- Title in body weight.
- Excerpt of one line.
- Author full name, author role, initials avatar in a 32px circle.
- Precise posting time, replies count, votes count, tags.

**Activity feed entry.**
- Natural-language sentence with full attribution and italicized thread title.

**Forum index header.**
- Active-user count on the right.

**Dashboard greeting.**
- "Good afternoon, [first name]" in display type.

**Onboarding narration.**
- First-person plural acknowledging collaboration.

**Confirmation messages.**
- Plain-language and warm, never system-toned.

---

## Part Seven — The Three-Question Acceptance Test

Before any surface ships, walk the acceptance test as a fresh user with no prior knowledge of the product. Within thirty seconds of landing on the page:

1. Can the user answer "Where am I"?
2. Can the user answer "What can I do here"?
3. Can the user answer "Where can I go next"?

If any answer is no, the surface fails. Fix before shipping.

---

## Part Eight — Reference Hierarchy

When this document is silent, defer in this order:

1. **Nielsen's 10 Usability Heuristics** — foundational framework.
2. **Linear** — for sidebar architecture, command palette, keyboard primacy.
3. **Notion** — for content composition, blocks, and onboarding fork by user type.
4. **Stripe** — for editorial register, settings, error states.
5. **Hebbia** — for the structural pattern matching Geode's closest competitor.
6. **Ornn** — for atmospheric finish only, not for navigation architecture.

When two references conflict, the higher-listed one wins.

---

## Part Nine — Standing Constraints

- No design decision violates a principle in Part One.
- No manager workspace surface omits the sidebar and top bar.
- No public resource surface omits the shared public navigation.
- No interactive element has a hit target below 44×44 pixels.
- No animation lacks a reduced-motion fallback.
- No empty state is left undesigned.
- No forum thread is rendered without human authorship.
- No data fetch is rendered without a skeleton placeholder.
- No destructive action is permitted without undo.

---

## Part Ten — Codex Session Opener

At the start of every Codex session working on Geode's frontend, Codex confirms in one line that it has read this document before proceeding. If Codex begins work without confirming, the session is invalid and must be restarted.
