# ChessLens

**A free, offline chess game analyzer with an AI voice coach.**  
Paste any PGN → get Stockfish analysis + move-by-move coaching — no account, no ads, no cloud.

---

## What it does

- **Full game analysis** — Stockfish evaluates every position at depth 16
- **Move classification** — Brilliant !! / Best ★ / Good ! / Inaccuracy ?! / Mistake ? / Blunder ??
- **AI voice coach** — says "Knight to f6 was a mistake — you left the e4 pawn hanging" out loud as you step through moves
- **Accuracy scores** — chess.com-style 0–100% accuracy per player
- **Per-player summary** — move-quality breakdown for White and Black separately after analysis
- **Eval bar + graph** — animated vertical eval bar and a clickable curve showing the game's momentum
- **Board customization** — 3 Lichess piece sets (Cburnett, Merida, Alpha) + 6 board color themes
- **Sound effects** — move, capture, check, castle, promotion, and a ready chime
- **Works offline** — Stockfish downloads once (~10 MB); AI voice downloads once (~100 MB); nothing else phoned home

---

## Download

**Easiest:** grab `ChessLens.exe` from the [Releases page](../../releases) — double-click, no install needed.

**From source:**
```
git clone <this-repo>
cd chesslens_pyside
RUN_CHESSLENS.vbs
```
Python 3.10+ required. Two launch options:

| File | Use when… |
|---|---|
| `RUN_CHESSLENS.vbs` | Normal use — launches silently via `pythonw`, no CMD window |
| `START_CHESSLENS_DEBUG.bat` | Debugging — CMD window stays open so you can see errors/tracebacks |

The VBS finds `pythonw.exe` automatically (checks PATH, then `%LOCALAPPDATA%\Programs\Python\`).  
The BAT installs/upgrades dependencies from `requirements.txt` on first run — run it once after a fresh clone, then switch to the VBS.

---

## How to use

1. Get your PGN:
   - **Chess.com:** open the game → Share & Export → Copy PGN
   - **Lichess:** game page → Share & Export → Copy PGN
2. Paste it into the box and click **Analyze Game**
3. First run: Stockfish downloads automatically (~10 MB, takes ~10s)
4. Step through moves with **← →** keys or click the move list
5. Click the eval graph to jump to any moment in the game
6. Enable **Voice** (top bar) for spoken coaching — first time downloads the AI model (~100 MB)

---

## Screenshots

To add screenshots: run ChessLens, analyze a game, and take a screenshot showing the board, eval bar, and coach panel. Place images in `docs/screenshots/` and link them here with `![Description](docs/screenshots/your-image.png)`.

---

## Building the .exe yourself

```
build_exe.bat
```
Installs PyInstaller, bundles everything into a single `ChessLens.exe` (~70 MB), and copies it to `%USERPROFILE%\Documents\ChessLens.exe`.

---

## Tech stack

| Layer | Choice |
|---|---|
| UI | PySide6 (Qt 6) |
| Chess logic | python-chess |
| Engine | Stockfish (auto-downloaded) |
| AI voice | Kokoro ONNX + pyttsx3 fallback |
| Packaging | PyInstaller (one-file exe) |

---

## Architecture (for contributors)

```
chesslens_pyside/
├── main.py                      20-line entry point
├── app/
│   ├── config.py                Paths, sizes, constants
│   ├── core/                    Qt-free Python logic
│   │   ├── analyzer.py          Stockfish QThread worker + move classifier
│   │   ├── coach.py             Position-aware move explainer
│   │   └── pgn_parser.py        PGN + %clk parsing
│   ├── ui/
│   │   ├── theme.py             Color/font/spacing tokens (single source of truth)
│   │   ├── main_window.py       Three-pane window orchestrator
│   │   └── widgets/             Board, eval bar, move list, coach panel, ...
│   └── services/
│       ├── voice.py             Kokoro TTS + pyttsx3 fallback
│       ├── sounds.py            QSoundEffect player
│       └── stockfish.py         Engine finder + auto-downloader
├── assets/
│   └── pieces/                  Lichess open-source SVGs (cburnett / merida / alpha)
├── installer/                   Inno Setup script + build bat
├── docs/dev/scripts/            Developer utility scripts
└── .github/workflows/           GitHub Actions CI/release
```

Design rules:
- `app/core/` is Qt-free — pure Python, testable in isolation
- `app/ui/widgets/` is presentation only — receives data, emits signals
- `app/services/` owns side effects — audio, subprocess, network
- `theme.py` is the single source of truth for colors/fonts — no widget hardcodes a value

---

## License

Source code: MIT — see [LICENSE](LICENSE).

Chess piece sets (in `assets/pieces/`):
- **Cburnett** — GPL v2+ / CC BY-SA 3.0 — Colin M.L. Burnett, via Lichess
- **Merida** — GPL v2+ — Armando Hernandez Marroquin, via Lichess
- **Alpha** — GPL v2+ — Eric Bentzen, via Lichess
