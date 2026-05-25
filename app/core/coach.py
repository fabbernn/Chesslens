"""
MoveExplainer — generates position-aware reasoning for why one move beats another.
Uses python-chess to inspect actual tactical features of the position.
"""

from dataclasses import dataclass, field
import chess


# ── Phase boundaries (in plies/half-moves, 1-based) ──────────────────────
# These constants gate opening-specific coaching logic. Tune them here
# rather than searching for hard-coded "12" or "7" scattered through the
# file. analyzer.classify() has its own constant (more lenient) for
# classification threshold leniency.
OPENING_PHASE_PLY        = 12   # Cutoff for principle-based coach text
EARLY_DEVELOPMENT_PLY    = 12   # Cutoff for "develop a minor piece" reason
EARLY_CENTRAL_PAWN_PLY   = 10   # Cutoff for "grab central space" reason
EARLY_QUEEN_PLY          = 7    # Queen sortie before this ply is flagged
# Eval drop below this is small enough to defer to principle-based
# commentary instead of the usual "X was stronger" framing.
OPENING_DELTA_TOLERANCE  = 0.8


@dataclass
class OpeningPrinciples:
    """Result of _check_opening_principles. Replaces an ad-hoc dict so
    callers get autocomplete + type checking, and so the only two
    relevant axes (positive vs negative principle hits) are obvious.
    """
    affirmations: list = field(default_factory=list)
    violations:   list = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.affirmations or self.violations)


# ── Piece values + names ─────────────────────────────────────────────────
PV = {
    chess.PAWN:   1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK:   5, chess.QUEEN:  9, chess.KING:   0,
}
PN = {
    chess.PAWN:   "pawn",   chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK:   "rook",   chess.QUEEN:  "queen",  chess.KING:   "king",
}

# Common opening squares for development
CENTER       = {chess.D4, chess.E4, chess.D5, chess.E5,
                chess.C4, chess.F4, chess.C5, chess.F5}
CENTER_INNER = {chess.D4, chess.E4, chess.D5, chess.E5}


# ── Pawn-affirmation lookup tables ───────────────────────────────────────
# Per-color: { destination_square: affirmation_phrase }. Drives principle-
# based coach text for opening pawn moves. Edge pawns (a/h) deliberately
# absent — those genuinely ARE slow and the standard "X was stronger"
# framing is honest feedback there.
_PAWN_AFFIRMATIONS_WHITE = {
    chess.D4: "staking out the centre",
    chess.E4: "staking out the centre",
    chess.D3: "supporting the centre",
    chess.E3: "supporting the centre",
    chess.C4: "a flank pawn supporting central play",
    chess.F4: "a flank pawn supporting central play",
    chess.B3: "preparing a fianchetto setup",
    chess.G3: "preparing a fianchetto setup",
    chess.C3: "a solid setup move",
    chess.F3: "a solid setup move",
}
_PAWN_AFFIRMATIONS_BLACK = {
    chess.D5: "staking out the centre",
    chess.E5: "staking out the centre",
    chess.D6: "supporting the centre",
    chess.E6: "supporting the centre",
    chess.C5: "a flank pawn supporting central play",
    chess.F5: "a flank pawn supporting central play",
    chess.B6: "preparing a fianchetto setup",
    chess.G6: "preparing a fianchetto setup",
    chess.C6: "a solid setup move",
    chess.F6: "a solid setup move",
}


def _sq(sq):
    """Square name like 'e4'."""
    return chess.square_name(sq)


def _fmt_move(move):
    """Format a move as 'e2 to e4'."""
    if not move:
        return "the engine's choice"
    u = move.uci()
    return f"{u[:2]} to {u[2:4]}"


class MoveExplainer:
    """
    Analyzes the actual position to generate human-readable reasoning
    for why one chess move is better than another.
    """

    def explain(self, board_before, played_move, best_move, played_pv=None,
                best_pv=None, delta=0.0, move_number=1,
                played_is_best=False, is_only_legal_move=False):
        """
        Generate reasoning. Returns dict with:
          'reasons'  — list of short reason strings
          'voice'    — natural sentence for TTS
          'card'     — fuller explanation for the coaching card
        """
        # FORCED MOVE — no real choice was available. Don't suggest a
        # "better" alternative; just label it as the only legal response.
        if is_only_legal_move:
            played_san = self._safe_san(board_before, played_move)
            return {
                "reasons": ["forced move — only legal response"],
                "voice":   f"{played_san} was forced — the only legal move.",
                "card":    f"{played_san} was the only legal move in this "
                           f"position. No alternative was available.",
                "played_problems": [],
            }

        if not best_move:
            return {"reasons": [], "voice": "", "card": ""}

        # If played the engine's choice, just affirm it
        if played_move == best_move or played_is_best:
            return self._explain_good_move(board_before, played_move)

        # ── OPENING-PRINCIPLE AWARENESS ──────────────────────────────────
        # Many legitimate openings (Cow, London, hypermodern systems) are
        # NOT the engine's #1 but follow sound principles. The helper
        # self-gates on move number; we just check the eval drop is small
        # enough that principle-based coaching is appropriate.
        if abs(delta) <= OPENING_DELTA_TOLERANCE:
            principles = self._check_opening_principles(
                board_before, played_move, move_number)
            if principles:
                return self._explain_opening_move(
                    board_before, played_move, best_move,
                    principles, delta)

        reasons = []
        played_problems = []

        played_piece = board_before.piece_at(played_move.from_square)
        best_piece   = board_before.piece_at(best_move.from_square)
        is_white     = board_before.turn == chess.WHITE

        # Pre-compute boards after each move
        board_best   = board_before.copy()
        board_best.push(best_move)
        board_played = board_before.copy()
        board_played.push(played_move)

        # ─── REASONS THE BEST MOVE IS GOOD ──────────────────────────────
        # 1. Captures a piece
        cap_by_best = board_before.piece_at(best_move.to_square)
        if cap_by_best:
            attackers = board_before.attackers(played_piece.color,
                                                best_move.to_square)
            defenders = board_before.attackers(not played_piece.color,
                                                best_move.to_square)
            best_val = PV.get(best_piece.piece_type, 0)
            cap_val  = PV.get(cap_by_best.piece_type, 0)
            if not defenders or cap_val >= best_val:
                reasons.append(
                    f"capture the {PN[cap_by_best.piece_type]} on "
                    f"{_sq(best_move.to_square)}"
                )
            elif cap_val > best_val:
                reasons.append(
                    f"win material with the capture on "
                    f"{_sq(best_move.to_square)}"
                )

        # 2. Gives check
        if board_best.is_check():
            if board_best.is_checkmate():
                reasons.append("deliver checkmate")
            else:
                reasons.append("give check, forcing the opponent to respond")

        # 3. Fork / multi-attack
        attacked_by_moved = board_best.attacks(best_move.to_square)
        valuable_attacks = []
        for sq in attacked_by_moved:
            p = board_best.piece_at(sq)
            if p and p.color != best_piece.color:
                pval = PV.get(p.piece_type, 0)
                mover_val = PV.get(best_piece.piece_type, 0)
                if pval > mover_val or p.piece_type == chess.KING:
                    valuable_attacks.append((sq, p))
        if len(valuable_attacks) >= 2:
            names = [PN[p.piece_type] for _, p in valuable_attacks[:2]]
            reasons.append(f"fork the opponent's {' and '.join(names)}")
        elif valuable_attacks and not cap_by_best:
            sq, p = valuable_attacks[0]
            reasons.append(f"attack the {PN[p.piece_type]} on {_sq(sq)}")

        # 4. Castles
        if board_before.is_castling(best_move):
            side = ("kingside" if best_move.to_square in (chess.G1, chess.G8)
                    else "queenside")
            reasons.append(f"castle {side} and put the king in safety")

        # 5. Develops a minor piece (early game)
        if (move_number <= EARLY_DEVELOPMENT_PLY and not reasons
                and best_piece.piece_type in (chess.KNIGHT, chess.BISHOP)):
            home_rank = 0 if is_white else 7
            if chess.square_rank(best_move.from_square) == home_rank:
                reasons.append(
                    f"develop the {PN[best_piece.piece_type]} "
                    f"toward active squares"
                )

        # 6. Central control by pawn (e.g. d4/e4)
        if (move_number <= EARLY_CENTRAL_PAWN_PLY and not reasons
                and best_piece.piece_type == chess.PAWN
                and best_move.to_square in CENTER_INNER):
            reasons.append(
                f"grab central space with the pawn on "
                f"{_sq(best_move.to_square)}"
            )

        # ─── PROBLEMS WITH THE PLAYED MOVE ──────────────────────────────
        played_to = played_move.to_square
        opponent_attackers = board_played.attackers(
            not played_piece.color, played_to)
        own_defenders = board_played.attackers(played_piece.color, played_to)
        played_val = PV.get(played_piece.piece_type, 0)

        if opponent_attackers:
            min_atk_val = min(
                PV.get(board_played.piece_at(a).piece_type, 99)
                for a in opponent_attackers
            )
            if (min_atk_val < played_val
                    and len(own_defenders) <= len(opponent_attackers) - 1):
                played_problems.append(
                    f"your {PN[played_piece.piece_type]} on {_sq(played_to)} "
                    f"can be captured by a lower-value piece"
                )
            elif not own_defenders and played_val >= 3:
                played_problems.append(
                    f"your {PN[played_piece.piece_type]} on {_sq(played_to)} "
                    f"is undefended"
                )

        # B. Played move missed a capture
        if cap_by_best and played_move.to_square != best_move.to_square:
            played_to_piece = board_before.piece_at(played_move.to_square)
            if (not played_to_piece
                    or PV.get(played_to_piece.piece_type, 0)
                       < PV.get(cap_by_best.piece_type, 0)):
                if not any("capture" in r for r in reasons):
                    played_problems.append(
                        f"you missed capturing the "
                        f"{PN[cap_by_best.piece_type]} on "
                        f"{_sq(best_move.to_square)}"
                    )

        # C. Played move ignored a threat
        threats_before = self._find_threats_to(
            board_before, played_piece.color)
        if threats_before and not played_problems:
            highest_threat = max(threats_before, key=lambda t: t[1])
            sq, val = highest_threat
            if val >= 3:
                played_problems.append(
                    f"your {PN[board_before.piece_at(sq).piece_type]} on "
                    f"{_sq(sq)} was under threat"
                )

        # ─── BUILD OUTPUT ──────────────────────────────────────────────
        if not reasons:
            if abs(delta) >= 2.0:
                reasons.append("avoid significant material loss")
            elif abs(delta) >= 0.8:
                reasons.append(
                    "keep better piece coordination and central control")
            else:
                reasons.append("achieve slightly better piece activity")

        reasons_str = " and ".join(reasons[:2])

        played_san = self._safe_san(board_before, played_move)
        best_san   = self._safe_san(board_before, best_move)

        if played_problems:
            voice = (f"You played {played_san}, but {best_san} was stronger."
                     f" It would {reasons_str}. Also, {played_problems[0]}.")
        else:
            voice = (f"You played {played_san}, but {best_san} was stronger."
                     f" It would {reasons_str}.")

        card_parts = [
            f"Better: {best_san} ({_fmt_move(best_move)})",
            f"This would {reasons_str}.",
        ]
        if played_problems:
            card_parts.append(
                f"Problem with your move: {played_problems[0]}.")

        # Engine PV continuation
        if best_pv and len(best_pv) >= 3:
            tmp = board_before.copy()
            tmp.push(best_pv[0])
            try:
                tmp.push(best_pv[1])
                third = tmp.san(best_pv[2])
                card_parts.append(f"Engine plan: {best_san} … then {third}.")
            except Exception:
                pass

        return {
            "reasons":         reasons,
            "voice":           voice,
            "card":            "\n".join(card_parts),
            "played_problems": played_problems,
        }

    # ─── helpers ────────────────────────────────────────────────────────
    def _explain_good_move(self, board_before, move):
        """When the user played the best move."""
        piece = board_before.piece_at(move.from_square)
        cap   = board_before.piece_at(move.to_square)
        if cap:
            voice = f"Good capture — winning the {PN[cap.piece_type]}."
        elif board_before.is_castling(move):
            voice = "Good — castling to king safety."
        elif piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            voice = f"Good development of the {PN[piece.piece_type]}."
        else:
            voice = "The engine completely agrees with this move."
        return {"reasons": [], "voice": voice, "card": voice,
                "played_problems": []}

    def _check_opening_principles(self, board_before, move,
                                  move_number) -> OpeningPrinciples:
        """Inspect an opening move against classical principles.

        Self-gates on `move_number` — returns an empty OpeningPrinciples
        if outside the opening phase, so callers can call this
        unconditionally and just check the result.

        Designed to be CHARITABLE — prefers affirmations to violations.
        Goal: stop labelling sensible opening moves as mistakes.
        """
        out = OpeningPrinciples()
        if move_number > OPENING_PHASE_PLY:
            return out

        piece = board_before.piece_at(move.from_square)
        if piece is None:
            return out

        is_white   = piece.color == chess.WHITE
        home_rank  = 0 if is_white else 7
        from_rank  = chess.square_rank(move.from_square)
        to_file    = chess.square_file(move.to_square)

        # Knight development from the home square
        if piece.piece_type == chess.KNIGHT and from_rank == home_rank:
            out.affirmations.append("developing the knight")
            if to_file in (0, 7):
                out.violations.append(
                    "a knight on the rim limits its range"
                )

        # Bishop development from the home square
        if piece.piece_type == chess.BISHOP and from_rank == home_rank:
            out.affirmations.append("developing the bishop")

        # Pawn moves — table lookup keyed on destination square
        if piece.piece_type == chess.PAWN:
            table = (_PAWN_AFFIRMATIONS_WHITE if is_white
                     else _PAWN_AFFIRMATIONS_BLACK)
            phrase = table.get(move.to_square)
            if phrase is not None:
                out.affirmations.append(phrase)

        # Castling
        if board_before.is_castling(move):
            side = ("kingside" if move.to_square in (chess.G1, chess.G8)
                    else "queenside")
            out.affirmations.append(f"castling {side} for king safety")

        # Early queen sortie (queen leaves home to an empty square —
        # captures are usually justified by the material gain)
        if (piece.piece_type == chess.QUEEN
                and move_number <= EARLY_QUEEN_PLY
                and board_before.piece_at(move.to_square) is None):
            out.violations.append(
                "developing the queen this early can lose tempo if attacked"
            )

        return out

    def _explain_opening_move(self, board_before, played_move, best_move,
                              principles: OpeningPrinciples, delta):
        """Build an opening-aware explanation. Affirms what the move does
        right, mentions "better" softly so the user doesn't feel scolded
        for playing a perfectly fine opening system.
        """
        played_san = self._safe_san(board_before, played_move)
        best_san   = (self._safe_san(board_before, best_move)
                      if best_move else None)
        affirms    = principles.affirmations
        violations = principles.violations

        # Voice line — short, positive when possible
        if affirms and not violations:
            voice = f"{played_san} — {affirms[0]}. A solid opening move."
        elif affirms and violations:
            voice = f"{played_san} — {affirms[0]}, though {violations[0]}."
        elif violations:
            voice = f"{played_san} — careful, {violations[0]}."
        else:
            voice = f"{played_san} is a reasonable opening move."

        # Card text — engine alternative as info, not a scolding
        card_lines = []
        if affirms:
            card_lines.append(
                f"{played_san} follows opening principles: {affirms[0]}."
            )
        else:
            card_lines.append(f"{played_san} is a playable opening move.")
        if violations:
            card_lines.append(f"One concern: {violations[0]}.")
        if best_san and best_san != played_san:
            card_lines.append(
                f"The engine slightly preferred {best_san}, but in the "
                f"opening many moves are reasonable."
            )

        return {
            "reasons":         affirms or violations,
            "voice":           voice,
            "card":            "\n".join(card_lines),
            "played_problems": [],
        }

    def _find_threats_to(self, board, color):
        """Return [(square, value)] of friendly pieces opponent threatens."""
        threats = []
        for sq in chess.SQUARES:
            p = board.piece_at(sq)
            if not p or p.color != color:
                continue
            attackers = board.attackers(not color, sq)
            defenders = board.attackers(color, sq)
            if not attackers:
                continue
            min_atk_val = min(
                PV.get(board.piece_at(a).piece_type, 99) for a in attackers
            )
            pval = PV.get(p.piece_type, 0)
            if min_atk_val < pval and not defenders:
                threats.append((sq, pval))
        return threats

    def _safe_san(self, board, move):
        """Return SAN, falling back to UCI if illegal in this position."""
        try:
            return board.san(move)
        except Exception:
            try:
                return move.uci()
            except Exception:
                return "?"
