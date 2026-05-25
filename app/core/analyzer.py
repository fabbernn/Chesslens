"""
Game analyzer — runs Stockfish analysis on a parsed game in a QThread.

Emits progress signals as it works so the UI can show a progress bar
without freezing the event loop.

The analyzer is split into two pieces:
  * AnalyzedMove — pure data type, one entry per move
  * AnalyzerWorker — QObject worker that runs in a QThread

Pattern: create worker → move to thread → connect signals → start().
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

import chess

from PySide6.QtCore import QObject, Signal

from app.config import ENGINE_DEPTH
from app.core.coach import MoveExplainer
from app.core.pgn_parser import ParsedGame, time_taken_per_move
from app.services.stockfish import Engine, find_engine, download_engine


# ─────────────────────────────────────────────────────────────────────────────
#  ANALYZED MOVE — one entry per move
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class AnalyzedMove:
    index:        int                       # move index (0-based, plies)
    san:          str
    uci:          str
    from_sq:      int
    to_sq:        int
    fen_after:    str                       # position AFTER the move
    is_white:     bool
    move_number:  int                       # standard 1-based, both colors
    # Evaluation
    eval_before:  float = 0.0
    eval_after:   float = 0.0
    delta:        float = 0.0               # eval change from side's POV
    classification: str = "good"            # brilliant/best/good/inaccuracy/mistake/blunder
    best_move:    Optional[chess.Move] = None      # engine's #1 from position AFTER move (= what to play next)
    best_pv:      list[chess.Move] = field(default_factory=list)
    # The actual alternative to THIS move — engine's #1 from BEFORE this move
    # was played. This is the move the player "should have" chosen, and it's
    # what the coach's "Better: X" text references. The green arrow on the
    # board uses this so it visually matches the coach text.
    alternative_move: Optional[chess.Move] = None
    time_taken:   Optional[float] = None    # seconds
    # Position-aware coaching
    explanation:  dict = field(default_factory=dict)   # from MoveExplainer.explain()


@dataclass
class AnalysisResult:
    """Full per-game analysis output."""
    moves:           list[AnalyzedMove] = field(default_factory=list)
    ev_scores:       list[float] = field(default_factory=list)    # per-position eval
    white_accuracy:  int = 0
    black_accuracy:  int = 0
    stats:           dict[str, int] = field(default_factory=dict)
    parsed:          Optional[ParsedGame] = None


# ─────────────────────────────────────────────────────────────────────────────
#  CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
#  CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────
# Classifier threshold leniency for the opening. Slightly wider than
# coach.OPENING_PHASE_PLY (12) so the transition into the middlegame
# stays lenient — a -0.5 eval drop at move 14 is still likely a
# reasonable opening choice, not a true inaccuracy.
OPENING_CLASSIFIER_PHASE_PLY = 15


def classify(delta: float,
             played_is_best: bool = False,
             is_only_legal_move: bool = False,
             eval_before_side: float = 0.0,
             eval_after_side: float = 0.0,
             move_number: int = 1) -> str:
    """Classify a move using:
      delta              — eval change from side-to-move's POV
      played_is_best     — did the player pick the engine's #1 (or very close)?
      is_only_legal_move — was there only ONE legal move? (forced response)
      eval_before/after  — full evaluations, used to detect sacrifices / mate
      move_number        — ply-pair number (1-based). Used to give opening
                           moves lenient thresholds, since many legitimate
                           openings (Cow, London, hypermodern setups) are
                           NOT the engine's #1 pick but are perfectly playable.

    'Brilliant' is intentionally hard to earn:
      * Must be the engine's #1 choice
      * Must significantly improve the position (delta ≥ +0.40)
      * Must NOT be the only legal move (forced moves are never brilliant)

    A move that improves the eval but ISN'T the engine's top choice is
    capped at 'good' — it just means the engine slightly under-rated it
    at the search depth used. Calling that 'brilliant' contradicts the
    coach card which still recommends the engine's top choice.
    """
    # Forced moves: never brilliant. They were just "the move".
    if is_only_legal_move:
        return "best"

    # Brilliant requires hitting the engine's #1 AND a real eval gain
    if played_is_best and delta >= 0.40:
        return "brilliant"

    # Played the engine's top choice → "best"
    if played_is_best:
        return "best"

    # ── Player chose something other than the engine's #1 ───────────────────
    # Use LENIENT thresholds in the opening (first ~15 moves). Without
    # this, hypermodern systems like the Cow (1.e3 d3 Ne2 Nd2) get spammed
    # with "inaccuracy" labels even though they're legitimate openings —
    # the engine just prefers more central play.
    in_opening = move_number <= OPENING_CLASSIFIER_PHASE_PLY
    if in_opening:
        if   delta >= -0.60: return "good"
        elif delta >= -1.20: return "inaccuracy"
        elif delta >= -2.50: return "mistake"
        else:                return "blunder"

    # Middlegame / endgame — chess.com-aligned thresholds
    # Blunder requires a minimum -2.0 swing; -0.38 is never a blunder.
    if   delta >= -0.10: return "good"
    elif delta >= -0.50: return "inaccuracy"
    elif delta >= -2.00: return "mistake"
    else:                return "blunder"


_ACC_WEIGHTS = {
    "brilliant": 100, "best": 95, "good": 80,
    "inaccuracy": 60, "mistake": 30, "blunder": 5,
}


def _game_end_explanation(board: chess.Board, is_white: bool,
                          san: str, pgn_result: str) -> dict:
    """Return a game-end explanation dict for the final move, or {} if the
    position is not a recognised terminal state."""
    def wname(color: str) -> str:
        return "White" if color == "white" else "Black"

    if board.is_checkmate():
        winner = "white" if is_white else "black"
        w = wname(winner)
        return {
            "game_end": True, "game_end_type": "checkmate", "winner": winner,
            "reasons": ["checkmate"], "played_problems": [],
            "voice": f"{san} — checkmate! {w} wins.",
            "card":  f"Checkmate — {w} wins. A decisive conclusion to the game.",
        }
    if board.is_stalemate():
        return {
            "game_end": True, "game_end_type": "stalemate", "winner": "draw",
            "reasons": ["stalemate"], "played_problems": [],
            "voice": f"{san} — stalemate. The game ends in a draw.",
            "card":  ("Stalemate — the game is drawn. The opponent has no legal "
                      "moves but is not in check."),
        }
    if board.is_insufficient_material():
        return {
            "game_end": True, "game_end_type": "draw_material", "winner": "draw",
            "reasons": ["draw"], "played_problems": [],
            "voice": "Draw by insufficient material.",
            "card":  "Neither side has enough pieces to force checkmate. The game is drawn.",
        }
    if board.is_seventyfive_moves():
        return {
            "game_end": True, "game_end_type": "draw_rule", "winner": "draw",
            "reasons": ["draw"], "played_problems": [],
            "voice": "Draw by the seventy-five move rule.",
            "card":  "No pawn has moved and no capture has been made in 75 moves. The game is drawn.",
        }
    if board.is_fivefold_repetition():
        return {
            "game_end": True, "game_end_type": "draw_repetition", "winner": "draw",
            "reasons": ["draw"], "played_problems": [],
            "voice": "Draw by fivefold repetition.",
            "card":  "The same position has occurred five times. The game is drawn.",
        }
    # Non-forced end: resignation or agreed draw — read from PGN Result tag
    if pgn_result == "1/2-1/2":
        return {
            "game_end": True, "game_end_type": "draw_agreed", "winner": "draw",
            "reasons": ["draw"], "played_problems": [],
            "voice": "The players agreed to a draw.",
            "card":  "The game ends in an agreed draw.",
        }
    if pgn_result in ("1-0", "0-1"):
        winner = "white" if pgn_result == "1-0" else "black"
        loser  = "black" if winner == "white" else "white"
        w, l   = wname(winner), wname(loser)
        return {
            "game_end": True, "game_end_type": "resignation", "winner": winner,
            "reasons": ["resignation"], "played_problems": [],
            "voice": f"{l} resigns. {w} wins.",
            "card":  f"{l} resigned. {w} wins the game.",
        }
    return {}


def accuracy_for(moves: list[AnalyzedMove]) -> int:
    """Compute a 0-100 accuracy score from a move list."""
    if not moves:
        return 0
    total = sum(_ACC_WEIGHTS.get(m.classification, 50) for m in moves)
    return round(total / len(moves))


# ─────────────────────────────────────────────────────────────────────────────
#  WORKER — runs analysis in a QThread
# ─────────────────────────────────────────────────────────────────────────────
class AnalyzerWorker(QObject):
    """
    Analyzes a ParsedGame using Stockfish.

    Signals:
        progress(percent, message)
        finished(AnalysisResult)
        failed(error_message)
    """
    progress  = Signal(int, str)
    finished  = Signal(object)        # AnalysisResult
    failed    = Signal(str)
    cancelled = Signal()              # user-initiated cancel (no error dialog)

    def __init__(self, parsed: ParsedGame, depth: int = ENGINE_DEPTH) -> None:
        super().__init__()
        self._parsed = parsed
        self._depth = depth
        self._cancelled = False

    # ─────────────────────────────────────────────────────────────────────
    def cancel(self) -> None:
        self._cancelled = True

    # ─────────────────────────────────────────────────────────────────────
    def run(self) -> None:
        """Slot that does the actual work. Connect to QThread.started."""
        try:
            self._run()
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")

    def _run(self) -> None:
        moves = self._parsed.moves
        if not moves:
            self.failed.emit("No moves in PGN")
            return

        # 1. Find/download Stockfish
        self.progress.emit(0, "Locating engine…")
        engine_path = find_engine()
        if engine_path is None:
            self.progress.emit(2, "Downloading Stockfish (one-time)…")
            engine_path = download_engine(
                progress_cb=lambda msg: self.progress.emit(2, msg)
            )
        if engine_path is None:
            self.failed.emit("Stockfish not found and download failed")
            return

        # 2. Build position sequence
        starting_fen = self._parsed.starting_fen
        board = chess.Board(starting_fen)
        fens = [board.fen()]
        for m in moves:
            board.push(m)
            fens.append(board.fen())

        # 3. Analyze each position
        ev_scores: list[float] = []
        best_moves: list[Optional[chess.Move]] = []
        best_pvs: list[list[chess.Move]] = []
        total = len(fens)

        with Engine(engine_path, depth=self._depth) as eng:
            for i, fen in enumerate(fens):
                if self._cancelled:
                    self.cancelled.emit()
                    return
                pct = int(5 + (i / total) * 90)
                self.progress.emit(pct, f"Analysing position {i+1}/{total}…")
                try:
                    info = eng.analyse(chess.Board(fen))
                    score_obj = info["score"].white()
                    if score_obj.is_mate():
                        mate = score_obj.mate()
                        # Encode distance: M1→9999, M2→9998, ..., preserving sign.
                        # Anything >9000 is treated as "forced mate" in the UI.
                        if mate is not None and mate > 0:
                            cp = 10000.0 - min(abs(mate), 999)
                        else:
                            cp = -(10000.0 - min(abs(mate or 1), 999))
                    else:
                        cp = score_obj.score(mate_score=10000) / 100.0
                    pv = info.get("pv", []) or []
                    best = pv[0] if pv else None
                except Exception:
                    cp = 0.0
                    pv = []
                    best = None
                ev_scores.append(cp)
                best_moves.append(best)
                best_pvs.append(pv)

        # 4. Build AnalyzedMove records
        self.progress.emit(96, "Classifying moves…")
        times = time_taken_per_move(self._parsed.clock_times)
        explainer = MoveExplainer()

        analyzed: list[AnalyzedMove] = []
        board = chess.Board(starting_fen)
        for i, move in enumerate(moves):
            pre_eval  = ev_scores[i]
            post_eval = ev_scores[i + 1]
            is_white  = board.turn == chess.WHITE
            pre_side  = pre_eval  if is_white else -pre_eval
            post_side = post_eval if is_white else -post_eval
            delta = post_side - pre_side

            # ── Rich classification context ─────────────────────────────────
            # The engine's #1 from BEFORE this move was played
            engine_best = best_moves[i] if i < len(best_moves) else None
            played_is_best = (engine_best is not None and move == engine_best)

            # Was the player forced? (only one legal response)
            try:
                n_legal = sum(1 for _ in board.legal_moves)
            except Exception:
                n_legal = 2  # safe fallback — assume not forced
            is_only_legal_move = (n_legal == 1)

            cls = classify(
                delta,
                played_is_best=played_is_best,
                is_only_legal_move=is_only_legal_move,
                eval_before_side=pre_side,
                eval_after_side=post_side,
                move_number=i // 2 + 1,
            )

            san = self._parsed.sans[i] if i < len(self._parsed.sans) else move.uci()

            # Position-aware reasoning — analyzed BEFORE we push the move
            engine_pv   = best_pvs[i] if i < len(best_pvs) else []
            try:
                explanation = explainer.explain(
                    board, move, engine_best,
                    best_pv=engine_pv,
                    delta=delta,
                    move_number=i // 2 + 1,
                    played_is_best=played_is_best,
                    is_only_legal_move=is_only_legal_move,
                )
            except Exception:
                explanation = {"voice": "", "card": "", "reasons": [],
                                "played_problems": []}

            board.push(move)

            # Override explanation for the final move when the game has ended.
            # This replaces generic move feedback ("good development of the
            # bishop") with a result-aware message ("checkmate — White wins").
            if i == len(moves) - 1:
                end_exp = _game_end_explanation(
                    board, is_white, san, self._parsed.result)
                if end_exp:
                    explanation = end_exp

            analyzed.append(AnalyzedMove(
                index = i,
                san = san,
                uci = move.uci(),
                from_sq = move.from_square,
                to_sq = move.to_square,
                fen_after = board.fen(),
                is_white = is_white,
                move_number = i // 2 + 1,
                eval_before = round(pre_eval, 2),
                eval_after = round(post_eval, 2),
                delta = round(delta, 2),
                classification = cls,
                # "best_move" / "best_pv" still describe what's BEST from the
                # position AFTER this move — useful for showing what to do next.
                best_move = best_moves[i + 1] if (i + 1) < len(best_moves) else None,
                best_pv   = best_pvs[i + 1]   if (i + 1) < len(best_pvs)   else [],
                # "alternative_move" is what they SHOULD have played instead of
                # this move — the engine's #1 from BEFORE the move. The green
                # arrow on the board uses this so it matches "Better: X" text.
                alternative_move = engine_best,
                time_taken = times[i] if i < len(times) else None,
                explanation = explanation,
            ))

        # 5. Stats + accuracy
        stats = {k: 0 for k in ["brilliant","best","good","inaccuracy","mistake","blunder"]}
        for a in analyzed:
            stats[a.classification] = stats.get(a.classification, 0) + 1

        white_moves = [a for a in analyzed if a.is_white]
        black_moves = [a for a in analyzed if not a.is_white]

        result = AnalysisResult(
            moves          = analyzed,
            ev_scores      = ev_scores,
            white_accuracy = accuracy_for(white_moves),
            black_accuracy = accuracy_for(black_moves),
            stats          = stats,
            parsed         = self._parsed,
        )

        self.progress.emit(100, "")
        self.finished.emit(result)
