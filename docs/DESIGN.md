# Design System — Style Sync

This is the single source of truth for visual design. `static/css/style.css` should be re-themed to match this document (see `TASKS.md` — the current CSS uses an older "editorial forest/terracotta" palette that predates this spec and needs to be swapped over).

## 1. Color Palette

| Token | Name | Hex | Usage |
|---|---|---|---|
| `--color-primary` | Deep Ocean Blue | `#0A2540` | Primary brand color — navbars, headers, primary text on light surfaces, sidebar, dark UI chrome |
| `--color-accent` | Vibrant Coral | `#FF6B6B` | Primary CTA buttons, active states, badges, key highlights — use sparingly, it's the "pop" color |
| `--color-secondary` | Cool Sky Blue | `#A0C8E8` | Secondary accents, hover backgrounds, chips/tags, decorative gradients, info states |
| `--color-surface` | Canvas Cloud White | `#FFFFFF` | Card surfaces, modals, primary content backgrounds |
| `--color-bg` | Soft Off-White | `#F8F9FA` | Page background (behind cards), subtle section dividers |
| `--color-text` | Text Charcoal Grey | `#333333` | Body copy, default text color |

### 1.1 Derived / functional tokens

Build these from the palette above rather than inventing new colors:

| Token | Value | Usage |
|---|---|---|
| `--color-text-muted` | `#333333` at 65% opacity, or `#6B7280` | Secondary text, meta info, timestamps |
| `--color-border` | `rgba(10, 37, 64, 0.12)` | Card borders, dividers (derived from primary) |
| `--color-success` | `#2F9E63` | Success toasts/badges (kept outside the core 5 — functional only) |
| `--color-danger` | `#E5484D` | Destructive actions (delete), error states — distinct from coral so "delete" never looks like a CTA |
| `--color-warning` | `#E8A73A` | Warnings, "haven't worn in X days" nudges |
| `--shadow-soft` | `0 8px 24px rgba(10, 37, 64, 0.10)` | Card resting shadow |
| `--shadow-hover` | `0 14px 32px rgba(10, 37, 64, 0.16)` | Card/button hover shadow |
| `--shadow-accent-glow` | `0 8px 20px rgba(255, 107, 107, 0.30)` | Glow behind coral CTAs |

### 1.1a Warm-canvas refresh (UI refactor, Sep 2026)

The current `style.css` layers these on top of the palette above:

| Token | Value | Usage |
|---|---|---|
| `--color-bg` | `#FFF9F6` (Warm Canvas) | Page background — replaces `#F8F9FA`, which is kept as `--color-bg-alt` for inset surfaces |
| `--color-accent-hover` | `#E05555` | Coral CTA hover (replaces `#FF5252` in §5) |
| `--color-accent-tint` | `#FFEBEB` | Active pill / selected chip background, with coral `#FF6B6B` text |
| `--color-secondary-tint` | `#EAF3FA` | Info tags, reason callouts |
| `--color-border` | `rgba(10, 37, 64, 0.06)` | Card border (softer than the 0.12 above; 0.14 kept as `--color-border-strong` for inputs/pills) |
| Card radius | `20px` (`--radius-lg`) | All `.ss-card` containers |
| Button / pill radius | `999px` | Buttons and nav pills are fully rounded |

Navigation is a single top bar (`templates/includes/nav.html`): logo + "stylesync" / "YOUR CLOSET, CLEARER" on the left, pill nav in the centre, "+ Add item" coral CTA, initial badge and logout on the right. The old sidebar (`app-nav.js`) is no longer used.

### 1.2 Usage ratio (guardrail)

Keep the UI calm — Deep Ocean Blue and whites/off-whites should dominate; Coral is a small-percentage accent, not a background color:

- ~60% neutral surfaces (`--color-surface`, `--color-bg`)
- ~25% primary (`--color-primary`) for structure (nav, headers, text, icons)
- ~10% secondary (`--color-secondary`) for soft highlights/hovers
- ~5% accent (`--color-accent`) for CTAs and the single most important element per screen

## 2. Typography

| Role | Font | Fallback stack | Notes |
|---|---|---|---|
| Display / headings | `"Poppins"` (or `"Fraunces"` if a more editorial/boutique feel is wanted) | `"Segoe UI", Arial, sans-serif` | Weights 500–700. Used for H1–H3, hero titles, card titles. |
| Body / UI | `"Inter"` | `"Segoe UI", Arial, sans-serif` | Weights 400–600. Used for paragraphs, labels, buttons, nav. |

```css
:root {
  --font-display: "Poppins", "Segoe UI", Arial, sans-serif;
  --font-body: "Inter", "Segoe UI", Arial, sans-serif;
}
```

### Type scale

| Token | Size | Line height | Usage |
|---|---|---|---|
| `--text-h1` | `clamp(2.2rem, 4vw, 3.2rem)` | 1.15 | Page hero titles |
| `--text-h2` | `1.75rem` | 1.2 | Section headings |
| `--text-h3` | `1.25rem` | 1.3 | Card titles |
| `--text-body` | `1rem` | 1.6 | Paragraphs |
| `--text-small` | `0.875rem` | 1.5 | Meta text, captions, labels |

Load both fonts from Google Fonts in the base template `<head>`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Poppins:wght@500;600;700&display=swap" rel="stylesheet">
```

## 3. Core CSS Tokens

```css
:root {
  /* Palette */
  --color-primary: #0A2540;
  --color-accent: #FF6B6B;
  --color-secondary: #A0C8E8;
  --color-surface: #FFFFFF;
  --color-bg: #F8F9FA;
  --color-text: #333333;
  --color-text-muted: #6B7280;
  --color-border: rgba(10, 37, 64, 0.12);
  --color-success: #2F9E63;
  --color-danger: #E5484D;
  --color-warning: #E8A73A;

  /* Typography */
  --font-display: "Poppins", "Segoe UI", Arial, sans-serif;
  --font-body: "Inter", "Segoe UI", Arial, sans-serif;

  /* Shadows */
  --shadow-soft: 0 8px 24px rgba(10, 37, 64, 0.10);
  --shadow-hover: 0 14px 32px rgba(10, 37, 64, 0.16);
  --shadow-accent-glow: 0 8px 20px rgba(255, 107, 107, 0.30);

  /* Radii */
  --radius-sm: 6px;
  --radius-md: 12px;
  --radius-lg: 20px;

  /* Motion */
  --ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
  --duration-fast: 150ms;
  --duration-base: 250ms;
}
```

## 4. Glassmorphism Spec

Use glassmorphism deliberately — on the **navbar**, the **dashboard "today's outfit" hero panel**, and **modal dialogs** only. Not on every card (that flattens the hierarchy and hurts readability/contrast).

```css
.glass-panel {
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(16px) saturate(160%);
  -webkit-backdrop-filter: blur(16px) saturate(160%);
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-soft);
}

/* Dark variant — for the glass panel when it sits over the primary-blue hero image */
.glass-panel--on-dark {
  background: rgba(10, 37, 64, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: #FFFFFF;
}

/* Navbar glass — sticky, sits above page content on scroll */
.navbar-glass {
  background: rgba(248, 249, 250, 0.72);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--color-border);
}
```

**Accessibility guardrail:** always test text contrast *after* applying `backdrop-filter` against the busiest image likely to sit behind it. If body text sits on `.glass-panel`, it must be `--color-primary` or darker on the light variant, or pure white on `.glass-panel--on-dark` — never place `--color-text-muted` directly on glass.

## 5. Buttons

```css
.btn-primary {
  background: var(--color-accent);
  color: #FFFFFF;
  font-family: var(--font-body);
  font-weight: 600;
  border: none;
  border-radius: var(--radius-sm);
  padding: 12px 24px;
  box-shadow: var(--shadow-accent-glow);
  transition: transform var(--duration-fast) var(--ease-standard),
              box-shadow var(--duration-fast) var(--ease-standard),
              background var(--duration-fast) var(--ease-standard);
}

.btn-primary:hover {
  background: #FF5252;
  transform: translateY(-2px);
  box-shadow: 0 12px 26px rgba(255, 107, 107, 0.4);
}

.btn-primary:active {
  transform: translateY(0) scale(0.98);
}

.btn-secondary {
  background: transparent;
  color: var(--color-primary);
  border: 1.5px solid var(--color-primary);
  border-radius: var(--radius-sm);
  padding: 11px 22px;
  font-weight: 600;
  transition: background var(--duration-fast) var(--ease-standard), color var(--duration-fast) var(--ease-standard);
}

.btn-secondary:hover {
  background: var(--color-primary);
  color: #FFFFFF;
}
```

## 6. Cards & Hover Effects

```css
.item-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-soft);
  transition: transform var(--duration-base) var(--ease-standard),
              box-shadow var(--duration-base) var(--ease-standard);
}

.item-card:hover {
  transform: translateY(-6px);
  box-shadow: var(--shadow-hover);
}

.item-card img {
  transition: transform 0.4s var(--ease-standard);
}

.item-card:hover img {
  transform: scale(1.05);
}

/* Nav link underline-grow */
.nav-link {
  position: relative;
  color: var(--color-primary);
}

.nav-link::after {
  content: "";
  position: absolute;
  left: 0;
  bottom: -2px;
  width: 0;
  height: 2px;
  background: var(--color-accent);
  transition: width var(--duration-base) var(--ease-standard);
}

.nav-link:hover::after,
.nav-link.is-active::after {
  width: 100%;
}
```

## 7. Motion Principles

- One entrance animation per page max (hero image or hero panel) — avoid animating everything at once.
- Standard duration: 150ms for micro-interactions (buttons, links), 250–350ms for panel/card transitions.
- Always respect `prefers-reduced-motion: reduce` — disable transforms/animations, keep opacity-only fallback.
- Use `transform`/`opacity` only for animated properties (GPU-friendly); avoid animating `width`/`height`/`top`/`left` directly.

## 8. Iconography

- Use **Bootstrap Icons** (already Bootstrap-native, consistent stroke weight, free) via CDN — avoid mixing multiple icon sets.
- Icon color follows text color context: `--color-primary` on light surfaces, white on dark/glass panels, `--color-accent` only for a single emphasized icon (e.g., the active nav icon).

## 9. Layout Grid

- Container max-width: `1280px`, centered, `24px` side gutters on desktop, `16px` on mobile.
- Use Bootstrap 5's 12-column grid for page-level layout; use CSS Grid for component-level layouts (masonry wardrobe gallery, dashboard stat columns) where Bootstrap's grid is too rigid.
- Breakpoints follow Bootstrap defaults: `sm 576px`, `md 768px`, `lg 992px`, `xl 1200px`, `xxl 1400px`.

## 10. Accessibility Baseline

- Minimum contrast: body text 4.5:1, large text/headings 3:1 (verify `--color-text` on `--color-bg` and white text on `--color-primary`/`--color-accent` — both pass).
- Every `<img>` (garment photos especially) needs meaningful `alt` text (e.g., "Navy blue oxford shirt"), not filenames.
- All interactive elements reachable and operable by keyboard; visible focus ring using `--color-accent` at 3px outline, never `outline: none` without a replacement.
- Form errors communicated with text + icon + color (never color alone) — see the `.is-invalid` shake pattern already used in `add-clothing-item.js`/`style.css`.
