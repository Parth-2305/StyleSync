# Vibe Coding Rules — Style Sync

These are guardrails for anyone (human or AI assistant) writing code in this repo. The goal: move fast without breaking what already works, and keep the code readable by a beginner-to-intermediate B.Tech student defending this project in a viva.

## 1. Don't Break What Works

- Before editing an existing file, **read the whole file first** — don't guess at context from a snippet.
- Never delete or rewrite a working feature "while you're in there" unless the task asked for it. If you notice something worth fixing, mention it — don't silently expand scope.
- When changing a shared file (`style.css`, `api.js`, `toast.js`, base templates), check every page that uses it before assuming your change is safe. One shared CSS file styles four+ pages — a class rename in the gallery page can silently break the dashboard.
- Test the actual page in a browser after a UI change — a change that "looks right" in the diff can still break at runtime (typo in a selector, wrong element ID, etc).

## 2. Error Handling

- Every API call from the frontend (`api.js` and page scripts) must handle both the network-failure case and the "server responded with an error" case — never assume `fetch` succeeds. Show the user a toast (`toast.js`), never a raw `console.error` as the only feedback.
- Every Flask route that touches Supabase or Pillow must handle the realistic failure modes: missing/invalid auth token, Supabase returning an error, a corrupt/oversized image upload, a missing required field. Return the standard error shape (`{"error": {"code", "message"}}`) documented in `ARCHITECTURE.md` §5 — never let a raw stack trace reach the client.
- Never use bare `except:` in Python — catch specific exceptions (`supabase.PostgrestAPIError`, `PIL.UnidentifiedImageError`, etc.) so real bugs aren't silently swallowed.
- Validate on both ends: client-side validation is for UX (instant feedback), server-side validation is the actual security boundary (see `SECURITY.md`). Never trust the client-side check alone.

## 3. No Silent Failures

- If something is not implemented yet (e.g., a Phase 2 stub route), say so explicitly — return a clear `501 Not Implemented` or a visible "Coming in Phase 2" UI state, not a silently empty response.
- Don't catch an exception just to make an error disappear. If you can't handle it meaningfully, let it propagate (or log it clearly) rather than hiding it behind a generic `except Exception: pass`.

## 4. Comment for a Beginner, Not for Yourself

- Comments should explain **why**, not restate **what** (the code already says what). E.g., good: `# Resize before upload so mobile photos (often 4000px+) don't blow past Supabase's payload limit.` Bad: `# resize the image`.
- Every non-obvious business rule (e.g., "don't suggest an outfit worn in the last 3 days") needs a one-line comment pointing at the *reason*, since that logic isn't self-evident from code alone.
- Keep functions short enough to read in one screen. If a Flask route handler is doing validation + Supabase calls + image processing + response shaping all inline, extract the pieces into `services/` — not because "clean code" demands it, but because a beginner debugging a 120-line route function will get lost.
- Prefer descriptive names over cleverness: `get_unworn_items_for_season()` beats `getStuff()`. This matters extra here since the code needs to be explained during a viva.

## 5. Incremental, Demoable Progress

- Work in the smallest slice that leaves the app in a runnable state. Don't leave the repo in a state where `python app.py` fails to start, even mid-feature — commit/checkpoint working states.
- Follow `TASKS.md` in order within a phase — later tasks assume earlier ones exist (e.g., outfit suggestions assume wardrobe CRUD already works). Don't build Phase 2 (RFID/AI) features before Phase 1's exit criteria (`PRD.md` §5.1) are met.
- After finishing a task, manually click through the affected page(s) before marking it done — automated checks (if any exist) don't replace looking at the real UI.

## 6. Consistency Over Cleverness

- Follow the palette, type scale, and component patterns in `DESIGN.md` exactly — don't invent a one-off color or font for a single page. If the design system is missing something you need, add it to `DESIGN.md` first, then use it.
- Reuse existing JS helpers (`toast.js`, `api.js`, nav scripts) instead of writing a parallel one-off version in a new page script.
- Keep the same code style already established in the existing files (e.g., the vanilla-JS module pattern already used in `dashboard.js`/`wardrobe-gallery.js`) rather than introducing a different pattern (e.g., a framework, a different fetch wrapper) for just one page.

## 7. Secrets & Environment

- Never hardcode a Supabase URL, API key, or service-role key directly in a `.py`, `.js`, or `.html` file. Always read from environment variables (see `SECURITY.md` §4 and `README.md`).
- Never commit `.env`. If you accidentally do, treat the keys as compromised — rotate them in the Supabase dashboard, don't just remove the file from a later commit.

## 8. When Unsure

- If a requirement is ambiguous, check `PRD.md` first — it's the source of truth for scope. If still unclear, make the smallest reasonable assumption, note it in the commit/PR description, and move on rather than blocking progress on it.
- If a change would affect the database schema (`ARCHITECTURE.md` §3), update `ARCHITECTURE.md` in the same change — the doc and the schema must never drift apart.
