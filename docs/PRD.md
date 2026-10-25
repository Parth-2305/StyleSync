# Product Requirements Document (PRD)
## Style Sync — Smart Wardrobe Management & Personalized Outfit Recommendation System

**Document owner:** Parth Mhatre
**Program:** B.Tech Information Technology — Capstone (Phase 1) / Major Project (Phase 2)
**Status:** Draft v1.0

---

## 1. Problem Statement

Most people own more clothes than they can mentally track. They forget what they have, repeat the same outfits, and waste time each morning deciding what to wear — especially when packing for trips or dressing for weather/occasions they haven't planned for. There is no simple, personal system that:

- Catalogs a person's actual wardrobe (not a shopping wishlist).
- Suggests outfits from *items the user already owns*.
- Learns from what the user actually wears over time.

Style Sync solves this by digitizing a user's wardrobe and using rule-based (Phase 1) and AI-assisted (Phase 2) logic to recommend outfits, eventually tying physical garments to digital records via RFID hardware.

## 2. Goals

- G1: Let a user digitize their wardrobe quickly (photo + tags) in under 60 seconds per item.
- G2: Give the user a daily "what should I wear" recommendation with zero manual outfit-building.
- G3: Track wear history so recommendations improve and laundry/rotation gets easier to reason about.
- G4: (Phase 2) Bridge the physical wardrobe to the digital catalog automatically via RFID, removing manual entry as a long-term barrier.

## 3. Non-Goals

- Not a social/sharing platform (no public feeds, follows, or likes in Phase 1/2).
- Not an e-commerce or shopping recommendation engine (no "buy this" suggestions).
- Not building a native mobile app — the web app must be responsive/mobile-friendly instead.
- Not attempting real computer-vision garment classification in Phase 1 (manual tagging only).

## 4. Target Users

- **Primary:** The student/individual user managing their own wardrobe (single-tenant per account).
- **Secondary (evaluation audience):** Capstone/Major Project examiners assessing functional completeness, code quality, and (Phase 2) hardware integration.

## 5. Phase Split

Style Sync is delivered in two academically-scoped phases. Phase 1 must be a fully working, demoable product on its own — Phase 2 extends it, it does not replace it.

### 5.1 Phase 1 — Capstone MVP (Software Only)

**Scope: prove the core software loop — auth, wardrobe CRUD, rule-based outfit suggestions.**

| # | Feature | Description |
|---|---------|-------------|
| F1.1 | Auth | Sign up / log in / log out via Supabase Auth (email + password). Session persisted, protected routes redirect to landing/login when unauthenticated. |
| F1.2 | Wardrobe CRUD | Add, view, edit, delete clothing items. Each item has: photo, category, subcategory, color, season, occasion tags, notes. |
| F1.3 | Image upload | Upload a garment photo from device; client-side resize/compress (Pillow on the backend as a safety net) before storing in Supabase Storage. |
| F1.4 | Wardrobe gallery | Filterable/searchable masonry gallery of all items (by category, color, season, occasion). |
| F1.5 | Dashboard | Landing-after-login screen: today's outfit suggestion, quick stats (total items, most/least worn), recent activity. |
| F1.6 | Rule-based outfit suggestion | Given category rules (top+bottom+footwear, optional layer), weather-agnostic or simple season filter, and "avoid recently worn" logic, propose 1–3 outfit combinations from the user's actual items. |
| F1.7 | Mark as worn | User can log "I wore this outfit today," which updates wear counts and recency (feeds F1.6). |
| F1.8 | Responsive UI | Mobile-first responsive layout across all screens using Bootstrap 5 grid + custom CSS. |

**Phase 1 exit criteria:** a user can register, add 15–20 real garments with photos, receive a sensible outfit suggestion, mark it worn, and see it reflected in their stats — end to end, no manual DB edits required.

### 5.2 Phase 2 — Major Project (IoT + AI Extension)

**Scope: extend the working MVP with hardware tagging and smarter recommendations. Builds on Phase 1's schema — no rewrite.**

| # | Feature | Description |
|---|---------|-------------|
| F2.1 | RFID tag binding | Each physical garment gets an RFID tag; user "binds" a tag to a wardrobe item once via a binding UI flow. |
| F2.2 | ESP32 + RC522 scanning | ESP32 reads RC522 RFID scans and pushes scan events to the Flask backend over Wi-Fi (REST call or MQTT-to-webhook bridge). |
| F2.3 | Smart laundry basket / wear logging | Scanning an item (e.g., at a laundry basket or on the way out the door) auto-logs "worn" or "returned to wardrobe" instead of manual tapping in the UI. |
| F2.4 | AI-assisted recommendations | Replace/augment rule-based suggestions with a weighted model considering weather (via a free weather API), color-pairing heuristics, occasion, and wear-history recency to reduce repetition. |
| F2.5 | Outfit history & analytics | Visual history of what was worn on which days; basic analytics (cost-per-wear if cost is entered, most-neglected items). |
| F2.6 | Notifications | In-app (and optionally email) nudges: "You haven't worn this in 60 days" / "Today's suggested outfit is ready." |

**Phase 2 exit criteria:** at least one physical garment can be scanned by the ESP32+RC522 rig and have its wear status update in the live dashboard within a few seconds, and outfit suggestions visibly account for at least one AI/weighted signal beyond simple rotation.

## 6. User Stories (Phase 1 focus)

- As a new user, I can sign up and land on an empty-state dashboard that tells me to add my first item.
- As a user, I can add a clothing item with a photo and tags in under a minute.
- As a user, I can browse my wardrobe visually and filter by category/color/season/occasion.
- As a user, I can open my dashboard and get an outfit suggestion built entirely from items I own.
- As a user, I can tell the app I wore an outfit, so it stops suggesting the same thing every day.
- As a user, I can edit or delete an item if I donate/discard the garment.

## 7. Success Metrics

- Functional: 100% of Phase 1 features (F1.1–F1.8) demoable without console errors or manual DB intervention.
- Usability: a first-time user can add an item and receive a suggestion without instructions (self-evident UI).
- Performance: image upload + resize completes in <3s on a typical item photo (<5MB, JPEG/PNG).
- Academic: PRD/ARCHITECTURE/DESIGN/SECURITY docs current enough to support a viva/demo defense.

## 8. Assumptions & Constraints

- Single-user-per-account model (no shared/family wardrobes in Phase 1/2).
- Supabase free tier is sufficient for capstone-scale data (dozens to low hundreds of items, one demo account).
- ESP32/RC522 hardware work (Phase 2) happens on the same Wi-Fi network as the Flask dev server, or the Flask app is deployed somewhere hardware can reach over the internet.
- No payment processing, no multi-language support, no accessibility certification required — but basic a11y (contrast, alt text, keyboard nav) is still good practice and expected in DESIGN.md.

## 9. Open Questions

- Weather API provider for Phase 2 (OpenWeatherMap vs. free alternative) — decide before F2.4 starts.
- Whether Phase 2 hardware events go straight to Flask REST or through a lightweight MQTT broker — decide once ESP32 firmware work begins.
