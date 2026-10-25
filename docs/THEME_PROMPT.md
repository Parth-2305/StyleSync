# Theme prompt — paste this at the start of any new Claude session

You are working on **Style Sync**, a Flask + Bootstrap 5 + vanilla JS wardrobe app. Follow the "Vibrant Coral" theme exactly. Read `static/css/style.css` (section 1, Tokens) first and reuse its variables. Never invent a new colour.

## Colours

| Role | Hex | Where |
|---|---|---|
| Page background | `#FFF9F6` | warm canvas behind everything |
| Card / modal surface | `#FFFFFF` | cards, forms |
| Primary (structure) | `#0A2540` | headings, nav text, icons |
| Body text | `#333333` | paragraphs |
| Muted text | `#6B7280` | meta, captions (never on glass) |
| **Coral (accent)** | `#FF6B6B` | main CTA per screen, active nav pill text, focus ring |
| Coral hover | `#E05555` | CTA hover (+ lift 2px, stronger glow) |
| Coral pressed | `#C94A4A` | CTA `:active` (scale .98, no lift) |
| Coral tint | `#FFEBEB` | selected pill / chip background (text stays coral) |
| Sky blue | `#A0C8E8` | secondary accents, chips |
| Sky tint | `#EAF3FA` | info boxes, "reason" callouts |
| Success / Danger / Warning | `#2F9E63` / `#E5484D` / `#E8A73A` | toasts, delete (never coral), nudges |

Usage ratio: ~60% neutral surfaces, 25% navy, 10% sky, **5% coral**. Coral is a highlight, never a big background.

## States (buttons, pills, links, inputs)

- **Primary button:** coral fill, white text, glow `0 8px 20px rgba(255,107,107,.30)`. Hover `#E05555` + `translateY(-2px)`. Active `scale(.98)`. Disabled 50% opacity, no glow.
- **Secondary button:** transparent, 1.5px navy border. Hover navy fill + white text.
- **Selected pill / chip:** `#FFEBEB` background, coral text, coral 1px border. Unselected: white, navy text, border `rgba(10,37,64,.14)`. Hover: sky tint `#EAF3FA`.
- **Nav link:** navy text. Hover: sky tint background. Active: coral tint pill with coral text.
- **Cards:** radius 20px, border `rgba(10,37,64,.06)`, soft shadow. Hover: lift 6px, stronger shadow, image scale 1.05.
- **Inputs:** white, border `rgba(10,37,64,.14)`. Focus: coral border + 3px coral ring at 25% opacity. Error: `#E5484D` border, shake, and a text message (never colour alone).
- **Delete:** `#E5484D`, always confirmed in a modal.

## Blur, shadow, light

- Glass (`backdrop-filter: blur(16px) saturate(160%)`, `rgba(255,255,255,.55)`, 1px white 35% border) **only** on: top nav, the dashboard hero panel, modals.
- Shadows are navy-tinted: `0 8px 24px rgba(10,37,64,.10)` at rest, `0 14px 32px rgba(10,37,64,.16)` on hover. The only coloured shadow is the coral CTA glow.
- Soft light: a blurred coral + sky radial gradient blob behind the hero (`filter: blur(80px)`, 20% opacity, `pointer-events:none`).

## Type, motion, icons

- Poppins 500–700 for headings, Inter 400–600 for everything else.
- 150ms for micro-interactions, 250–350ms for panels. Animate only `transform` and `opacity`. One entrance animation per page. Respect `prefers-reduced-motion`.
- Bootstrap Icons only. Icons follow text colour; coral only for the active nav icon.
- Mobile first: 16px gutters, bottom-safe tap targets ≥ 44px, single top bar collapses to a menu.

## Code rules (keep it lean, viva-friendly)

- Short functions, `const`/arrow functions, one job each. No dead code, no duplicate helpers.
- Comment the *why*, not the *what*.
- Reuse `toast.js` and the shared helpers in `app.js`. Do not add libraries.
- If a change touches `style.css`, check every page still looks right.
