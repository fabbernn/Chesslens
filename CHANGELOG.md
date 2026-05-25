# Changelog

All notable changes to ChessLens are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.0] - 2026-05-25

### Added
- Stockfish engine integration — full game analysis at depth 16
- Move classification — Brilliant / Best / Good / Inaccuracy / Mistake / Blunder with accuracy scores
- AI voice coach — Kokoro ONNX TTS with pyttsx3 fallback, speaks move-by-move coaching out loud
- Board color themes — 6 Lichess-style board palettes
- Piece sets — Cburnett, Merida, Alpha (36 open-source Lichess SVGs)
- Opening detection — named opening displayed from PGN header
- User profile auto-color — avatar and accent derived from username
- Eval bar — animated vertical evaluation indicator with pill shape
- Eval graph — clickable momentum curve for the full game
- Sound effects — move, capture, check, castle, promotion, game-end, and ready chime (7 WAV files)
- Accuracy scores — 0–100% per player, chess.com-style breakdown
