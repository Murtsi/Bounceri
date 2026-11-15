---
name: Bounceri Dashboard
description: A dark, glass-surfaced workspace for reading traffic evidence and detector verdicts.
colors:
  forest-night: "#08110c"
  glass-solid: "#1b2620"
  glass-translucent: "rgba(255, 255, 255, 0.055)"
  ink: "#eef3ea"
  ink-muted: "rgba(226, 236, 220, 0.68)"
  glass-border: "rgba(255, 255, 255, 0.09)"
  signal-lime: "#c5ef5d"
  signal-lime-ink: "#0f1a0c"
  verdict-human: "#4f92e0"
  verdict-good-bot: "#26a088"
  verdict-bad-bot: "#bf8418"
  verdict-uncertain: "#8a958c"
  activity-browser-like: "#67c6e3"
  activity-automation-signal: "#bb9af7"
  status-good: "#4cc764"
  status-warning: "#fab219"
  status-serious: "#ec835a"
  status-critical: "#e0a43a"
typography:
  headline:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif'
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.025em"
  body:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif'
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif'
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
  identifier:
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace'
    fontSize: "0.6875rem"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  sm: "12px"
  md: "14px"
  lg: "16px"
  xl: "20px"
  card: "24px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.signal-lime}"
    textColor: "{colors.signal-lime-ink}"
    rounded: "{rounded.pill}"
    height: "36px"
    padding: "8px 16px"
    typography: "14px / 600"
  button-ghost:
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    height: "32px"
    padding: "8px 14px"
    typography: "14px / 500"
  card:
    backgroundColor: "{colors.glass-translucent}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "24px"
  badge-outline:
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
    typography: "12px / 500"
  nav-active:
    backgroundColor: "{colors.signal-lime}"
    textColor: "{colors.signal-lime-ink}"
    rounded: "{rounded.pill}"
    height: "44px"
    padding: "0 16px"
---

# Design System: Bounceri Dashboard

## Overview

**Creative North Star: “Evidence at a glance” — focused triage with honest operating context.**

The interface feels focused, assured, and precise. A deep forest backdrop and layered green glass give the evidence room to breathe, while compact labels, tabular counts, and monospace identifiers keep dense operational details scannable. Signal lime marks selection and primary action; verdict and status colors retain their distinct meanings.

The dashboard preserves its existing navigation while adding views in the same visual world. The overview puts operating context and a prioritized, clickable attention queue first, followed by traffic trend, known-human honesty metrics and latest activity. **Key Characteristics:**
- Dark forest-green surfaces with translucent glass layers.
- A restrained lime signal for active and primary states.
- Dense evidence rows with calm hierarchy and soft corners.

## Colors

The palette pairs near-black forest greens and pale botanical ink with a single bright lime accent; chart and status colors carry explicit data meaning.

### Primary
- **Signal Lime**: Used for selected navigation, primary actions, focus indication, and small emphasis. It is reserved for interface state rather than a traffic-series color.

### Secondary
- **Status Green**: Positive status feedback, paired with its label or icon.
- **Status Amber**: Warning and synthetic/unavailable status feedback.
- **Status Coral**: Serious status feedback.
- **Status Gold**: Critical status token.

### Tertiary
- **Human Blue**: The traffic chart's human series.
- **Good-Bot Teal**: The traffic chart's good-bot series.
- **Bad-Bot Amber**: The traffic chart's bad-bot series.
- **Uncertain Grey**: The de-emphasized uncertain series; the label remains visible alongside color.

### Neutral
- **Forest Night**: The fixed dark page base.
- **Glass Solid**: The opaque green surface used where a layered or popover surface needs a firm backing.
- **Translucent Glass**: The shared card and navigation surface, backed by blur and subtle inner light.
- **Pale Ink**: Main text and headings.
- **Muted Ink**: Supporting descriptions, timestamps, and secondary metadata.
- **Glass Border**: Fine separation around glass surfaces and controls.

### Named Rules
**The Signal Lime Rule.** Keep lime for interaction and selection; do not reuse it as a traffic data series.

**The Verdict Vocabulary Rule.** Preserve distinct chart and status colors, and pair status meaning with text or an icon rather than color alone.

## Typography

**Display Font:** System UI (`system-ui`, `-apple-system`, “Segoe UI”, sans-serif)
**Body Font:** The same system sans stack
**Label/Mono Font:** System UI for labels; `ui-monospace`, `SFMono-Regular`, Menlo, monospace for identifiers and compact numeric metadata.

**Character:** A neutral, familiar sans keeps the dashboard direct and readable. Monospace is a secondary tool for identifiers and time-oriented data, not a competing display voice.

### Hierarchy
- **Headline** (600, 24px; 30px at the small-screen breakpoint, 1.25 line-height): Page title.
- **Title** (600, 16–20px, tight line-height): Card and section headings.
- **Body** (400, 14px, 1.5 line-height): Descriptions and readable evidence copy.
- **Label** (500, 12px, about 1.4 line-height): Status, secondary metadata, and controls.
- **Identifier** (400, 11px, monospace): Session identifiers and compact timestamps.

## Layout

The desktop shell uses a fixed glass sidebar and a centered content column capped at the Tailwind `max-w-7xl` width, offset to clear the sidebar. At narrow widths the sidebar becomes a sticky top bar and a floating bottom navigation; content stays in one column without requiring horizontal scrolling. The overview puts a compact context rail above the prioritized attention queue, followed by a full-width traffic chart and supporting evidence cards. Other existing views retain the shared shell and their established layouts.

Spacing follows the recurring 4px-based utility rhythm (4, 8, 12, 16, and 24px are common). On mobile, the attention queue remains ahead of the traffic trend and supporting evidence.

## Elevation & Depth

Depth comes mainly from translucent green surfaces over a fixed, softly graded forest background, with backdrop blur and a fine inset highlight. Shadows appear when a glass surface needs separation or an element is lifted; they are not a universal card outline. Some charts and evidence blocks instead use tonal contrast and thin borders.

### Shadow Vocabulary
- **Glass lift** (`inset 0 1px 0 rgba(255,255,255,0.06), 0 10px 30px -12px rgba(0,0,0,0.45)`): Shared glass treatment for separating a surface from the background.

## Shapes

Controls and navigation use pill silhouettes. Cards are gently rounded (24px); smaller investigation panels and inputs use tighter corners (typically 8–16px). Borders are fine and low-contrast, with stronger lime-tinted outlines reserved for selected and focused controls. Glass surfaces clip their contents cleanly at the rounded boundary.

## Components

### Buttons
- **Character:** Precise, calm controls with a clear selected state.
- **Shape:** Pill-shaped (999px), with compact 32–40px heights.
- **Primary:** Signal-lime fill with dark green text; the default size is 36px high with 16px horizontal padding.
- **Hover / Focus:** Primary fill softens on hover; visible focus uses a lime ring. Disabled buttons reduce opacity.
- **Ghost / Outline:** Ghost actions remain quiet until hover. Outline buttons use glass, a border, and a restrained surface change on hover.

### Chips
- **Style:** Verdict and action badges are compact outlined pills. A verdict badge pairs its color swatch with a readable label; action badges use an icon and action text without assigning action severity by color.
- **State:** The active navigation item uses the lime fill; data labels keep their series color.

### Cards / Containers
- **Character:** Soft glass containers group evidence without making every metric look interchangeable.
- **Corner Style:** Gently rounded (24px for shared cards; 14–16px on compact evidence panels).
- **Background:** Translucent white over green, with an opaque green backing available for popovers.
- **Shadow Strategy:** Use the glass lift treatment when the container needs separation; other sections use border and tonal contrast.
- **Border:** Fine translucent light border.
- **Internal Padding:** Shared cards use 24px vertical and 24px horizontal spacing; compact panels use 16–20px.

### Inputs / Fields
- **Style:** Native select fields use a glass-tinted background, subtle border, compact padding, and tighter corners (14px).
- **Focus:** Visible lime outline with offset; focus remains distinct from hover.
- **Error / Disabled:** Keep state text visible and pair meaning with an icon or label where applicable.

### Navigation
- **Style:** Desktop uses a fixed, rounded glass sidebar with full-width, icon-led rows. Mobile uses a compact floating glass pill with icon buttons.
- **States:** The active item is lime with dark text; inactive items are muted and brighten on hover. Keyboard focus has a visible ring.

## Do's and Don'ts

### Do:
- **Do** keep lime on interaction and selection, and keep data series mapped to their distinct chart colors.
- **Do** use the system sans for interface copy and monospace for identifiers and compact time metadata.
- **Do** pair status colors with visible words or icons and preserve the uncertain grey treatment.
- **Do** use layered green glass for shared surfaces and reserve shadows for actual separation or lift.
- **Do** preserve the incumbent dashboard shell and view language when adding a new view.

### Don't:
- **Don't** turn evidence into a generic AI-looking dashboard of interchangeable metric tiles.
- **Don't** imply that detector recommendations are live enforcement; the dashboard labels them as recommendations.
- **Don't** use color as the only carrier of verdict or status meaning.
