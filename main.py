import json, os, sys, urllib.request

U = os.environ["MAKEFUN_ENV_URL"]

# --- piece values and tables -------------------------------------------------
V = {"p": 100, "n": 320, "b": 330, "r": 500, "q": 900, "k": 0}

PAWN = (0, 0, 0, 0, 0, 0, 0, 0,
        5, 10, 10, -20, -20, 10, 10, 5,
        5, -5, -10, 0, 0, -10, -5, 5,
        0, 0, 0, 20, 20, 0, 0, 0,
        5, 5, 10, 25, 25, 10, 5, 5,
        10, 10, 20, 30, 30, 20, 10, 10,
        50, 50, 50, 50, 50, 50, 50, 50,
        0, 0, 0, 0, 0, 0, 0, 0)

KNIGHT = (-50, -40, -30, -30, -30, -30, -40, -50,
          -40, -20, 0, 5, 5, 0, -20, -40,
          -30, 5, 10, 15, 15, 10, 5, -30,
          -30, 0, 15, 20, 20, 15, 0, -30,
          -30, 5, 15, 20, 20, 15, 5, -30,
          -30, 0, 10, 15, 15, 10, 0, -30,
          -40, -20, 0, 0, 0, 0, -20, -40,
          -50, -40, -30, -30, -30, -30, -40, -50)

BISHOP = (-20, -10, -10, -10, -10, -10, -10, -20,
          -10, 5, 0, 0, 0, 0, 5, -10,
          -10, 10, 10, 10, 10, 10, 10, -10,
          -10, 0, 10, 10, 10, 10, 0, -10,
          -10, 5, 5, 10, 10, 5, 5, -10,
          -10, 0, 5, 10, 10, 5, 0, -10,
          -10, 0, 0, 0, 0, 0, 0, -10,
          -20, -10, -10, -10, -10, -10, -10, -20)

KING = (-25, -20, -20, -20, -20, -20, -20, -25,
        -25, -10, 0, 0, 0, 0, -10, -25,
        -25, 0, 5, 5, 5, 5, 0, -25,
        -20, 0, 10, 10, 10, 10, 0, -20,
        -10, 0, 10, 10, 10, 10, 0, -10,
        -5, 5, 10, 10, 10, 10, 5, -5,
        -20, 0, 5, 0, 0, 0, 0, -20,
        -25, -20, -20, -20, -20, -20, -20, -25)

KING_END = (-50, -30, -30, -30, -30, -30, -30, -50,
            -30, -10, 0, 0, 0, 0, -10, -30,
            -30, 0, 20, 30, 30, 20, 0, -30,
            -30, 0, 30, 40, 40, 30, 0, -30,
            -30, 0, 30, 40, 40, 30, 0, -30,
            -30, 0, 20, 30, 30, 20, 0, -30,
            -30, -10, 0, 0, 0, 0, -10, -30,
            -50, -30, -30, -30, -30, -30, -30, -50)

# one flat table per piece letter, so eval is a single list index
TAB = {"p": PAWN, "n": KNIGHT, "b": BISHOP, "r": KNIGHT, "q": KNIGHT, "k": KING}

KNIGHT_DIRS = (17, 15, 10, 6, -6, -10, -15, -17)
KING_DIRS = (1, -1, 8, -8, 9, 7, -7, -9)
ROOK_DIRS = ((0, 1), (0, -1), (1, 0), (-1, 0))
BISHOP_DIRS = ((1, 1), (1, -1), (-1, 1), (-1, -1))


def parse(fen):
    """board dict, side to move, castling mask, ep square, halfmove clock."""
    p = fen.split()
    brd = {}
    r, f = 7, 0
    for ch in p[0]:
        if ch == "/":
            r -= 1
            f = 0
        elif ch.isdigit():
            f += int(ch)
        else:
            brd[r * 8 + f] = ch
            f += 1
    mask = 0
    for c in p[2]:
        mask |= {"K": 1, "Q": 2, "k": 4, "q": 8}.get(c, 0)
    eps = -1
    if p[3] != "-":
        eps = (int(p[3][1]) - 1) * 8 + "abcdefgh".index(p[3][0])
    return brd, p[1], mask, eps, int(p[4])


def find_king(brd, up):
    k = "K" if up else "k"
    for s, p in brd.items():
        if p == k:
            return s
    return -1


def attacked(brd, s, by_white):
    """Is s attacked by the given side? Sliders walk out from s."""
    f, r = s & 7, s >> 3
    # pawns: a white pawn on rank r-1 attacks upward onto r
    pd = -8 if by_white else 8
    want = "P" if by_white else "p"
    for df in (-1, 1):
        f2 = f + df
        if 0 <= f2 <= 7:
            t = s + pd + df
            if 0 <= t < 64 and brd.get(t) == want:
                return True
    wn = "N" if by_white else "n"
    for d in KNIGHT_DIRS:
        t = s + d
        if 0 <= t < 64 and abs((t & 7) - f) <= 2 and brd.get(t) == wn:
            return True
    wk = "K" if by_white else "k"
    for d in KING_DIRS:
        t = s + d
        if 0 <= t < 64 and abs((t & 7) - f) <= 1 and brd.get(t) == wk:
            return True
    rq = ("R" if by_white else "r", "Q" if by_white else "q")
    bq = ("B" if by_white else "b", "Q" if by_white else "q")
    for df, dr in ROOK_DIRS:
        f2, r2 = f + df, r + dr
        while 0 <= f2 <= 7 and 0 <= r2 <= 7:
            p = brd.get(r2 * 8 + f2)
            if p:
                if p in rq:
                    return True
                break
            f2 += df
            r2 += dr
    for df, dr in BISHOP_DIRS:
        f2, r2 = f + df, r + dr
        while 0 <= f2 <= 7 and 0 <= r2 <= 7:
            p = brd.get(r2 * 8 + f2)
            if p:
                if p in bq:
                    return True
                break
            f2 += df
            r2 += dr
    return False


def gen(brd, up, mask, eps):
    """Pseudo-legal moves as (from, to, promo, flag); flag 1 ep, 2 castle, 3 double push."""
    out = []
    add = out.append
    for s, p in brd.items():
        if p.isupper() != up:
            continue
        t = p.lower()
        f, r = s & 7, s >> 3
        if t == "p":
            d = 8 if up else -8
            last = 7 if up else 0
            one = s + d
            if 0 <= one < 64 and one not in brd:
                if one >> 3 == last:
                    for q in "qrbn":
                        add((s, one, q, 0))
                else:
                    add((s, one, "", 0))
                    two = one + d
                    if two not in brd and r == (1 if up else 6):
                        add((s, two, "", 3))
            for df in (-1, 1):
                f2 = f + df
                if not 0 <= f2 <= 7:
                    continue
                to = s + d + df
                if not 0 <= to < 64:
                    continue
                v = brd.get(to)
                if v is not None:
                    if v.isupper() != up:
                        if to >> 3 == last:
                            for q in "qrbn":
                                add((s, to, q, 0))
                        else:
                            add((s, to, "", 0))
                elif to == eps:
                    add((s, to, "", 1))
        elif t == "n":
            for dd in KNIGHT_DIRS:
                to = s + dd
                if not 0 <= to < 64 or abs((to & 7) - f) > 2:
                    continue
                v = brd.get(to)
                if v is None or v.isupper() != up:
                    add((s, to, "", 0))
        elif t == "k":
            for dd in KING_DIRS:
                to = s + dd
                if not 0 <= to < 64 or abs((to & 7) - f) > 1:
                    continue
                v = brd.get(to)
                if v is None or v.isupper() != up:
                    add((s, to, "", 0))
            if up:
                if s == 4:
                    if mask & 1 and 5 not in brd and 6 not in brd:
                        add((4, 6, "", 2))
                    if mask & 2 and 1 not in brd and 2 not in brd and 3 not in brd:
                        add((4, 2, "", 2))
            elif s == 60:
                if mask & 4 and 61 not in brd and 62 not in brd:
                    add((60, 62, "", 2))
                if mask & 8 and 57 not in brd and 58 not in brd and 59 not in brd:
                    add((60, 58, "", 2))
        else:
            dirs = ROOK_DIRS if t == "r" else BISHOP_DIRS if t == "b" else ROOK_DIRS + BISHOP_DIRS
            for df, dr in dirs:
                f2, r2 = f + df, r + dr
                while 0 <= f2 <= 7 and 0 <= r2 <= 7:
                    to = r2 * 8 + f2
                    v = brd.get(to)
                    if v is not None:
                        if v.isupper() != up:
                            add((s, to, "", 0))
                        break
                    add((s, to, "", 0))
                    f2 += df
                    r2 += dr
    return out


def make(brd, m, up):
    s, to, promo, flag = m
    p = brd.pop(s)
    if flag == 1:
        cap_sq = to - 8 if up else to + 8
        return (s, to, p, brd.pop(cap_sq), cap_sq, 1)
    if flag == 2:
        if to == 6:
            rk = brd.pop(7)
            brd[5] = rk
        elif to == 2:
            rk = brd.pop(0)
            brd[3] = rk
        elif to == 62:
            rk = brd.pop(63)
            brd[61] = rk
        else:
            rk = brd.pop(56)
            brd[59] = rk
        brd[to] = p
        return (s, to, p, rk, -1, 2)
    cap = brd.pop(to, None)
    brd[to] = promo.upper() if (promo and up) else promo if promo else p
    return (s, to, p, cap, -1, 0)


# castling rights a move clears: keyed by the square the mover leaves or lands on
CLR = {4: 3, 7: 1, 0: 2, 60: 12, 63: 4, 56: 8}


def make_cr(brd, m, up, mask):
    """Apply a move and also return the castling mask after it."""
    nm = mask
    s, to = m[0], m[1]
    if s in CLR:
        nm &= ~CLR[s] & 15
    if to in CLR:
        nm &= ~CLR[to] & 15
    return make(brd, m, up), nm


def unmake(brd, u):
    s, to, p, cap, cap_sq, flag = u
    brd.pop(to, None)
    brd[s] = p
    if flag == 1:
        brd[cap_sq] = cap
    elif flag == 2:
        if to == 6:
            brd[7] = brd.pop(5)
        elif to == 2:
            brd[0] = brd.pop(3)
        elif to == 62:
            brd[63] = brd.pop(61)
        else:
            brd[56] = brd.pop(59)
    elif cap:
        brd[to] = cap


def eval_(brd, up, ks_w, ks_b):
    """Material, tables and bishop pair; from the side to move's view."""
    sc = 0
    mat = 0
    wb = bb = 0
    end = True
    for s, p in brd.items():
        lo = p.lower()
        v = V[lo]
        if lo != "k":
            mat += v
        if p.isupper():
            wb += p == "B"
            sc += v + TAB[lo][s]
        else:
            bb += p == "b"
            sc -= v + TAB[lo][s ^ 56]
    if mat < 2400:
        end = True
        sc += (KING_END[ks_b] - KING_END[ks_w ^ 56]) if False else 0
    if wb > 1:
        sc += 30
    if bb > 1:
        sc -= 30
    return sc if up else -sc


NODES = [0]
LIMIT = 14000
INF = 1 << 20


def qsearch(brd, up, mask, eps, ks_me, ks_them, alpha, beta):
    NODES[0] += 1
    if NODES[0] >= LIMIT:
        return alpha
    stand = eval_(brd, up, ks_me, ks_them)
    if stand >= beta:
        return stand
    if stand > alpha:
        alpha = stand
    caps = [m for m in gen(brd, up, mask, eps) if m[2] or m[1] in brd or m[3] == 1]
    caps.sort(key=lambda m: -(V.get((brd.get(m[1]) or "p").lower(), 0)))
    for m in caps:
        u, nm = make_cr(brd, m, up, mask)
        ksm = m[1] if brd.get(m[1], "").lower() == "k" else ks_me
        if attacked(brd, ksm, not up):
            unmake(brd, u)
            continue
        sc = -qsearch(brd, not up, nm, eps, ks_them, ksm, -beta, -alpha)
        unmake(brd, u)
        if sc >= beta:
            return sc
        if sc > alpha:
            alpha = sc
    return alpha


def search(brd, up, mask, eps, ks_me, ks_them, depth, alpha, beta, ply):
    NODES[0] += 1
    if NODES[0] >= LIMIT:
        return None
    if depth <= 0:
        return qsearch(brd, up, mask, eps, ks_me, ks_them, alpha, beta)
    moves = gen(brd, up, mask, eps)
    scored = []
    for m in moves:
        v = 0
        if m[2]:
            v += 900 + V[m[2]]
        cap = brd.get(m[1])
        if cap:
            v += V[cap.lower()] * 10 - V[brd[m[0]].lower()] // 10
        scored.append((v, m))
    scored.sort(key=lambda x: -x[0])
    best = -INF
    any_legal = False
    for _, m in scored:
        u, nm = make_cr(brd, m, up, mask)
        piece = brd.get(m[1], "")
        ksm = m[1] if piece.lower() == "k" else ks_me
        if attacked(brd, ksm, not up):
            unmake(brd, u)
            continue
        any_legal = True
        sc = search(brd, not up, nm, eps, ks_them, ksm, depth - 1, -beta, -alpha, ply + 1)
        unmake(brd, u)
        if sc is None:
            return None
        sc = -sc
        if sc > best:
            best = sc
        if sc > alpha:
            alpha = sc
            if alpha >= beta:
                break
    if not any_legal:
        return -30000 + ply if attacked(brd, ks_me, not up) else 0
    return best


def uci(m):
    s, to, promo, _ = m
    return ("abcdefgh"[s & 7] + str((s >> 3) + 1) + "abcdefgh"[to & 7]
            + str((to >> 3) + 1) + promo)


def post(path, body):
    req = urllib.request.Request(U + path, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def pick(fen, legal_uci):
    brd, side, mask, eps, hm = parse(fen)
    up = side == "w"
    ks_me = find_king(brd, up)
    ks_them = find_king(brd, not up)
    global NODES
    best = None
    NODES = [0]
    for d in range(1, 10):
        if NODES[0] >= LIMIT:
            break
        moves = gen(brd, up, mask, eps)
        scored = []
        for m in moves:
            v = 0
            if m[2]:
                v += 900 + V[m[2]]
            cap = brd.get(m[1])
            if cap:
                v += V[cap.lower()] * 10 - V[brd[m[0]].lower()] // 10
            if best is not None and m[:2] == best[:2]:
                v += 100000
            scored.append((v, m))
        scored.sort(key=lambda x: -x[0])
        alpha = -INF
        local = None
        aborted = False
        for _, m in scored:
            u, nm = make_cr(brd, m, up, mask)
            piece = brd.get(m[1], "")
            ksm = m[1] if piece.lower() == "k" else ks_me
            if attacked(brd, ksm, not up):
                unmake(brd, u)
                continue
            sc = search(brd, not up, nm, eps, ks_them, ksm, d - 1, -INF, -alpha, 1)
            unmake(brd, u)
            if sc is None:
                aborted = True
                break
            sc = -sc
            if local is None or sc > alpha:
                alpha = sc
                local = m
        if aborted:
            break
        if local is not None:
            best = local
    if best is None:
        for m in gen(brd, up, mask, eps):
            if uci(m) in legal_uci:
                best = m
                break
    return uci(best)


def inf_():
    return INF


while True:
    g = post("/game", {})
    if g["status"] == "done":
        break
    while g["status"] == "your_move":
        mv = pick(g["fen"], set(g["legal_moves"]))
        if mv not in g["legal_moves"]:
            mv = g["legal_moves"][0]
        g = post("/move", {"game": g["game"], "move": mv})
    print("game %s: %s by %s" % (g["game"], g["outcome"], g["reason"]), file=sys.stderr)
print("done: %s won, %s drawn, %s lost" % (g.get("wins"), g.get("draws"), g.get("losses")),
      file=sys.stderr)