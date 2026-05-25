# ChessLens — UI Modernization Brief

**Mission for this session:** take the UI from "competent and functional" to "premium and modern" — chess.com 2024+ / Linear / Cursor / Arc-browser quality. The functionality is stable. We're not adding features; we're elevating presentation.

---

## 0 · Setup — DO THIS FIRST

The project is not yet under Git. Before touching anything visual:

```bash
git init
```

Write a sensible `.gitignore` covering:
- `__pycache__/`, `*.pyc`, `*.pyo`
- `build/`, `dist/`, `*.spec` artifacts (but KEEP `ChessLens.spec` — it's the build config)
- `.venv/`, `venv/`, `env/`
- `.DS_Store`, `Thumbs.db`
- `.pytest_cache/`, `.coverage`
- `*.egg-info/`
- IDE files: `.vscode/`, `.idea/`

Then:

```bash
git add -A
git commit -m "Initial commit: ChessLens v12 baseline before UI modernization"
git checkout -b feature/ui-modernization
```

This gives us a safety net. If any visual change breaks the app, `git checkout main` restores it instantly.

---

## 1 · Project context (the things you need to know)

ChessLens is a PySide6 desktop chess analyzer. It loads a PGN, runs Stockfish, classifies each move (brilliant/best/good/inaccuracy/mistake/blunder), and provides voice-narrated coaching. Built as a single-file Windows `.exe` via PyInstaller.

**The user is sjefenfabian** — Norwegian, 24, finance student. Strong aesthetic sense. Plays optimization games (Slay the Spire, Balatro, Hades II). Notices immediately when software feels stale or generic. Has built this app across ~13 sessions and wants it to feel premium.

**Architecture** (read these in this order to orient):
- `app/ui/theme.py` — design tokens (Palette, Typography, Spacing, Radius) + global QSS. This is the single source of truth for visuals.
- `app/ui/main_window.py` — main shell. Defines TopBar, LeftPanel, CenterArea, RightPanel. 1000+ lines; will likely need refactoring but only AFTER visual work lands.
- `app/ui/widgets/` — all the custom widgets:
  - `coach_panel.py` — the coach cards with eval delta badges + tactical keyword highlighting
  - `eval_bar.py` — vertical eval bar next to the board
  - `eval_graph.py` — the curve below the board with classification dots
  - `move_list.py` — the move list with classification icons (`!!`, `★`, `!`, `?!`, `?`, `??`)
  - `pgn_input.py` — the PGN textarea
  - `profile_dialog.py` — username manager (👤 button)
  - `subtitle_box.py` — voice subtitle under the board
  - `voice_settings.py` — voice settings modal
  - `board/scene.py` + `board/view.py` + `board/items.py` — the chess board
- `app/core/` — analyzer, coach, PGN parser. **DO NOT TOUCH.** These are stable.
- `app/services/` — voice, sounds, user_profile. **DO NOT TOUCH.**
- `tests/` — pytest tests. One file currently: `test_board_flip_highlights.py`.

**Build / run:**
- Run from source: `python main.py` (opens maximized, F11 toggles fullscreen)
- Build .exe: `build_exe.bat` (PyInstaller, auto-copies to `C:\Users\haard\Documents\ChessLens.exe`)
- Tests: `python -m pytest tests/`

**Hard constraints:**
- Stay on PySide6. No React/Electron migration.
- Must still build with `build_exe.bat`. No new heavy dependencies.
- Must work on Windows 11. Performance target: 60fps on Ryzen 5 5500 + RTX 4060.
- Voice and analysis must keep working. Run `python main.py` and load `app/core/pgn_parser.py`'s sample after every phase to verify nothing regressed.
- Don't bundle new fonts. Use system-available stacks (Segoe UI Variable is already specified).

---

## 2 · Aesthetic principles for modern dark UI in 2026

Read this twice before writing CSS. Most of these are violated somewhere in the current code.

### Layered depth via tonal shifts, not borders
Modern dark UIs achieve depth through **subtle background tonal differences**, not visible borders. The current code uses borders everywhere. Push toward:
- `bg_app` (darkest) → `bg_panel` → `bg_card` → `bg_card_hi` (lightest)
- Reserve borders for *emphasis* (focused input, divider that needs to read as a divider) — not for every card edge.

### Soft shadows for elevation
Cards, modals, the active piece should have soft drop shadows. PySide6 supports `QGraphicsDropShadowEffect`. Use sparingly:
- Coach cards: very subtle (4-6px blur, 30-40% opacity, 2px offset)
- Modals (profile/voice dialogs): more pronounced (16-24px blur, 50% opacity)
- Active piece during animation: tight shadow (2-3px blur, 60% opacity)

### Generous whitespace
The spacing scale is good (4/8/12/16/24/32). The current code is biased toward `sm` (8) and `md` (12). Bias toward `lg` (16) and `xl` (24) for card padding and group separation. **Cards should breathe.**

### Smooth interactions
Hover states need transitions. PySide6 doesn't support CSS transitions in QSS, so use `QPropertyAnimation` on widget properties for:
- Card hover: subtle background lighten over 120ms
- Button hover: background + border transition
- Move list row hover: subtle fill that grows from left

Don't animate everything. The board is sacred — minimal animation there. Coach cards arriving = subtle fade-in. Eval graph cursor = smooth slide.

### Typography hierarchy that reads
The current scale is 10/11/12/14/18/28. The gaps between are slightly off. Consider:
- `xs: 11` for labels/captions
- `sm: 12` for secondary text
- `md: 13` for body
- `lg: 15` for emphasized body
- `xl: 20` for section headers
- `xxl: 32` for the main "Game Review" title

Weights matter. Use weights 400 (body), 500 (emphasized), 600 (headers), 700 (sparingly, for title). Don't use italic.

### Restrained accent color
Green is overused. It's the brand color but it shouldn't appear on every interactive element. Reserve `accent` (green) for:
- Primary action buttons (Analyze Game, Done in modals)
- The active "Next" button in coach actions
- The cursor dot on the eval graph
- The logo

For everything else, use neutrals. Hover states can use lighter neutrals or a subtle accent tint at 20-40% opacity.

### Consistent rounded corners
- Inputs / small buttons: `radius.md` (6px)
- Cards / modals: `radius.lg` (10px)
- Large modals / pills: bump to 12-14px (consider adding `radius.xl = 14`)
- Coach card stripes: should be radius 0 on the left, follow card radius on the right

### Refined chess board
This is the visual centerpiece. It deserves polish:
- The square colors are flat. Add a 1-3% brightness variation noise/gradient to make them feel less plastic.
- The active piece (during animation) should cast a soft shadow.
- Coordinate labels (a-h, 1-8) are too prominent. Smaller, dimmer, better positioned. Like chess.com's: at the corners of the edge squares, not floating outside.
- Last-move highlight squares are flat yellow. Consider a subtle gradient or inner glow.
- The green "better move" arrow is fine but could use a soft outer glow for emphasis.

---

## 3 · Phased implementation plan

Work through these in order. Each phase ends with a screenshot for before/after comparison and a manual functional check (load a PGN, navigate moves, toggle voice — make sure nothing broke).

### Phase 1 · Design system refinement (~1-2 hours)

In `app/ui/theme.py`:

1. **Refine the palette.** Adjust `bg_app`, `bg_panel`, `bg_card`, `bg_card_hi` so the four levels have distinct but subtle tonal separation. Current values are too close together to read as elevation.
2. **Add elevation shadows** as a utility function:
   ```python
   def elevation_shadow(level: int) -> QGraphicsDropShadowEffect: ...
   ```
   Levels 1-3 for ambient/raised/floating. Apply to cards, modals, top bar.
3. **Add `radius.xl = 14`** for large modals.
4. **Refine typography scale** to 11/12/13/15/20/32 (see above).
5. **Add hover transition helper** — a small utility that wires `QPropertyAnimation` on `backgroundColor` for hover effects.
6. **Audit and remove** every hardcoded color in widgets (`#xxx` literals outside `theme.py`). Every visual constant must live in `Palette`.

Run `python main.py` after this phase. Should look slightly more polished but mostly the same. No regressions allowed.

### Phase 2 · Layout breathing room (~1 hour)

In `app/ui/main_window.py` and each panel:

1. **Audit padding everywhere.** Replace `SPACE.sm` (8) with `SPACE.lg` (16) on outer panel padding. Replace cramped card padding with generous.
2. **Increase coach card padding** from current to `SPACE.lg` vertical + `SPACE.lg` horizontal.
3. **Group related controls** with `SPACE.lg` gutters, not `SPACE.sm`.
4. **Top bar height**: increase to 56px so it doesn't feel like a strip.
5. **Side panels**: widen by 10-20px each if the user's screen has room.

The user is on a 1920×1080 monitor typically. The board is the hero — keep it generous.

### Phase 3 · Board polish (~1-2 hours)

In `app/ui/widgets/board/scene.py`:

1. **Subtle square noise** — apply a 1-3% brightness gradient or noise to each square so they don't read as flat plastic. Could be a `QLinearGradient` from top to bottom with 2-3% lighter at top.
2. **Active piece shadow** — when a piece is animating to a new square, give it a `QGraphicsDropShadowEffect`. Remove when animation ends.
3. **Coordinate label refinement** — smaller, dimmer (`text_dim`), inside the edge squares' corners (like chess.com).
4. **Refined arrow** — give the green "better" arrow a soft outer glow (drop shadow with green tint). Smooth its pulse animation.
5. **Last-move highlight** — instead of flat yellow `board_from`, use a subtle gradient or inner glow. Consider chess.com's approach: the from-square is dimmer than the to-square.
6. **Active square (during navigation)** — when hovering a square that the user could right-click on, very subtle highlight.

### Phase 4 · Coach panel refinement (~1 hour)

In `app/ui/widgets/coach_panel.py`:

1. **Bigger card padding** (Phase 2 covers this but verify).
2. **Card elevation** — apply a level-1 drop shadow.
3. **Accent stripe** — instead of a flat color stripe on the left, use a subtle gradient (top: classification color full, bottom: classification color at 60% opacity).
4. **Eval delta badge** — already exists. Add a subtle entrance animation: fade in + slight scale from 0.95 to 1.0 over 200ms when a new card appears.
5. **Tactical keyword highlighting** — currently colored text. Consider a subtle background pill (background tint of the same color at 15% opacity) for more visual weight.
6. **Coach header** ("COACH") — uppercase, letter-spaced. Already done; verify it reads as a proper section header.

### Phase 5 · Top bar + branding (~30 min)

In `app/ui/main_window.py` TopBar:

1. **Logo refinement** — "ChessLens" should be the wordmark, larger and more confident. Consider 18-20pt at weight 700 with -0.5px letter-spacing.
2. **Icon buttons** — Flip, Voice, Pause, Profile, Export currently use emoji. Emoji rendering varies by Windows version. Consider using:
   - `qtawesome` package (Font Awesome / Material icons rendered as Qt icons) — small additional dep but standard
   - OR ship a small SVG set in `app/ui/icons/` and load via `QIcon`
   - The Flip icon (⇅) and others should be visually consistent
3. **Subtle bottom border** on the top bar to separate from content (1px, very subtle).
4. **Optional: subtle glassmorphism** — `QGraphicsBlurEffect` behind the top bar at 4-8px blur. Don't overdo. Test performance.

### Phase 6 · Move list polish (~1 hour)

In `app/ui/widgets/move_list.py`:

1. **Bigger row height** — from current to ~32-36px so moves don't feel cramped.
2. **Subtle row hover** — entire row gets a fill that grows from left over 120ms.
3. **Active move row** — accent border on the left (3-4px wide), slight background highlight, NOT a hard outline.
4. **Better white/black grouping** — visually separate the columns more clearly. Could be a faint vertical divider, or different background tints.
5. **Classification icons** — currently colored text characters (`!!`, `★`, `!`, `?!`, `?`, `??`). Consider giving each a subtle filled circle/pill background in the classification color at 15-20% opacity. Makes them read as badges, not text.
6. **Move number column** — slightly dimmer than the SAN. Use `text_dim`.

### Phase 7 · Eval graph refinement (~45 min)

In `app/ui/widgets/eval_graph.py`:

1. **Inset background** — the graph area should feel recessed. Use `bg_input` or even darker, with a 1px inner border in `border_subtle`.
2. **Smoother curve** — the current curve has hard segments. Use `QPainterPath` with `cubicTo` for smooth bezier curves.
3. **Classification dots** — currently small flat circles. Add a 1px halo (lighter ring around the dot) for the more important classifications (blunder, brilliant).
4. **Cursor line** — when hovering the graph, show a vertical line at the cursor position. Future: also show eval value as a tooltip.
5. **Subtle midline** — the 0.0 horizontal line should be visible but very subtle.

### Phase 8 · Final pass (~30 min)

1. **Subtitle box** — refine. The voice subtitle bar should look like a chip/pill, not a flat rectangle.
2. **Player labels** — wrap the "◆ Hayama_s (259) • you · 76%" text in a subtle pill background for visual weight.
3. **Run the full app**, navigate through a real game, screenshot every panel state, compare to before.
4. **Commit each phase separately** so we have a clean history.

---

## 4 · Quality bars

After each phase:

- **Visual diff**: take a screenshot, compare to the phase-start screenshot. The change should be a clear improvement, not a sideways move.
- **Functional regression**: load the sample PGN (button in left panel), navigate moves, toggle voice on/off, open profile dialog. Everything must still work.
- **Performance**: hovering, scrolling the move list, navigating — should feel instant. If any animation feels sluggish, simplify it.
- **No dead code**: remove commented-out blocks. If you tried something and abandoned it, delete the lines.

---

## 5 · Inspirations (look at these before designing)

- **chess.com Game Review** (2024+ design) — already the primary reference. The user has shown multiple screenshots.
- **lichess.org** — different aesthetic but very clean.
- **Linear app** (linear.app) — gold standard for dark-UI density and spacing.
- **Arc browser** — gradients and depth done tastefully.
- **Cursor IDE** — typography and dark backgrounds.
- **Vercel dashboard** — restrained, refined.

When in doubt, ask: "would this fit in Linear?" If yes, ship it. If it would look out of place in Linear, reconsider.

---

## 6 · What NOT to do

- Do not touch `app/core/` (analyzer, coach, pgn_parser). Stable.
- Do not touch `app/services/` (voice, sounds, user_profile). Stable.
- Do not introduce React, web tech, or any non-PySide6 UI.
- Do not bundle new fonts. Use system fonts only.
- Do not break `build_exe.bat`.
- Do not add an "options/preferences" dialog. Settings persist via existing JSON files.
- Do not invent new features. This is purely visual.
- Do not animate the board pieces beyond their existing animation. The board is sacred.
- Do not ship without taking a screenshot before/after for each phase.

---

## 7 · Definition of done for the whole session

- A PR-quality commit per phase
- All visual changes consistent with the design system in `theme.py`
- App launches maximized, runs at 60fps, voice works, analysis works
- `python -m pytest tests/` passes
- `build_exe.bat` produces a working `.exe`
- The before/after comparison clearly shows a more modern, more refined product

Start with Phase 0 (git init) and walk through each phase in order. Ask me before any architectural change. For purely visual decisions inside the brief, just proceed — show the result and we'll iterate.
