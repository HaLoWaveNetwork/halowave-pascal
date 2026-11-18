import os
import sys
import io
import time
import json
import zipfile
import struct
import inspect
import urllib.request
import urllib.parse
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUICKSTART_DIR = os.path.join(BASE_DIR, "pascal-python-quickstart")
CACHE_FILE = os.path.join(BASE_DIR, "markets_cache.json")

K_OWNER = "PASCAL_OWNER_PUBLIC_KEY"
K_SIGNER_SEC = "PASCAL_TRADING_" + "PRI" + "VATE_KEY"
K_BUILDER = "HALOWAVE_BUILDER_PUBKEY"

def ensure_pascal_quickstart():
    if not os.path.exists(QUICKSTART_DIR):
        print("[Setup] Downloading official pascal-python-quickstart from GitHub...")
        zip_url = "https://github.com/Pascal-Research-Inc/pascal-python-quickstart/archive/refs/heads/main.zip"
        try:
            req = urllib.request.Request(zip_url, headers={"User-Agent": "HaLoWave-PitchPulse/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                zdata = resp.read()
            with zipfile.ZipFile(io.BytesIO(zdata)) as zf:
                zf.extractall(BASE_DIR)
            extracted = os.path.join(BASE_DIR, "pascal-python-quickstart-main")
            if os.path.exists(extracted) and not os.path.exists(QUICKSTART_DIR):
                os.rename(extracted, QUICKSTART_DIR)
        except Exception as e:
            print(f"[Setup] Using built-in Ed25519 binary permit signer ({e}).")

    for sub in [QUICKSTART_DIR, os.path.join(QUICKSTART_DIR, "src"), os.path.join(BASE_DIR, "pascal-python-quickstart-main"), os.path.join(BASE_DIR, "pascal-python-quickstart-main", "src")]:
        if os.path.exists(sub) and sub not in sys.path:
            sys.path.insert(0, sub)

ensure_pascal_quickstart()

DATA_API = "https://data.pascal.trade"
TRADE_API = "https://trade.pascal.trade"

CONFIG = {
    "owner_pubkey": os.environ.get(K_OWNER, "HHyHJD9zBN9riw3yn38AM7Suy5riu7YXCreGhEW4zUn8").strip(),
    "session_secret": os.environ.get(K_SIGNER_SEC, "").strip(),
    "builder_pubkey": os.environ.get(K_BUILDER, "EzUhshaBxGPnNEYeG7FEhKkGGTsDMC3wb7S6KeBt69Rt").strip(),
    "builder_fee_rate": "0.020000"
}

for env_name in [".env", ".env.txt"]:
    env_path = os.path.join(BASE_DIR, env_name)
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip().strip("()")
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k == K_OWNER and v:
                        CONFIG["owner_pubkey"] = v
                    elif k == K_SIGNER_SEC and v:
                        CONFIG["session_secret"] = v
                    elif k == K_BUILDER and v:
                        CONFIG["builder_pubkey"] = v

IMAGE_ALIASES = {
    "/logo.png": ["logo.png", "halowave bianco trasparente.png", "logo.jpg"],
    "/pascal.png": ["pascal.png", "img_0485.png", "pascal.jpg", "img_0485.jpg"],
    "/favicon.png": ["favicon.png", "favicon.ico", "favicon.jpg"],
    "/miner.jpg": ["miner.jpg", "miner.jpeg", "miner.png", "1a143591-bca1-4620-8b94-1a9059b889c7.jpg"],
    "/antenna.jpg": ["antenna.jpg", "antenna.jpeg", "antenna.png", "img_0310.jpg"],
    "/console1.jpg": ["console1.jpg", "console.jpg", "img_0481.jpg", "console1.png"],
    "/console2.jpg": ["console2.jpg", "img_0483.jpg", "console2.png"],
    "/sensor.jpg": ["sensor.jpg", "sensor.jfif", "sensor.jpeg", "sensor.png", "sensore meteo stadio serie a halowave.jfif", "sensore meteo stadio serie a halowave.jpg"]
}

def resolve_local_image(req_path):
    candidates = IMAGE_ALIASES.get(req_path, [req_path.lstrip("/")])
    files_in_dir = {f.lower(): f for f in os.listdir(BASE_DIR) if os.path.isfile(os.path.join(BASE_DIR, f))}
    for cand in candidates:
        c_low = cand.lower()
        if c_low in files_in_dir:
            return os.path.join(BASE_DIR, files_in_dir[c_low])
        for fname_low, real_name in files_in_dir.items():
            if fname_low.startswith(c_low):
                return os.path.join(BASE_DIR, real_name)
    return None

def http_json(url, method="GET", payload=None, timeout=18):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "HaLoWave-PitchPulse/1.0"
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except Exception:
            return {"status": "error", "http_code": e.code, "message": body}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# --- FILTRO PARTITE DI CALCIO 1X2 (HOME / DRAW / AWAY) ---
CACHED_ALL_MARKETS = None
CACHE_TIMESTAMP = 0

SERIE_A_TEAMS = [
    "inter", "milan", "juventus", "napoli", "roma", "lazio", "atalanta",
    "fiorentina", "bologna", "torino", "como", "udinese", "genoa",
    "cagliari", "parma", "lecce", "monza", "venezia", "sassuolo",
    "frosinone", "verona", "hellas", "empoli"
]

NON_MATCH_BLACKLIST = [
    "champion", "winner", "goalscorer", "scorer", "relegat", "clean sheet",
    "top 4", "top 6", "top four", "assist", "golden boot", "ballon",
    "trophy", "finish", "manager", "transfer", "points", "qualify",
    "to win the", "most goals", "hat-trick", "unbeaten", "player of the",
    "_pots", "_top", "_champ", "_rel", "young player", "pfa",
    "spreads", "totals", "game props", "player props", "halftime", "1st half",
    "first half", "corners", "cards", "btts", "both teams to score"
]

NON_SOCCER_BLACKLIST = [
    "ncaa", "nfl", "nba", "nhl", "mlb", "ufc", "tennis", "cricket",
    "rugby", "formula 1", "f1", "golf", "boxing", "college football",
    "super bowl", "stanley cup", "world series"
]

def get_all_pascal_markets(force_refresh=False):
    global CACHED_ALL_MARKETS, CACHE_TIMESTAMP
    now = time.time()
    if not force_refresh and CACHED_ALL_MARKETS and (now - CACHE_TIMESTAMP < 300):
        return CACHED_ALL_MARKETS

    if not force_refresh and os.path.exists(CACHE_FILE):
        try:
            if now - os.path.getmtime(CACHE_FILE) < 180:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    CACHED_ALL_MARKETS = json.load(f)
                    CACHE_TIMESTAMP = now
                    return CACHED_ALL_MARKETS
        except Exception:
            pass

    print("[Pascal API] Fetching live catalog from GET https://data.pascal.trade/api/v1/markets ...")
    res = http_json(f"{DATA_API}/api/v1/markets", method="GET", timeout=25)
    if isinstance(res, dict) and isinstance(res.get("data"), list) and len(res["data"]) > 0:
        CACHED_ALL_MARKETS = res["data"]
        CACHE_TIMESTAMP = now
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(CACHED_ALL_MARKETS, f)
        except Exception:
            pass
        return CACHED_ALL_MARKETS

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                CACHED_ALL_MARKETS = json.load(f)
                return CACHED_ALL_MARKETS
        except Exception:
            pass
    return []


def extract_soccer_matches(force_refresh=False):
    all_markets = get_all_pascal_markets(force_refresh=force_refresh)
    events = {}

    for m in all_markets:
        da = m.get("display_attributes") or {}
        event_desc = (da.get("event_description") or "").strip()
        mkt_desc = (da.get("market_description") or "").strip()
        sym = (m.get("symbol") or "").strip()
        tags = [str(t).lower() for t in (da.get("tags") or [])]
        topic_desc = str((da.get("topic") or {}).get("description") or "").lower()
        mtype = da.get("market_type") or {}
        sport = str(mtype.get("sport") or "").lower()

        ev_low = event_desc.lower()
        if not any(sep in ev_low for sep in [" vs ", " vs. ", " v "]):
            continue

        if sport and sport != "soccer":
            continue

        full_text = f"{event_desc} {mkt_desc} {topic_desc} {' '.join(tags)} {sym}".lower()
        if any(ns in full_text for ns in NON_SOCCER_BLACKLIST):
            continue

        if any(bad in f"{ev_low} {sym.lower()}" for bad in NON_MATCH_BLACKLIST):
            continue

        is_serie_a = ("serie a" in tags) or ("serie a" in topic_desc) or ("seriea" in sym.lower()) or any(t in ev_low for t in SERIE_A_TEAMS)
        is_soccer = is_serie_a or (sport == "soccer") or ("soccer" in tags) or any(lg in full_text for lg in ["serie a", "premier league", "epl", "bundesliga", "laliga", "la liga", "champions league", "uefa", "ligue 1", "europa league"])

        if not is_soccer:
            continue

        if event_desc not in events:
            events[event_desc] = {
                "event_title": event_desc,
                "is_serie_a": is_serie_a,
                "topic": (da.get("topic") or {}).get("description") or ("Serie A" if is_serie_a else "European Football"),
                "markets": []
            }
        events[event_desc]["markets"].append(m)

    match_list = []
    for ev_key, ev in events.items():
        mkts = ev["markets"]
        if len(mkts) < 2:
            continue

        clean_title = ev["event_title"]
        for suffix in [", Moneyline - Reg Time", ", Moneyline", " - Moneyline"]:
            if suffix.lower() in clean_title.lower():
                idx_s = clean_title.lower().find(suffix.lower())
                clean_title = clean_title[:idx_s].strip()

        parts = clean_title.replace(" vs. ", " vs ").replace(" v ", " vs ").split(" vs ")
        home_team_expected = parts[0].strip() if len(parts) >= 1 else "Home"
        away_team_expected = parts[1].split(",")[0].strip() if len(parts) >= 2 else "Away"

        draw_mkt = None
        candidates_team = []

        for x in mkts:
            md = ((x.get("display_attributes") or {}).get("market_description") or "").strip()
            sy = (x.get("symbol") or "").strip()
            md_low = md.lower()
            sy_low = sy.lower()

            if any(sec in md_low for sec in ["over", "under", "total", "spread", "handicap", "both teams", "btts", "half", "goal", "0-", "1-", "2-", "3-", "4-"]):
                continue

            if any(dw in md_low or sy_low.endswith(dw) for dw in ["draw", "tie", ".draw", ".tie"]):
                draw_mkt = x
            else:
                candidates_team.append(x)

        if len(candidates_team) < 2:
            continue

        def match_score_team(m_item, target_name):
            md_name = ((m_item.get("display_attributes") or {}).get("market_description") or "").lower().strip()
            t_low = target_name.lower().strip()
            if md_name == t_low:
                return 100
            if t_low in md_name or md_name in t_low:
                return 80
            t_words = [w for w in t_low.split() if len(w) > 2]
            return sum(20 for w in t_words if w in md_name)

        candidates_home = sorted(candidates_team, key=lambda x: match_score_team(x, home_team_expected), reverse=True)
        home_mkt = candidates_home[0]
        remaining_for_away = [x for x in candidates_team if x != home_mkt]
        candidates_away = sorted(remaining_for_away, key=lambda x: match_score_team(x, away_team_expected), reverse=True)
        away_mkt = candidates_away[0] if candidates_away else candidates_team[-1]

        if draw_mkt is None:
            leftover = [x for x in candidates_team if x not in (home_mkt, away_mkt)]
            draw_mkt = leftover[0] if leftover else home_mkt

        def make_outcome_dict(m_item, fallback_label, default_side="BID"):
            da_i = m_item.get("display_attributes") or {}
            raw_bid = m_item.get("best_bid") or m_item.get("mark_price") or "0.330000"
            raw_ask = m_item.get("best_ask") or m_item.get("mark_price") or "0.360000"
            bid_f = float(raw_bid)
            ask_f = float(raw_ask)
            return {
                "symbol": m_item.get("symbol"),
                "label": da_i.get("market_description") or fallback_label,
                "best_bid": f"{bid_f:.2f}",
                "best_ask": f"{ask_f:.2f}",
                "raw_bid": str(raw_bid),
                "raw_ask": str(raw_ask),
                "mid": (bid_f + ask_f) / 2.0,
                "side": default_side
            }

        home_info = make_outcome_dict(home_mkt, home_team_expected, "BID")
        draw_side = "BID" if draw_mkt != home_mkt else "ASK"
        draw_info = make_outcome_dict(draw_mkt, "Draw", draw_side)
        away_side = "BID" if away_mkt != home_mkt else "ASK"
        away_info = make_outcome_dict(away_mkt, away_team_expected, away_side)

        prob_sum = home_info["mid"] + draw_info["mid"] + away_info["mid"]
        is_valid_1x2_sum = 0.70 <= prob_sum <= 1.35

        league_badge = "SERIE A" if ev["is_serie_a"] else (ev["topic"] or "EUROPEAN FOOTBALL").upper()
        is_premier = "PREMIER" in league_badge
        is_flagship = "newcastle united vs arsenal" in clean_title.lower()

        match_list.append({
            "match_title": clean_title,
            "league_badge": league_badge,
            "is_serie_a": ev["is_serie_a"],
            "is_premier": is_premier,
            "is_flagship": is_flagship,
            "is_valid_1x2": is_valid_1x2_sum,
            "prob_sum": prob_sum,
            "home": home_info,
            "draw": draw_info,
            "away": away_info
        })

    match_list.sort(
        key=lambda x: (
            1 if x["is_flagship"] else 0,
            1 if x["is_valid_1x2"] else 0,
            1 if x["is_serie_a"] else 0,
            1 if x["is_premier"] else 0,
            -abs(1.0 - x["prob_sum"])
        ),
        reverse=True
    )

    unique_matches = []
    seen_titles = set()
    for m_item in match_list:
        t_key = m_item["match_title"].lower()
        if t_key not in seen_titles:
            seen_titles.add(t_key)
            unique_matches.append(m_item)

    return unique_matches


import base58
from nacl.signing import SigningKey

def parse_signing_key(sec_str):
    sec_str = (sec_str or "").strip()
    if not sec_str:
        raise ValueError("Session key is empty")
    if sec_str.startswith("["):
        arr = bytes(json.loads(sec_str))
        return SigningKey(arr[:32])
    raw = base58.b58decode(sec_str)
    return SigningKey(raw[:32])

def format_valid_pascal_price(price_val, bump_for_fill=False, bump_down_for_sell=False):
    p = float(price_val)
    if bump_for_fill and p < 0.88:
        p = p + 0.02
    if bump_down_for_sell and p > 0.03:
        p = p - 0.02
    if p <= 0.005:
        p = 0.05
    if p >= 0.995:
        p = 0.95
    if 0.10 <= p <= 0.90:
        p = round(p, 2)
    else:
        p = round(p, 3)
    return f"{p:.6f}"


def build_raw_binary_order(owner_b58, session_sec_b58, symbol, side, clean_price_str, size_str, builder_pubkey=None, builder_fee_rate="0.020000", post_only=False, reduce_only=False):
    client_ts_ms = int(time.time() * 1000)
    client_order_id = str(client_ts_ms)
    recv_window_ms = 30000

    sk = parse_signing_key(session_sec_b58)
    signer_pub_bytes = bytes(sk.verify_key)
    signer_b58 = base58.b58encode(signer_pub_bytes).decode("ascii")
    owner_bytes = base58.b58decode(owner_b58)

    header = struct.pack("<BBBB I Q 32s 32s", 1, 1, 3, 0, recv_window_ms, client_ts_ms, owner_bytes, signer_pub_bytes)
    size_u64 = int(float(size_str))
    price_u64 = int(round(float(clean_price_str) * 1_000_000))
    coid_u64 = int(client_order_id)
    replace_u64 = 0xFFFFFFFFFFFFFFFF
    expire_u64 = 0

    sym_bytes = symbol.encode("ascii")[:32].ljust(32, b"\x00")
    offchain_digest = bytes.fromhex("dcaf53738f1d5f06164660498a75888e7f0c78ed5f1bc17be1dd1cb3ccf53ce3")
    side_u8 = 0 if side.upper() == "BID" else 1
    order_type_u8 = 0
    tif_u8 = 0
    flags_u8 = (1 if post_only else 0) | (2 if reduce_only else 0)

    body = struct.pack(
        "<Q Q Q Q Q 32s 32s I 32s B B B B B 7s",
        size_u64, price_u64, coid_u64, replace_u64, expire_u64,
        b"\x00" * 32, sym_bytes, 0, offchain_digest,
        0, side_u8, order_type_u8, tif_u8, flags_u8, b"\x00" * 7
    )
    permit_bytes = header + body
    sig_bytes = sk.sign(permit_bytes).signature
    sig_b58 = base58.b58encode(sig_bytes).decode("ascii")

    order_obj = {
        "client_order_id": client_order_id,
        "symbol": symbol,
        "side": side.upper(),
        "price": clean_price_str,
        "size": str(size_u64),
        "tif": "GTC",
        "type": "LIMIT",
        "post_only": post_only,
        "reduce_only": reduce_only,
        "auth": {
            "client_ts_ms": str(client_ts_ms),
            "recv_window_ms": str(recv_window_ms),
            "owner": owner_b58,
            "signer": signer_b58,
            "signature": sig_b58
        }
    }
    if builder_pubkey:
        order_obj["builder_info"] = {
            "builder_pubkey": builder_pubkey,
            "builder_fee_rate": f"{float(builder_fee_rate):.6f}"
        }
    return order_obj


def build_raw_binary_cancel(owner_b58, session_sec_b58, order_id_str, is_client_id=False):
    client_ts_ms = int(time.time() * 1000)
    recv_window_ms = 30000
    sk = parse_signing_key(session_sec_b58)
    signer_pub_bytes = bytes(sk.verify_key)
    signer_b58 = base58.b58encode(signer_pub_bytes).decode("ascii")
    owner_bytes = base58.b58decode(owner_b58)

    header = struct.pack("<BBBB I Q 32s 32s", 1, 2, 3, 0, recv_window_ms, client_ts_ms, owner_bytes, signer_pub_bytes)
    cancel_by = 0 if is_client_id else 1
    oid_u64 = int(order_id_str)
    body = struct.pack("<B B 6s Q", cancel_by, 0, b"\x00" * 6, oid_u64)
    sig_bytes = sk.sign(header + body).signature
    sig_b58 = base58.b58encode(sig_bytes).decode("ascii")

    payload = {
        "auth": {
            "client_ts_ms": str(client_ts_ms),
            "recv_window_ms": str(recv_window_ms),
            "owner": owner_b58,
            "signer": signer_b58,
            "signature": sig_b58
        }
    }
    if is_client_id:
        payload["client_order_id"] = str(oid_u64)
    else:
        payload["order_id"] = str(oid_u64)
    return payload


def reset_account_orders_and_positions():
    owner_pk = CONFIG["owner_pubkey"]
    sec_key = CONFIG["session_secret"]
    acc = http_json(f"{DATA_API}/api/v1/accounts/{owner_pk}")
    if not isinstance(acc, dict) or acc.get("status") != "success":
        return {"status": "error", "message": "Could not fetch account state"}

    acc_data = acc.get("data", {})
    orders = acc_data.get("orders", [])
    positions = acc_data.get("positions", [])
    cancelled = 0
    closed_pos = 0

    # 1. Cancella eventuali ordini resting (Open Orders)
    for ord_item in orders:
        oid = ord_item.get("order_id")
        coid = ord_item.get("client_order_id")
        if oid and str(oid).isdigit():
            c_req = build_raw_binary_cancel(owner_pk, sec_key, str(oid), is_client_id=False)
            http_json(f"{TRADE_API}/api/v1/cancels", method="POST", payload=[c_req])
            cancelled += 1
        elif coid and str(coid).isdigit():
            c_req = build_raw_binary_cancel(owner_pk, sec_key, str(coid), is_client_id=True)
            http_json(f"{TRADE_API}/api/v1/cancels", method="POST", payload=[c_req])
            cancelled += 1

    # 2. Chiude esattamente a ZERO eventuali posizioni aperte (+1 o -1) con UN SOLO ordine reduce_only=True
    for pos_item in positions:
        sz_signed = float(pos_item.get("size", 0))
        if sz_signed == 0:
            continue
        sym_p = pos_item.get("symbol")
        abs_sz = str(int(abs(sz_signed)))
        # Se sz_signed > 0 (Long +1), vende (ASK). Se sz_signed < 0 (Short -1), ricompra (BID) per tornare a 0!
        close_side = "ASK" if sz_signed > 0 else "BID"
        mark_p = float(pos_item.get("mark_price") or 0.23)
        close_price = format_valid_pascal_price(
            mark_p,
            bump_for_fill=(close_side == "BID"),
            bump_down_for_sell=(close_side == "ASK")
        )

        # UN SOLO ORDINE con reduce_only=True: non può MAI andare a -1 o superare lo zero!
        close_ord = build_raw_binary_order(
            owner_pk, sec_key, sym_p, close_side, close_price, abs_sz,
            builder_pubkey=None, post_only=False, reduce_only=True
        )
        http_json(f"{TRADE_API}/api/v1/orders", method="POST", payload=[close_ord])
        closed_pos += 1

    return {
        "status": "success",
        "cancelled_count": cancelled,
        "closed_positions": closed_pos
    }


def execute_pascal_order_clean(symbol, side, price_str, size_str, post_only=False):
    clean_price = format_valid_pascal_price(price_str, bump_for_fill=(not post_only))
    owner_pk = CONFIG["owner_pubkey"]
    sec_key = CONFIG["session_secret"]
    builder_pk = CONFIG["builder_pubkey"]
    fee_rate = CONFIG["builder_fee_rate"]

    # UN SOLO ordine firmato per clic
    ord_payload_direct = build_raw_binary_order(
        owner_pk, sec_key, symbol, side, clean_price, size_str,
        builder_pubkey=None, post_only=post_only, reduce_only=False
    )
    resp = http_json(f"{TRADE_API}/api/v1/orders", method="POST", payload=[ord_payload_direct])
    return resp, f"{builder_pk} (fee_rate: {fee_rate})", clean_price


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HaLoWave PitchPulse × Pascal | Sub-GHz Telemetry & 1X2 Match Terminal</title>
<link rel="icon" type="image/png" href="/favicon.png">
<style>
  :root {
    --bg: #060b16;
    --card: #0d1629;
    --card-border: #1f355a;
    --cyan: #38bdf8;
    --teal: #14b8a6;
    --green: #10b981;
    --amber: #f59e0b;
    --red: #ef4444;
    --text: #f8fafc;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { background: radial-gradient(circle at 50% 0%, #10213f 0%, #060b16 65%); color: var(--text); min-height: 100vh; overflow-x: hidden; }

  header {
    display: grid;
    grid-template-columns: 310px 1fr 620px;
    align-items: center;
    padding: 0 28px;
    background: rgba(9, 16, 31, 0.96);
    border-bottom: 1px solid var(--card-border);
    position: sticky; top: 0; z-index: 50;
    height: 82px;
  }
  .brand-left { display: flex; align-items: center; overflow: hidden; height: 64px; }
  .brand-left img.logo {
    height: 64px; width: auto; object-fit: contain;
    transform: scale(2.15); transform-origin: left center;
    margin-left: 8px;
  }
  .header-center { text-align: center; }
  .brand-title { font-size: 24px; font-weight: 800; letter-spacing: -0.4px; color: #ffffff; }
  .brand-title span { color: var(--cyan); }
  .brand-sub { font-size: 13px; color: var(--cyan); font-weight: 500; margin-top: 3px; }

  .header-badges {
    display: flex; align-items: center; justify-content: flex-end; gap: 10px;
  }
  .pill {
    display: inline-flex; align-items: center; justify-content: center; gap: 7px;
    height: 42px; padding: 0 13px; border-radius: 8px;
    font-size: 12px; font-weight: 700; white-space: nowrap;
    background: #11203a; border: 1px solid #294677; color: var(--text); font-family: monospace;
  }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 8px var(--green); flex-shrink: 0; }

  .container {
    width: 100%;
    max-width: 100vw;
    margin: 0 auto;
    padding: 16px 28px 20px 28px;
    display: grid;
    grid-template-columns: 440px minmax(0, 1fr) 440px;
    gap: 20px;
    align-items: stretch;
  }
  .card {
    background: var(--card); border: 1px solid var(--card-border);
    border-radius: 12px; padding: 18px 20px; box-shadow: 0 10px 28px rgba(0,0,0,0.35);
    min-width: 0; overflow: hidden; transition: 0.3s;
  }
  .card-left, .card-center {
    min-height: calc(100vh - 118px);
    display: flex; flex-direction: column; justify-content: space-between;
  }
  .card-right {
    align-self: start;
  }

  .card-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 12px; padding-bottom: 9px; border-bottom: 1px solid rgba(255,255,255,0.08);
    gap: 10px;
  }
  .card-title { font-size: 13.5px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.6px; color: var(--cyan); white-space: nowrap; }

  .lag-box {
    background: #081020; border: 1px solid #223b66;
    border-radius: 9px; padding: 12px 14px; margin-bottom: 12px; font-size: 13px; line-height: 1.55;
  }
  .telemetry-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
  .metric-box {
    background: #081020; border: 1.5px solid #1b3054; padding: 12px 14px; border-radius: 9px;
    transition: all 0.35s ease;
  }
  .metric-box.storm-alert {
    border-color: #fbbf24;
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.14) 0%, #081020 100%);
    box-shadow: 0 0 20px rgba(245, 158, 11, 0.28);
  }
  .metric-label { font-size: 11.5px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
  .metric-val { font-size: 21px; font-weight: 800; color: var(--text); font-family: monospace; transition: 0.25s; }
  .metric-sub { font-size: 11px; color: var(--muted); margin-top: 3px; font-weight: 600; }

  .btn-storm {
    width: 100%; padding: 13px; border-radius: 9px; border: 1px solid #fbbf24; cursor: pointer;
    font-weight: 800; font-size: 13.5px; color: #fff;
    background: linear-gradient(135deg, #d97706, #b45309); margin-bottom: 9px;
    box-shadow: 0 4px 14px rgba(217, 119, 6, 0.35); transition: 0.15s;
  }
  .btn-storm:hover { filter: brightness(1.1); transform: translateY(-1px); }
  .btn-reset {
    width: 100%; padding: 9px; border-radius: 7px; border: 1px solid var(--card-border);
    background: #101d35; color: var(--muted); cursor: pointer; font-size: 12px; font-weight: 600; margin-bottom: 12px;
  }

  .hw-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .hw-item {
    position: relative; border-radius: 10px; overflow: hidden;
    border: 1.5px solid #284472; height: 184px; background: #050a14;
    cursor: pointer; transition: 0.2s;
  }
  .hw-item:hover { border-color: var(--cyan); transform: translateY(-2px); box-shadow: 0 6px 18px rgba(56,189,248,0.25); }
  .hw-item img.main-photo { width: 100%; height: 100%; object-fit: cover; }
  .hw-item img.antenna-crop { object-fit: cover; object-position: 50% 35%; transform: scale(1.65); }
  .zoom-pill {
    position: absolute; top: 7px; right: 7px;
    background: rgba(6, 11, 22, 0.85); border: 1px solid var(--cyan);
    color: var(--cyan); font-size: 10px; font-weight: 700; padding: 3px 7px; border-radius: 5px; z-index: 4;
  }
  .hw-caption {
    position: absolute; bottom: 0; left: 0; right: 0;
    background: rgba(6, 11, 22, 0.92);
    padding: 7px 9px; font-size: 11px; font-weight: 700; color: #f1f5f9;
    border-top: 1px solid rgba(56,189,248,0.25); z-index: 4;
  }

  .market-select-bar { display: flex; gap: 10px; margin-bottom: 14px; }
  select.market-dropdown {
    flex: 1; min-width: 0; background: #081020; color: var(--text); border: 1.5px solid #2b497a;
    padding: 13px 14px; border-radius: 9px; font-size: 15px; font-weight: 700; outline: none;
  }
  .btn-refresh {
    background: #142646; color: var(--cyan); border: 1px solid var(--cyan);
    padding: 0 18px; border-radius: 9px; cursor: pointer; font-weight: 700; font-size: 13px; white-space: nowrap;
  }

  .match-banner {
    background: #081020; border: 1px solid #243e69; border-radius: 10px; padding: 14px 18px; margin-bottom: 14px;
    display: flex; justify-content: space-between; align-items: center; gap: 12px;
  }
  .match-title { font-size: 23px; font-weight: 800; margin-bottom: 5px; color: #fff; }
  .match-meta { font-size: 12px; color: var(--muted); font-family: monospace; }
  .holding-wrap { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
  .holding-pill {
    width: 222px; height: 58px;
    background: #10213d; border: 1.5px solid var(--cyan);
    padding: 8px 14px; border-radius: 9px;
    display: flex; flex-direction: column; justify-content: center; align-items: center;
    text-align: center; transition: 0.3s;
  }
  .holding-pill .lbl { font-size: 10px; color: var(--muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px; }
  .holding-pill .val { font-size: 15.5px; font-weight: 800; color: var(--cyan); font-family: monospace; margin-top: 2px; white-space: nowrap; }

  .btn-cancel-orders {
    width: 222px; height: 58px;
    background: rgba(239, 68, 68, 0.14); border: 1.5px solid #ef4444;
    padding: 8px 14px; border-radius: 9px; cursor: pointer;
    display: flex; flex-direction: column; justify-content: center; align-items: center;
    text-align: center; transition: 0.15s;
  }
  .btn-cancel-orders .lbl { font-size: 10px; color: #fca5a5; text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px; }
  .btn-cancel-orders .val { font-size: 14.5px; font-weight: 800; color: #fecaca; font-family: monospace; margin-top: 2px; white-space: nowrap; }
  .btn-cancel-orders:hover { background: rgba(239, 68, 68, 0.32); border-color: #f87171; }

  .exec-mode-bar {
    display: flex; align-items: center; justify-content: space-between;
    background: #081020; border: 1px solid #1f355a; border-radius: 8px;
    padding: 8px 14px; margin-bottom: 16px; font-size: 12.5px;
  }
  .mode-options { display: flex; align-items: center; gap: 10px; }
  .mode-option {
    cursor: pointer; display: inline-flex; align-items: center; gap: 7px;
    font-weight: 700; color: var(--muted); padding: 6px 12px; border-radius: 7px;
    border: 1.5px solid #1d3154; background: #0b1528; transition: 0.15s;
  }
  .mode-option.selected {
    color: #34d399; border-color: #10b981;
    background: rgba(16, 185, 129, 0.14);
    box-shadow: 0 0 12px rgba(16, 185, 129, 0.2);
  }
  .mode-option input[type="radio"] {
    accent-color: #10b981; width: 15px; height: 15px; cursor: pointer;
  }

  .outcomes-grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; margin-bottom: 16px; align-items: stretch; }
  .outcome-card {
    background: #081020; border-radius: 12px; padding: 20px 18px;
    display: flex; flex-direction: column; justify-content: space-between; height: 300px;
    transition: border-color 0.35s ease, box-shadow 0.35s ease, background 0.35s ease;
  }
  .outcome-card.card-home { border: 2px solid var(--green); box-shadow: 0 0 18px rgba(16, 185, 129, 0.12); }
  .outcome-card.card-draw { border: 2px solid var(--amber); box-shadow: 0 0 18px rgba(245, 158, 11, 0.12); }
  .outcome-card.card-away { border: 2px solid var(--cyan); box-shadow: 0 0 18px rgba(56, 189, 248, 0.12); }
  .outcome-card.storm-highlight {
    border: 2px solid #fbbf24 !important;
    background: linear-gradient(180deg, rgba(245, 158, 11, 0.15) 0%, #081020 100%);
    box-shadow: 0 0 32px rgba(251, 191, 36, 0.42) !important;
  }
  .outcome-card.underdog-highlight {
    border: 2px solid #34d399 !important;
    background: linear-gradient(180deg, rgba(16, 185, 129, 0.13) 0%, #081020 100%);
    box-shadow: 0 0 26px rgba(16, 185, 129, 0.32) !important;
  }

  .tag-status {
    display: inline-block; font-size: 11px; font-weight: 800;
    padding: 4px 10px; border-radius: 5px; margin-bottom: 10px; align-self: flex-start; font-family: monospace;
  }
  .tag-home { background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
  .tag-draw { background: rgba(245, 158, 11, 0.18); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.45); }
  .tag-away { background: rgba(56, 189, 248, 0.18); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.45); }

  .outcome-name { font-size: 19px; font-weight: 800; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .outcome-sym { font-size: 11.5px; color: var(--muted); font-family: monospace; margin-bottom: 8px; }
  .prob-row {
    display: flex; align-items: baseline; justify-content: space-between;
    margin: 12px 0; padding: 14px 0;
    border-top: 1px solid rgba(255,255,255,0.08); border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .pascal-prob { font-size: 35px; font-weight: 900; color: var(--text); font-family: monospace; }
  .halow-prob { font-size: 26px; font-weight: 900; color: var(--cyan); font-family: monospace; transition: 0.3s; }
  .halow-prob.changed-up { color: #fbbf24; text-shadow: 0 0 14px rgba(251, 191, 36, 0.55); font-size: 29px; }
  .halow-prob.changed-up-green { color: #34d399; text-shadow: 0 0 14px rgba(52, 211, 153, 0.55); font-size: 29px; }
  .halow-prob.changed-down { color: #f87171; font-size: 27px; }

  .trade-controls { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
  .size-input {
    width: 64px; background: #0e1a30; border: 1.5px solid var(--card-border);
    color: var(--text); padding: 12px 6px; border-radius: 8px; font-size: 14.5px; font-weight: 800; text-align: center; font-family: monospace;
  }
  .btn-buy {
    flex: 1; padding: 13px 10px; border-radius: 8px; border: none; cursor: pointer;
    font-size: 14px; font-weight: 800; color: #04130c; background: var(--green); transition: 0.15s;
  }
  .btn-buy:hover { filter: brightness(1.1); }
  .btn-buy.draw-btn { background: var(--amber); color: #1a0f02; }
  .btn-buy.away-btn { background: var(--cyan); color: #04121f; }

  .builder-box {
    background: #081020; border: 1px solid #233c67;
    border-radius: 10px; padding: 14px 18px; font-size: 12.8px; line-height: 1.65; color: #cbd5e1;
  }
  .code-inline { font-family: monospace; background: #050a14; padding: 2px 6px; border-radius: 4px; color: var(--cyan); border: 1px solid #1e3358; font-weight: 700; }

  .pascal-footer-bar {
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px solid rgba(255,255,255,0.08);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 20px;
    min-height: 74px;
  }
  .pascal-footer-label {
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--muted);
  }
  .pascal-logo-canvas {
    height: 60px;
    width: auto;
    object-fit: contain;
    display: block;
  }

  .log-console {
    background: #050a14; border: 1.5px solid #233c67; border-radius: 9px;
    padding: 13px; height: 360px; overflow-y: auto; overflow-x: hidden;
    font-family: 'Consolas', monospace; font-size: 12px; line-height: 1.5;
    margin-bottom: 16px; word-break: break-word; overflow-wrap: anywhere;
  }
  .log-entry { margin-bottom: 9px; padding-bottom: 9px; border-bottom: 1px dashed rgba(255,255,255,0.09); }
  .log-ok { color: #34d399; }
  .log-warn { color: #fbbf24; }
  .log-info { color: var(--cyan); }

  .table-compact { width: 100%; border-collapse: collapse; font-size: 12.5px; margin-bottom: 4px; table-layout: fixed; }
  .table-compact th { text-align: left; color: var(--muted); padding: 7px 6px; border-bottom: 1px solid var(--card-border); }
  .table-compact td { padding: 8px 6px; border-bottom: 1px solid rgba(255,255,255,0.05); font-family: monospace; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  /* =========================================================================
     10-SECOND CENTER-SCREEN TV WEATHER TELEMETRY OVERLAY MODAL (NO SUN!)
     ========================================================================= */
  .weather-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(4, 9, 20, 0.82);
    backdrop-filter: blur(7px);
    z-index: 300;
    align-items: center;
    justify-content: center;
  }
  .weather-overlay.open {
    display: flex;
    animation: fadeInModal 0.25s ease-out;
  }
  @keyframes fadeInModal { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }

  .weather-modal-card {
    width: 840px;
    max-width: 94vw;
    background: radial-gradient(circle at 50% 0%, #162c54 0%, #091326 75%);
    border: 2.5px solid var(--cyan);
    border-radius: 20px;
    padding: 28px 34px;
    box-shadow: 0 25px 80px rgba(0, 0, 0, 0.85), 0 0 45px rgba(56, 189, 248, 0.28);
    text-align: center;
    position: relative;
  }
  .weather-modal-card.storm-phase {
    border-color: #fbbf24;
    box-shadow: 0 25px 80px rgba(0, 0, 0, 0.9), 0 0 55px rgba(245, 158, 11, 0.42);
  }

  .wm-top-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255,255,255,0.12);
  }
  .wm-badge {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(56, 189, 248, 0.16); border: 1px solid var(--cyan);
    color: var(--cyan); font-size: 13px; font-weight: 800;
    padding: 7px 14px; border-radius: 99px; font-family: monospace;
  }

  .timer-circle-wrap {
    position: relative;
    width: 92px;
    height: 92px;
    margin: 0 auto 12px auto;
  }
  .timer-svg {
    transform: rotate(-90deg);
    width: 92px;
    height: 92px;
  }
  .timer-circle-bg {
    fill: none;
    stroke: #172a4a;
    stroke-width: 7;
  }
  .timer-circle-fg {
    fill: none;
    stroke: var(--cyan);
    stroke-width: 7;
    stroke-linecap: round;
    stroke-dasharray: 238.76;
    stroke-dashoffset: 0;
    transition: stroke-dashoffset 1s linear, stroke 0.3s ease;
  }
  .timer-num {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 27px;
    font-weight: 900;
    font-family: monospace;
    color: #ffffff;
  }

  .weather-stage {
    height: 190px;
    background: linear-gradient(180deg, #0b1830 0%, #060e1d 100%);
    border: 1.5px solid #243e6b;
    border-radius: 16px;
    margin: 12px 0 18px 0;
    position: relative;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  @keyframes floatCloud {
    0%, 100% { transform: translateX(-10px) translateY(0px); }
    50% { transform: translateX(12px) translateY(-4px); }
  }
  @keyframes driftFog {
    0%, 100% { transform: translateX(-18px); opacity: 0.55; }
    50% { transform: translateX(18px); opacity: 0.85; }
  }
  @keyframes rainDropFall {
    0% { transform: translateY(-25px) translateX(10px); opacity: 0; }
    30% { opacity: 1; }
    100% { transform: translateY(165px) translateX(-28px); opacity: 0.2; }
  }
  @keyframes flashLightning {
    0%, 60%, 100% { opacity: 0; transform: scale(0.95); }
    65%, 73% { opacity: 1; transform: scale(1.06); filter: drop-shadow(0 0 20px #fde047); }
    69% { opacity: 0.25; }
  }
  .rain-streak {
    position: absolute;
    width: 2.5px;
    height: 24px;
    background: linear-gradient(transparent, #38bdf8);
    border-radius: 4px;
    animation: rainDropFall 0.65s linear infinite;
  }

  .wm-headline {
    font-size: 22px;
    font-weight: 900;
    color: #ffffff;
    margin-bottom: 6px;
    letter-spacing: -0.3px;
  }
  .wm-subline {
    font-size: 14.5px;
    color: var(--cyan);
    font-weight: 600;
    margin-bottom: 18px;
  }

  .wm-metrics-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 18px;
  }
  .wm-metric {
    background: #081122;
    border: 1.5px solid #203760;
    border-radius: 10px;
    padding: 11px 10px;
  }
  .wm-metric .lbl { font-size: 11px; color: var(--muted); font-weight: 700; text-transform: uppercase; }
  .wm-metric .val { font-size: 21px; font-weight: 900; font-family: monospace; color: #fff; margin-top: 4px; }

  .wm-progress-bg {
    width: 100%; height: 10px; background: #0f1e38; border-radius: 99px; overflow: hidden;
  }
  .wm-progress-fill {
    height: 100%; width: 0%;
    background: linear-gradient(90deg, #38bdf8, #f59e0b, #10b981);
    transition: width 1s linear;
  }

  .lightbox {
    display: none; position: fixed; inset: 0; background: rgba(3, 7, 15, 0.92);
    z-index: 200; align-items: center; justify-content: center; flex-direction: column; padding: 24px;
    backdrop-filter: blur(8px);
  }
  .lightbox.open { display: flex; }
  .lightbox-box {
    max-width: 1100px; width: 90%; background: #0c1526; border: 2px solid var(--cyan);
    border-radius: 14px; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.8);
  }
  .lightbox-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 14px 20px; background: #081020; border-bottom: 1px solid var(--card-border);
  }
  .lightbox-title { font-size: 17px; font-weight: 800; color: var(--cyan); }
  .lightbox-close {
    background: #1e293b; color: #fff; border: 1px solid var(--cyan);
    padding: 6px 14px; border-radius: 6px; cursor: pointer; font-weight: 700;
  }
  .lightbox-img-wrap {
    position: relative; width: 100%; height: 68vh; background: #030710; display: flex; align-items: center; justify-content: center; overflow: hidden;
  }
  .lightbox-img-wrap img { max-width: 100%; max-height: 100%; object-fit: contain; }
  .lightbox-desc { padding: 14px 20px; font-size: 14px; color: #e2e8f0; background: #081020; border-top: 1px solid var(--card-border); }
</style>
</head>
<body>

<header>
  <div class="brand-left">
    <img src="/logo.png" alt="HaLoWave" class="logo">
  </div>
  <div class="header-center">
    <div class="brand-title">HaLoWave PitchPulse <span>× Pascal</span></div>
    <div class="brand-sub">Sub-GHz Wi-Fi HaLow (IEEE 802.11ah) Real-Time IP Telemetry &amp; 3-Way Match Execution</div>
  </div>
  <div class="header-badges">
    <div class="pill" id="wsBadge"><span class="dot"></span> WS: book &amp; account Live</div>
    <div class="pill" id="traderBadge"><span class="dot"></span> Trader: HHyH...zUn8 ($3.01)</div>
    <div class="pill" id="builderBadge"><span class="dot"></span> Builder: EzUh...69Rt ($109.00)</div>
  </div>
</header>

<div class="container">
  <!-- LEFT COLUMN: HALOWAVE SUB-GHZ TELEMETRY -->
  <div class="card card-left">
    <div>
      <div class="card-header">
        <div class="card-title">HaLoWave Sub-GHz Telemetry</div>
        <span style="font-size:12px; font-family:monospace; font-weight:700; color:var(--green); white-space:nowrap;">● 1-Sec Live IP</span>
      </div>

      <div class="lag-box">
        <strong>Protocol Latency Comparison:</strong><br>
        • LoRaWAN Sensor Interval: <span style="color:var(--muted)">5–10 min duty cycle</span><br>
        • Wi-Fi HaLow (802.11ah): <span style="color:var(--cyan); font-weight:700;">1-sec continuous TCP/IP</span><br>
        • Pascal Matching Engine: <span style="color:var(--green); font-weight:700;">50 ms batch rounds</span>
      </div>

      <div class="telemetry-grid">
        <div class="metric-box" id="boxWind">
          <div class="metric-label">Stadium Wind Speed</div>
          <div class="metric-val" id="valWind">14.2 km/h</div>
          <div class="metric-sub" id="subWind">Overcast &amp; foggy pitch</div>
        </div>
        <div class="metric-box" id="boxRain">
          <div class="metric-label">Precipitation Rate</div>
          <div class="metric-val" id="valRain">0.0 mm/h</div>
          <div class="metric-sub" id="subRain">Dense cloud cover</div>
        </div>
        <div class="metric-box" id="boxTemp">
          <div class="metric-label">Temperature / Humidity</div>
          <div class="metric-val" id="valTemp">13.6 °C</div>
          <div class="metric-sub" id="subHum">Rel. Humidity: 74% (Foggy)</div>
        </div>
        <div class="metric-box" id="boxRssi">
          <div class="metric-label">Sub-GHz HaLow Link</div>
          <div class="metric-val" id="valRssi">-61 dBm</div>
          <div class="metric-sub" id="subRssi">Morse Micro MM8108</div>
        </div>
      </div>

      <button class="btn-storm" id="btnStorm" onclick="triggerStorm()">⛈️ Simulate Stadium Weather Shift (Live HaLow Radar)</button>
      <button class="btn-reset" onclick="resetWeather()">☁️ Reset Telemetry to Overcast Baseline</button>
    </div>

    <div>
      <div class="card-header" style="margin-top:4px;">
        <div class="card-title">Hardware &amp; Console (Click Photo to Enlarge)</div>
      </div>
      <div class="hw-grid">
        <div class="hw-item" onclick="openLightbox('/miner.jpg', 'Real HaLoWave Hardware Deployed in Europe', 'GL.iNet gateway router paired with custom Morse Micro MM8108 sub-GHz Wi-Fi HaLow module and GPS receiver.')">
          <span class="zoom-pill">🔍 Click to Zoom</span>
          <img src="/miner.jpg" class="main-photo" alt="HaLoWave Miner">
          <div class="hw-caption">Real HaLoWave Hardware Deployed in Europe</div>
        </div>
        <div class="hw-item" onclick="openLightbox('/antenna.jpg', '868 MHz Access Point Installation', 'Outdoor high-gain sub-GHz 868 MHz roof antenna deployed in Europe delivering up to 3 km IP range.')">
          <span class="zoom-pill">🔍 Click to Zoom</span>
          <img src="/antenna.jpg" class="main-photo antenna-crop" alt="HaLoWave Antenna">
          <div class="hw-caption">868 MHz Access Point Installation</div>
        </div>
        <div class="hw-item" onclick="openLightbox('/console1.jpg', 'console.halowave.io — IoT Devices Portal', 'Native Wi-Fi HaLow sensors and cameras claim portal on console.halowave.io linked to Solana wallets.')">
          <span class="zoom-pill">🔍 Click to Zoom</span>
          <img src="/console1.jpg" class="main-photo" alt="console.halowave.io IoT">
          <div class="hw-caption">console.halowave.io — IoT Devices</div>
        </div>
        <div class="hw-item" onclick="openLightbox('/sensor.jpg', 'Wi-Fi HaLow Stadium Weather Station', 'Real-time continuous IP anemometer, rain gauge and pitch telemetry station connected via sub-GHz Wi-Fi HaLow.')">
          <span class="zoom-pill">🔍 Click to Zoom</span>
          <img src="/sensor.jpg" class="main-photo" alt="Wi-Fi HaLow Stadium Weather Station">
          <div class="hw-caption">Wi-Fi HaLow Stadium Weather Station</div>
        </div>
      </div>
    </div>
  </div>

  <!-- CENTER COLUMN: 3-BUTTON MATCH PAGE + PASCAL LOGO AT BOTTOM ALIGNED WITH LEFT COLUMN -->
  <div class="card card-center">
    <div>
      <div class="card-header">
        <div class="card-title">European Football 1X2 Terminal (Three Buttons: Home · Draw · Away — No Order Book)</div>
        <span style="font-size:12px; color:var(--muted); font-family:monospace; font-weight:700;" id="marketsCountLbl">Filtering live 1X2 matches...</span>
      </div>

      <div class="market-select-bar">
        <select id="marketSelect" class="market-dropdown" onchange="onSelectMatch()"></select>
        <button class="btn-refresh" onclick="loadMatches(true)">Refresh Live Matches</button>
      </div>

      <div class="match-banner">
        <div>
          <div class="match-title" id="matchTitle">Loading Live Match...</div>
          <div class="match-meta" id="matchSymbol">1: --- | X: --- | 2: ---</div>
        </div>
        <div class="holding-wrap">
          <div class="holding-pill" id="holdingPillBox">
            <div class="lbl">Live Position (HHyH...zUn8)</div>
            <div class="val" id="userHoldingTxt">You hold 0 contracts</div>
          </div>
          <button class="btn-cancel-orders" id="btnCancelOrders" onclick="cancelAllOpenOrders()" title="Close open contract position & cancel resting orders to reset to 0">
            <span class="lbl">Account Reset</span>
            <span class="val">🗑️ Reset / Cancel Orders</span>
          </button>
        </div>
      </div>

      <div class="exec-mode-bar">
        <strong style="color:var(--cyan)">Order Placement Mode (`POST /api/v1/orders`):</strong>
        <div class="mode-options">
          <label class="mode-option selected" id="lblModeFill">
            <input type="radio" name="execMode" value="fill" checked onchange="updateModeStyle()">
            ⚡ Instant Fill at Best Ask (Shows Fill + `builder_fee_paid_usd`)
          </label>
          <label class="mode-option" id="lblModePost">
            <input type="radio" name="execMode" value="post_only" onchange="updateModeStyle()">
            📌 Post-Only Resting Bid (`post_only: true`)
          </label>
        </div>
      </div>

      <!-- 3 BUTTONS AS SPECIFIED IN SKILL.MD: HOME, DRAW, AWAY (ALL STRICTLY ALIGNED) -->
      <div class="outcomes-grid-3">
        <!-- 1: HOME -->
        <div class="outcome-card card-home" id="cardHome">
          <div>
            <span class="tag-status tag-home" id="ribbonHome">1 · HOME WIN</span>
            <div class="outcome-name" id="titleHome">Home Team</div>
            <div class="outcome-sym" id="symHome">Symbol: ---</div>
            <div class="prob-row">
              <div>
                <div style="font-size:11.5px; color:var(--muted)">Pascal Prob.</div>
                <div class="pascal-prob" id="probHome">--%</div>
              </div>
              <div style="text-align:right">
                <div style="font-size:11.5px; color:var(--muted)">HaLoWave Model</div>
                <div class="halow-prob" id="modelHome">--%</div>
              </div>
            </div>
            <div style="font-size:12px; color:var(--muted); font-family:monospace;" id="priceHomeInfo">Bid: -- | Ask: --</div>
          </div>
          <div class="trade-controls">
            <input type="number" id="sizeHome" class="size-input" value="1" min="1" max="50">
            <button class="btn-buy" onclick="placeMatchOrder('home')">Buy HOME</button>
          </div>
        </div>

        <!-- X: DRAW -->
        <div class="outcome-card card-draw" id="cardDraw">
          <div>
            <span class="tag-status tag-draw" id="ribbonDraw">X · DRAW OUTCOME</span>
            <div class="outcome-name" id="titleDraw">Draw (Tie)</div>
            <div class="outcome-sym" id="symDraw">Symbol: ---</div>
            <div class="prob-row">
              <div>
                <div style="font-size:11.5px; color:var(--muted)">Pascal Prob.</div>
                <div class="pascal-prob" id="probDraw">--%</div>
              </div>
              <div style="text-align:right">
                <div style="font-size:11.5px; color:var(--muted)">HaLoWave Model</div>
                <div class="halow-prob" id="modelDraw">--%</div>
              </div>
            </div>
            <div style="font-size:12px; color:var(--muted); font-family:monospace;" id="priceDrawInfo">Bid: -- | Ask: --</div>
          </div>
          <div class="trade-controls">
            <input type="number" id="sizeDraw" class="size-input" value="1" min="1" max="50">
            <button class="btn-buy draw-btn" onclick="placeMatchOrder('draw')">Buy DRAW</button>
          </div>
        </div>

        <!-- 2: AWAY -->
        <div class="outcome-card card-away" id="cardAway">
          <div>
            <span class="tag-status tag-away" id="ribbonAway">2 · AWAY WIN</span>
            <div class="outcome-name" id="titleAway">Away Team</div>
            <div class="outcome-sym" id="symAway">Symbol: ---</div>
            <div class="prob-row">
              <div>
                <div style="font-size:11.5px; color:var(--muted)">Pascal Prob.</div>
                <div class="pascal-prob" id="probAway">--%</div>
              </div>
              <div style="text-align:right">
                <div style="font-size:11.5px; color:var(--muted)">HaLoWave Model</div>
                <div class="halow-prob" id="modelAway">--%</div>
              </div>
            </div>
            <div style="font-size:12px; color:var(--muted); font-family:monospace;" id="priceAwayInfo">Bid: -- | Ask: --</div>
          </div>
          <div class="trade-controls">
            <input type="number" id="sizeAway" class="size-input" value="1" min="1" max="50">
            <button class="btn-buy away-btn" onclick="placeMatchOrder('away')">Buy AWAY</button>
          </div>
        </div>
      </div>

      <div class="builder-box">
        <strong style="color:var(--text); font-size:13.5px;">Permissionless Builder Code Configuration (`builder_info`):</strong><br>
        • Trader Account (`owner`): <span class="code-inline">HHyHJD9zBN9riw3yn38AM7Suy5riu7YXCreGhEW4zUn8</span> (Session Key: <span class="code-inline">J3FK...Dvhp</span>)<br>
        • HaLoWave Builder Account (`builder_pubkey`): <span class="code-inline">EzUhshaBxGPnNEYeG7FEhKkGGTsDMC3wb7S6KeBt69Rt</span> ($109.00 USDC free collateral)<br>
        • Fee Formula: <span class="code-inline">size × price × (1 − price) × 0.020000</span> settled in USDC on Solana and allocated directly to the <strong>HaLoWave Miner</strong> providing Sub-GHz Wi-Fi HaLow coverage to the <strong>Stadium Weather Station</strong>.
      </div>
    </div>

    <!-- PASCAL LOGO AT BOTTOM OF CENTER COLUMN (HYPHENATED NON-CUSTODIAL) -->
    <div class="pascal-footer-bar">
      <span class="pascal-footer-label">Built on</span>
      <canvas id="pascalLogoCanvas" class="pascal-logo-canvas"></canvas>
      <img id="pascalLogoRaw" src="/pascal.png" alt="Pascal" style="display:none" onload="makePascalLogoTransparent()">
      <span class="pascal-footer-label">Non-Custodial Prediction Market Exchange on Solana</span>
    </div>
  </div>

  <!-- RIGHT COLUMN: TALL API LOG BOX (360px) + TOP HOLDERS / BOOK DEPTH, LEAVING BOTTOM-RIGHT FREE FOR WEBCAM -->
  <div class="card card-right">
    <div class="card-header">
      <div class="card-title">Pascal API &amp; WebSocket Execution Log</div>
    </div>
    <div class="log-console" id="logConsole"></div>

    <div class="card-header" style="margin-top:6px;">
      <div class="card-title" id="holdersSectionTitle">Public On-Chain Positions &amp; Book Depth</div>
    </div>
    <table class="table-compact">
      <thead>
        <tr><th style="width:46%">Wallet / Outcome</th><th style="width:24%">Side</th><th style="width:30%">Contracts</th></tr>
      </thead>
      <tbody id="holdersBody">
        <tr><td colspan="3" style="color:var(--muted)">Loading market positions...</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- =========================================================================
     10-SECOND CENTER-SCREEN TV WEATHER TELEMETRY OVERLAY MODAL (OVERCAST -> RAIN -> DOWNPOUR)
     ========================================================================= -->
<div class="weather-overlay" id="weatherOverlayModal">
  <div class="weather-modal-card" id="weatherModalCard">
    <div class="wm-top-row">
      <div class="wm-badge">📡 Wi-Fi HaLow Stadium Weather Station (Sub-GHz Live IP)</div>
      <div class="wm-badge" id="wmPhaseBadge" style="border-color:#38bdf8; color:#38bdf8;">1-SEC CONTINUOUS STREAM</div>
    </div>

    <!-- CIRCULAR COUNTDOWN TIMER (10 -> 1) -->
    <div class="timer-circle-wrap">
      <svg class="timer-svg" viewBox="0 0 88 88">
        <circle class="timer-circle-bg" cx="44" cy="44" r="38"></circle>
        <circle class="timer-circle-fg" id="wmTimerCircle" cx="44" cy="44" r="38"></circle>
      </svg>
      <div class="timer-num" id="wmTimerNum">10s</div>
    </div>

    <!-- ANIMATED BROADCAST TV WEATHER GRAPHIC (NO SUN: OVERCAST & FOG -> LIGHT RAIN -> HEAVY DOWNPOUR & LIGHTNING) -->
    <div class="weather-stage" id="wmStage">
      <div id="wmRainLayer" style="position:absolute; inset:0; display:none; pointer-events:none;"></div>

      <!-- PHASE 1 GRAPHIC: DENSE OVERCAST CLOUDS & STADIUM FOG/MIST (Seconds 10, 9, 8 - NO SUN!) -->
      <div id="wmGraphicOvercast" style="display:flex; align-items:center; justify-content:center; position:relative; width:280px; height:160px;">
        <svg width="210" height="115" viewBox="0 0 200 110" style="position:absolute; top:8px; left:15px; animation: floatCloud 3.2s ease-in-out infinite;">
          <path d="M35 80 H160 A22 22 0 0 0 160 36 A34 34 0 0 0 92 24 A28 28 0 0 0 35 80 Z" fill="#64748b" stroke="#94a3b8" stroke-width="2.5"/>
        </svg>
        <svg width="195" height="105" viewBox="0 0 190 100" style="position:absolute; top:26px; right:12px; animation: floatCloud 2.6s ease-in-out infinite reverse;">
          <path d="M30 82 H150 A20 20 0 0 0 150 42 A30 30 0 0 0 85 32 A25 25 0 0 0 30 82 Z" fill="#475569" stroke="#cbd5e1" stroke-width="2"/>
        </svg>
        <svg width="240" height="45" viewBox="0 0 240 45" style="position:absolute; bottom:8px; animation: driftFog 3s ease-in-out infinite;">
          <line x1="20" y1="10" x2="220" y2="10" stroke="#94a3b8" stroke-width="4" stroke-linecap="round" stroke-dasharray="140 20"/>
          <line x1="35" y1="22" x2="205" y2="22" stroke="#64748b" stroke-width="4" stroke-linecap="round" stroke-dasharray="110 25"/>
          <line x1="15" y1="34" x2="225" y2="34" stroke="#94a3b8" stroke-width="3.5" stroke-linecap="round" stroke-dasharray="90 30"/>
        </svg>
      </div>

      <!-- PHASE 2 & 3 GRAPHIC: DARK STORM CLOUDS, RAIN & FLASHING LIGHTNING (Seconds 7 -> 1) -->
      <div id="wmGraphicStorm" style="display:none; align-items:center; justify-content:center; position:relative; width:270px; height:165px;">
        <svg width="225" height="120" viewBox="0 0 200 110" style="position:absolute; top:6px; animation: floatCloud 2s ease-in-out infinite;">
          <path d="M40 82 H160 A24 24 0 0 0 160 34 A36 36 0 0 0 92 22 A30 30 0 0 0 40 82 Z" fill="#334155" stroke="#64748b" stroke-width="3"/>
          <path d="M25 92 H135 A20 20 0 0 0 135 52 A28 28 0 0 0 80 42 A24 24 0 0 0 25 92 Z" fill="#1e293b" stroke="#475569" stroke-width="2.5"/>
        </svg>
        <svg id="wmLightningSvg" width="90" height="95" viewBox="0 0 80 90" style="position:absolute; bottom:4px; left:92px; animation: flashLightning 1.05s infinite;">
          <polygon points="45,5 15,48 38,48 25,85 68,36 43,36" fill="#fde047" stroke="#f59e0b" stroke-width="2"/>
        </svg>
      </div>
    </div>

    <div class="wm-headline" id="wmHeadline">☁️🌫️ Overcast &amp; Foggy Stadium Conditions</div>
    <div class="wm-subline" id="wmSubline">HaLoWave Miner receiving continuous 1-second Sub-GHz IP packets from Wi-Fi HaLow Stadium Weather Station...</div>

    <div class="wm-metrics-row">
      <div class="wm-metric">
        <div class="lbl">Wind Speed</div>
        <div class="val" id="wmWind">14.2 km/h</div>
      </div>
      <div class="wm-metric">
        <div class="lbl">Rain Rate</div>
        <div class="val" id="wmRain">0.0 mm/h</div>
      </div>
      <div class="wm-metric">
        <div class="lbl">Humidity</div>
        <div class="val" id="wmHum">74%</div>
      </div>
      <div class="wm-metric">
        <div class="lbl">Draw (X) Model</div>
        <div class="val" id="wmDrawProb" style="color:var(--cyan)">23%</div>
      </div>
    </div>

    <div class="wm-progress-bg">
      <div class="wm-progress-fill" id="wmProgressFill"></div>
    </div>
  </div>
</div>

<!-- LIGHTBOX MODAL -->
<div class="lightbox" id="lightboxModal" onclick="closeLightbox()">
  <div class="lightbox-box" onclick="event.stopPropagation()">
    <div class="lightbox-header">
      <div class="lightbox-title" id="lbTitle">Image Preview</div>
      <button class="lightbox-close" onclick="closeLightbox()">✕ Close (ESC)</button>
    </div>
    <div class="lightbox-img-wrap">
      <img id="lbImg" src="" alt="Preview">
    </div>
    <div class="lightbox-desc" id="lbDesc"></div>
  </div>
</div>

<script>
let matches = [];
let currentMatch = null;
let stormActive = false;
let stormTransitioning = false;
let pascalWs = null;
let wsPingTimer = null;

function updateModeStyle() {
  const modeEl = document.querySelector('input[name="execMode"]:checked');
  const isPost = modeEl && modeEl.value === "post_only";
  document.getElementById("lblModeFill").classList.toggle("selected", !isPost);
  document.getElementById("lblModePost").classList.toggle("selected", isPost);
}

function makePascalLogoTransparent() {
  const img = document.getElementById("pascalLogoRaw");
  const canvas = document.getElementById("pascalLogoCanvas");
  if (!img || !canvas || !img.naturalWidth) return;
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0);
  try {
    const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const d = imgData.data;
    for (let i = 0; i < d.length; i += 4) {
      const r = d[i], g = d[i+1], b = d[i+2];
      if (r > 235 && g > 235 && b > 235) {
        d[i+3] = 0;
      } else if (r > 215 && g > 215 && b > 215) {
        d[i+3] = Math.round(((255 - ((r+g+b)/3)) / 40) * 255);
      }
    }
    ctx.putImageData(imgData, 0, 0);
  } catch (e) {}
}

function setRainDropsCount(count) {
  const layer = document.getElementById("wmRainLayer");
  if (!layer) return;
  layer.innerHTML = "";
  for (let i = 0; i < count; i++) {
    const drop = document.createElement("div");
    drop.className = "rain-streak";
    drop.style.left = Math.round(Math.random() * 96) + "%";
    drop.style.top = Math.round(Math.random() * 40) + "px";
    drop.style.animationDelay = (Math.random() * 0.65).toFixed(2) + "s";
    drop.style.animationDuration = (count > 20 ? (0.42 + Math.random() * 0.25) : (0.7 + Math.random() * 0.3)).toFixed(2) + "s";
    layer.appendChild(drop);
  }
}

function connectPascalWebSocket(symbolsList) {
  try {
    if (pascalWs) {
      pascalWs.close();
      pascalWs = null;
    }
    if (wsPingTimer) clearInterval(wsPingTimer);

    pascalWs = new WebSocket("wss://data.pascal.trade/ws");
    pascalWs.onopen = () => {
      document.getElementById("wsBadge").innerHTML = `<span class="dot"></span> WS: book &amp; account Live`;
      const channels = symbolsList.map(s => ({channel: "book", symbol: s}));
      channels.push({channel: "account", owner: "HHyHJD9zBN9riw3yn38AM7Suy5riu7YXCreGhEW4zUn8"});
      pascalWs.send(JSON.stringify({type: "subscribe", channels: channels}));
      addLog(`wss://data.pascal.trade/ws -> Subscribed to book (${symbolsList.join(", ")}) & account`, "log-info");

      wsPingTimer = setInterval(() => {
        if (pascalWs && pascalWs.readyState === WebSocket.OPEN) {
          pascalWs.send(JSON.stringify({type: "ping"}));
        }
      }, 25000);
    };

    pascalWs.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === "update" && msg.data && msg.data.fills && msg.data.fills.length > 0) {
          const f = msg.data.fills[0];
          addLog(`⚡ [WS account fill] Symbol: ${f.symbol} | Size: ${f.fill_size} @ $${f.fill_price} | builder_fee_paid_usd: $${f.builder_fee_paid_usd || '0.003542'}`, "log-ok");
        }
      } catch (e) {}
    };
  } catch (e) {}
}

function openLightbox(src, title, desc) {
  document.getElementById("lbImg").src = src;
  document.getElementById("lbTitle").innerText = title;
  document.getElementById("lbDesc").innerText = desc;
  document.getElementById("lightboxModal").classList.add("open");
}

function closeLightbox() {
  document.getElementById("lightboxModal").classList.remove("open");
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeLightbox();
});

function addLog(msg, cls="log-info") {
  const box = document.getElementById("logConsole");
  const t = new Date().toLocaleTimeString();
  const div = document.createElement("div");
  div.className = "log-entry " + cls;
  div.innerHTML = `<strong>[${t}]</strong> ${msg}`;
  box.prepend(div);
}

setInterval(() => {
  if (stormTransitioning) return;
  const jitter = (Math.random() - 0.5) * 0.8;
  if (!stormActive) {
    const rssi = -61 + Math.round((Math.random() - 0.5) * 2);
    document.getElementById("valRssi").innerText = rssi + " dBm";
    document.getElementById("valWind").innerText = (14.2 + jitter).toFixed(1) + " km/h";
    document.getElementById("valRain").innerText = "0.0 mm/h";
    document.getElementById("valTemp").innerText = (13.6 + jitter * 0.2).toFixed(1) + " °C";
    document.getElementById("subHum").innerText = "Rel. Humidity: 74% (Foggy)";
  } else {
    const rssi = -63 + Math.round((Math.random() - 0.5) * 2);
    document.getElementById("valRssi").innerText = rssi + " dBm";
    document.getElementById("valWind").innerText = (54.2 + jitter * 1.4).toFixed(1) + " km/h";
    document.getElementById("valRain").innerText = (28.4 + jitter * 0.7).toFixed(1) + " mm/h";
    document.getElementById("valTemp").innerText = (11.2 + jitter * 0.1).toFixed(1) + " °C";
    document.getElementById("subHum").innerText = "Rel. Humidity: 96% (Saturated)";
  }
}, 1000);

function triggerStorm() {
  if (stormTransitioning) return;
  stormTransitioning = true;

  const overlay = document.getElementById("weatherOverlayModal");
  const modalCard = document.getElementById("weatherModalCard");
  const circle = document.getElementById("wmTimerCircle");
  const numEl = document.getElementById("wmTimerNum");
  const overcastGraphic = document.getElementById("wmGraphicOvercast");
  const stormGraphic = document.getElementById("wmGraphicStorm");
  const rainLayer = document.getElementById("wmRainLayer");
  const lightningSvg = document.getElementById("wmLightningSvg");
  const headline = document.getElementById("wmHeadline");
  const subline = document.getElementById("wmSubline");
  const phaseBadge = document.getElementById("wmPhaseBadge");
  const progFill = document.getElementById("wmProgressFill");

  const baseDraw = currentMatch ? Math.round(((parseFloat(currentMatch.draw.best_bid||0.22)+parseFloat(currentMatch.draw.best_ask||0.23))/2)*100) : 23;

  modalCard.classList.remove("storm-phase");
  overcastGraphic.style.display = "flex";
  stormGraphic.style.display = "none";
  rainLayer.style.display = "none";
  circle.style.stroke = "#38bdf8";
  circle.style.strokeDashoffset = "0";
  numEl.innerText = "10s";
  progFill.style.width = "4%";
  phaseBadge.innerText = "SUB-GHZ STREAM: OVERCAST & FOGGY";
  phaseBadge.style.color = "#38bdf8";
  phaseBadge.style.borderColor = "#38bdf8";
  headline.innerText = "☁️🌫️ Overcast & Foggy Stadium Conditions";
  subline.innerText = "Wi-Fi HaLow Stadium Weather Station streaming continuous 1-second IP packets to HaLoWave Miner...";
  document.getElementById("wmWind").innerText = "14.2 km/h";
  document.getElementById("wmRain").innerText = "0.0 mm/h";
  document.getElementById("wmHum").innerText = "74%";
  document.getElementById("wmDrawProb").innerText = baseDraw + "%";
  document.getElementById("wmDrawProb").style.color = "#38bdf8";

  overlay.classList.add("open");
  addLog("📡 [Wi-Fi HaLow Stadium Weather Station] Real-time Sub-GHz IP telemetry sequence started (Overcast & Foggy baseline)...", "log-info");

  const totalSec = 10;
  const circum = 238.76;
  let secLeft = 10;

  const stepInterval = setInterval(() => {
    secLeft -= 1;
    const elapsed = totalSec - secLeft;
    const frac = elapsed / totalSec;
    circle.style.strokeDashoffset = String((frac * circum).toFixed(1));
    progFill.style.width = Math.min(100, Math.round(frac * 100)) + "%";
    numEl.innerText = secLeft > 0 ? (secLeft + "s") : "✓";

    if (secLeft === 9) {
      document.getElementById("wmWind").innerText = "18.6 km/h";
      document.getElementById("wmHum").innerText = "78%";
      headline.innerText = "🌫️☁️ Dense Fog & Low Cloud Ceiling Over Pitch";
      subline.innerText = "Barometric pressure dropping; humidity rising to 78% across stadium sensors...";
    } else if (secLeft === 8) {
      document.getElementById("wmWind").innerText = "23.4 km/h";
      document.getElementById("wmRain").innerText = "1.8 mm/h";
      document.getElementById("wmHum").innerText = "81%";
      headline.innerText = "☁️💨 First Raindrops & Wind Gusts Detected";
      subline.innerText = "Wi-Fi HaLow 1-second IP link transmitting initial precipitation onset...";
    } else if (secLeft === 7) {
      overcastGraphic.style.display = "none";
      stormGraphic.style.display = "flex";
      setRainDropsCount(14);
      rainLayer.style.display = "block";
      lightningSvg.style.display = "none";
      circle.style.stroke = "#38bdf8";
      phaseBadge.innerText = "🌧️ STEADY RAIN ONSET";
      headline.innerText = "🌧️ Steady Rain Begins Across Stadium Turf";
      subline.innerText = "1-sec HaLow IP stream updates instantly (while 10-min LoRaWAN sensors remain blind)...";
      document.getElementById("wmWind").innerText = "29.5 km/h";
      document.getElementById("wmRain").innerText = "7.4 mm/h";
      document.getElementById("wmHum").innerText = "85%";
      document.getElementById("wmDrawProb").innerText = (baseDraw + 1) + "%";
    } else if (secLeft === 6) {
      document.getElementById("wmWind").innerText = "35.8 km/h";
      document.getElementById("wmRain").innerText = "12.8 mm/h";
      document.getElementById("wmHum").innerText = "88%";
      document.getElementById("wmDrawProb").innerText = (baseDraw + 2) + "%";
      headline.innerText = "🌧️💨 Rain Intensifying & Cross-Pitch Gusts Rising";
      subline.innerText = "Wet turf slowing ball roll; HaLoWave model begins adjusting 1X2 probabilities...";
      updateMatchCards(0.35);
    } else if (secLeft === 5) {
      circle.style.stroke = "#f59e0b";
      phaseBadge.innerText = "🌧️💨 SQUALL THRESHOLD CROSSED";
      phaseBadge.style.color = "#fbbf24";
      phaseBadge.style.borderColor = "#fbbf24";
      document.getElementById("wmWind").innerText = "42.1 km/h";
      document.getElementById("wmRain").innerText = "18.5 mm/h";
      document.getElementById("wmHum").innerText = "91%";
      document.getElementById("wmDrawProb").innerText = (baseDraw + 3) + "%";
      document.getElementById("wmDrawProb").style.color = "#fbbf24";
      headline.innerText = "🌧️⚠️ Strong Wind Gusts (>40 km/h) & Heavy Rain";
      subline.innerText = "Expected goals (xG) dropping for technical passing teams...";
      updateMatchCards(0.5);
    } else if (secLeft === 4) {
      modalCard.classList.add("storm-phase");
      setRainDropsCount(38);
      lightningSvg.style.display = "block";
      phaseBadge.innerText = "⛈️ HEAVY STADIUM DOWNPOUR";
      headline.innerText = "⛈️⚡ Heavy Downpour & Gale Gusts Hit Stadium!";
      subline.innerText = "Wi-Fi HaLow Stadium Weather Station records 24.2 mm/h torrential rain in real time...";
      document.getElementById("wmWind").innerText = "48.7 km/h";
      document.getElementById("wmRain").innerText = "24.2 mm/h";
      document.getElementById("wmHum").innerText = "94%";
      document.getElementById("wmDrawProb").innerText = (baseDraw + 4) + "%";
      addLog("⛈️ [Sub-GHz HaLow Alert] Heavy Stadium Downpour detected: Wind 48.7 km/h | Rain 24.2 mm/h.", "log-warn");
      updateMatchCards(0.75);
    } else if (secLeft === 3) {
      document.getElementById("wmWind").innerText = "52.4 km/h";
      document.getElementById("wmRain").innerText = "27.1 mm/h";
      document.getElementById("wmHum").innerText = "95%";
      document.getElementById("wmDrawProb").innerText = (baseDraw + 5) + "%";
      headline.innerText = "⛈️🌊 Waterlogged Pitch & 52.4 km/h Gale Gusts";
      subline.innerText = "Penalizing Favorite (-9%) while boosting Draw (+6%) and Home Underdog (+3%)...";
    } else if (secLeft === 2) {
      document.getElementById("wmWind").innerText = "54.2 km/h";
      document.getElementById("wmRain").innerText = "28.4 mm/h";
      document.getElementById("wmHum").innerText = "96%";
      document.getElementById("wmDrawProb").innerText = (baseDraw + 6) + "% (+6% EDGE)";
      headline.innerText = "⚡ Repricing 1X2 Probabilities Against Pascal Order Book";
      subline.innerText = "Draw repriced to " + (baseDraw + 6) + "% (+6% Edge) and Home Underdog +3% Edge!";
      updateMatchCards(1.0);
    } else if (secLeft === 1) {
      circle.style.stroke = "#10b981";
      headline.innerText = "✅ HaLoWave 1X2 Weather Model Locked!";
      subline.innerText = "Ready for 1-Tap Order Execution on Pascal Mainnet with HaLoWave Builder Fee routing.";
    } else if (secLeft <= 0) {
      clearInterval(stepInterval);
      stormActive = true;
      stormTransitioning = false;
      overlay.classList.remove("open");

      ["boxWind", "boxRain", "boxTemp", "boxRssi"].forEach(id => {
        document.getElementById(id).classList.add("storm-alert");
      });
      document.getElementById("valWind").style.color = "#fbbf24";
      document.getElementById("valRain").style.color = "#38bdf8";
      document.getElementById("valTemp").style.color = "#fbbf24";
      document.getElementById("valWind").innerText = "54.2 km/h";
      document.getElementById("valRain").innerText = "28.4 mm/h";
      document.getElementById("valTemp").innerText = "11.2 °C";
      document.getElementById("subHum").innerText = "Rel. Humidity: 96% (Saturated)";
      document.getElementById("subHum").style.color = "#38bdf8";
      document.getElementById("valRssi").innerText = "-63 dBm";
      document.getElementById("subWind").innerText = "⚠️ Gale gusts (>45 km/h)";
      document.getElementById("subWind").style.color = "#fbbf24";
      document.getElementById("subRain").innerText = "⚠️ Heavy downpour on pitch";
      document.getElementById("subRain").style.color = "#38bdf8";

      document.getElementById("cardDraw").classList.add("storm-highlight");
      document.getElementById("cardHome").classList.add("underdog-highlight");
      document.getElementById("btnStorm").innerText = "⛈️ Downpour Telemetry Active (Wind 54.2 km/h | Rain 28.4 mm/h | 96% RH)";
      updateMatchCards(1.0);
      addLog("✅ [Sub-GHz HaLow Telemetry Locked] Downpour active (Wind 54.2 km/h, Rain 28.4 mm/h, 96% RH). 1X2 Model repriced: Draw +6% Edge, Home Underdog +3% Edge, Favorite -9%.", "log-ok");
    }
  }, 1000);
}

function resetWeather() {
  stormActive = false;
  stormTransitioning = false;
  document.getElementById("weatherOverlayModal").classList.remove("open");
  const btn = document.getElementById("btnStorm");
  btn.innerText = "⛈️ Simulate Stadium Weather Shift (Live HaLow Radar)";

  ["boxWind", "boxRain", "boxTemp", "boxRssi"].forEach(id => {
    document.getElementById(id).classList.remove("storm-alert");
  });

  document.getElementById("valWind").style.color = "var(--text)";
  document.getElementById("valRain").style.color = "var(--text)";
  document.getElementById("valTemp").style.color = "var(--text)";
  document.getElementById("valWind").innerText = "14.2 km/h";
  document.getElementById("valRain").innerText = "0.0 mm/h";
  document.getElementById("valTemp").innerText = "13.6 °C";
  document.getElementById("subHum").innerText = "Rel. Humidity: 74% (Foggy)";
  document.getElementById("subHum").style.color = "var(--muted)";
  document.getElementById("valRssi").innerText = "-61 dBm";
  document.getElementById("subWind").innerText = "Overcast & foggy pitch";
  document.getElementById("subWind").style.color = "var(--muted)";
  document.getElementById("subRain").innerText = "Dense cloud cover";
  document.getElementById("subRain").style.color = "var(--muted)";
  document.getElementById("cardDraw").classList.remove("storm-highlight");
  document.getElementById("cardHome").classList.remove("underdog-highlight");
  addLog("[Sub-GHz Telemetry] Weather parameters reset to overcast/foggy baseline (13.6 °C, 74% RH).", "log-info");
  updateMatchCards(0.0);
}

async function cancelAllOpenOrders() {
  addLog("🗑️ Sending reduce-only position close & order cancellation on HHyH...zUn8...", "log-warn");
  const res = await fetch("/api/cancel-orders", {method: "POST"}).then(r => r.json());
  document.getElementById("userHoldingTxt").innerText = `You hold 0 contracts`;
  document.getElementById("holdingPillBox").style.borderColor = "var(--cyan)";
  addLog(`✅ Account Reset Complete (${res.cancelled_count || 0} order(s) cancelled, ${res.closed_positions || 0} position(s) closed via reduce_only). Position reset to 0.`, "log-ok");
  setTimeout(() => onSelectMatch(), 1100);
}

async function loadMatches(force=false) {
  addLog("GET https://data.pascal.trade/api/v1/markets -> Filtering clean 1X2 soccer matches...", "log-info");
  const res = await fetch(`/api/matches?refresh=${force?1:0}`).then(r => r.json());
  matches = res.matches || [];
  document.getElementById("marketsCountLbl").innerText = `${matches.length} Live 1X2 Matches`;

  const sel = document.getElementById("marketSelect");
  sel.innerHTML = "";
  matches.forEach((m, idx) => {
    const opt = document.createElement("option");
    opt.value = idx;
    opt.innerText = `[${m.league_badge}] ${m.match_title} — (1: $${m.home.best_ask} | X: $${m.draw.best_ask} | 2: $${m.away.best_ask})`;
    sel.appendChild(opt);
  });
  if (matches.length > 0) onSelectMatch();
}

async function onSelectMatch() {
  const idx = document.getElementById("marketSelect").value;
  currentMatch = matches[idx];
  if (!currentMatch) return;

  document.getElementById("matchTitle").innerText = `${currentMatch.match_title}`;
  document.getElementById("matchSymbol").innerText = `1: ${currentMatch.home.symbol} | X: ${currentMatch.draw.symbol} | 2: ${currentMatch.away.symbol}`;

  document.getElementById("titleHome").innerText = currentMatch.home.label;
  document.getElementById("symHome").innerText = currentMatch.home.symbol;

  document.getElementById("titleDraw").innerText = currentMatch.draw.label;
  document.getElementById("symDraw").innerText = currentMatch.draw.symbol;

  document.getElementById("titleAway").innerText = currentMatch.away.label;
  document.getElementById("symAway").innerText = currentMatch.away.symbol;

  updateMatchCards(stormActive ? 1.0 : 0.0);

  const symsArr = Array.from(new Set([currentMatch.home.symbol, currentMatch.draw.symbol, currentMatch.away.symbol]));
  connectPascalWebSocket(symsArr);

  const det = await fetch(`/api/match-details?symbols=${encodeURIComponent(symsArr.join(","))}`).then(r => r.json());
  if (det.books) {
    ["home", "draw", "away"].forEach(k => {
      const s = currentMatch[k].symbol;
      if (det.books[s]) {
        if (det.books[s].best_bid) currentMatch[k].best_bid = det.books[s].best_bid;
        if (det.books[s].best_ask) currentMatch[k].best_ask = det.books[s].best_ask;
        if (det.books[s].raw_bid) currentMatch[k].raw_bid = det.books[s].raw_bid;
        if (det.books[s].raw_ask) currentMatch[k].raw_ask = det.books[s].raw_ask;
      }
    });
    updateMatchCards(stormActive ? 1.0 : 0.0);
  }
  if (det.available_cash_usd !== undefined) {
    document.getElementById("traderBadge").innerHTML = `<span class="dot"></span> Trader: HHyH...zUn8 ($${parseFloat(det.available_cash_usd).toFixed(2)})`;
  }
  if (det.holding_text) {
    document.getElementById("userHoldingTxt").innerText = det.holding_text;
  } else {
    document.getElementById("userHoldingTxt").innerText = `You hold 0 contracts`;
  }

  const tb = document.getElementById("holdersBody");
  tb.innerHTML = "";
  if (det.holders && det.holders.length > 0) {
    det.holders.slice(0, 5).forEach(h => {
      const tr = document.createElement("tr");
      const wShort = h.owner.length > 16 ? (h.owner.slice(0, 6) + "..." + h.owner.slice(-4)) : h.owner;
      tr.innerHTML = `<td>${wShort}</td><td style="color:${h.side.includes('LONG') || h.side.includes('BID') ? '#34d399' : '#fbbf24'}">${h.side}</td><td>${h.position}</td>`;
      tb.appendChild(tr);
    });
  } else {
    tb.innerHTML = `<tr><td colspan="3" style="color:var(--muted)">No resting positions</td></tr>`;
  }
}

function updateMatchCards(factor = (stormActive ? 1.0 : 0.0)) {
  if (!currentMatch) return;

  const hBid = parseFloat(currentMatch.home.best_bid || 0.16);
  const hAsk = parseFloat(currentMatch.home.best_ask || 0.17);
  const dBid = parseFloat(currentMatch.draw.best_bid || 0.22);
  const dAsk = parseFloat(currentMatch.draw.best_ask || 0.23);
  const aBid = parseFloat(currentMatch.away.best_bid || 0.62);
  const aAsk = parseFloat(currentMatch.away.best_ask || 0.63);

  let hProb = Math.round(((hBid + hAsk) / 2) * 100);
  let dProb = Math.round(((dBid + dAsk) / 2) * 100);
  let aProb = Math.round(((aBid + aAsk) / 2) * 100);

  let mHome = hProb;
  let mDraw = dProb;
  let mAway = aProb;

  const elModelHome = document.getElementById("modelHome");
  const elModelDraw = document.getElementById("modelDraw");
  const elModelAway = document.getElementById("modelAway");

  elModelHome.className = "halow-prob";
  elModelDraw.className = "halow-prob";
  elModelAway.className = "halow-prob";

  if (factor > 0) {
    const dShift = Math.round(6 * factor);
    const uShift = Math.round(3 * factor);
    const fShift = dShift + uShift;
    mDraw = Math.min(85, dProb + dShift);
    elModelDraw.classList.add("changed-up");

    if (hProb <= aProb) {
      mHome = Math.min(85, hProb + uShift);
      mAway = Math.max(5, aProb - fShift);
      elModelHome.classList.add("changed-up-green");
      elModelAway.classList.add("changed-down");
      document.getElementById("ribbonHome").innerText = `⚡ 1 · HOME (+${uShift}% EDGE)`;
      document.getElementById("ribbonAway").innerText = `🌧️ 2 · AWAY (-${fShift}% RAIN)`;
    } else {
      mAway = Math.min(85, aProb + uShift);
      mHome = Math.max(5, hProb - fShift);
      elModelAway.classList.add("changed-up-green");
      elModelHome.classList.add("changed-down");
      document.getElementById("ribbonHome").innerText = `🌧️ 1 · HOME (-${fShift}% RAIN)`;
      document.getElementById("ribbonAway").innerText = `⚡ 2 · AWAY (+${uShift}% EDGE)`;
    }
    document.getElementById("ribbonDraw").innerText = `⚡ X · DRAW (+${dShift}% EDGE)`;
  } else {
    document.getElementById("ribbonHome").innerText = "1 · HOME WIN";
    document.getElementById("ribbonDraw").innerText = "X · DRAW OUTCOME";
    document.getElementById("ribbonAway").innerText = "2 · AWAY WIN";
  }

  document.getElementById("probHome").innerText = hProb + "%";
  elModelHome.innerText = factor > 0 ? `${hProb}% ➔ ${mHome}%` : `${mHome}%`;
  document.getElementById("priceHomeInfo").innerText = `Bid: $${hBid.toFixed(2)} | Ask: $${hAsk.toFixed(2)}`;

  document.getElementById("probDraw").innerText = dProb + "%";
  elModelDraw.innerText = factor > 0 ? `${dProb}% ➔ ${mDraw}%` : `${mDraw}%`;
  document.getElementById("priceDrawInfo").innerText = `Bid: $${dBid.toFixed(2)} | Ask: $${dAsk.toFixed(2)}`;

  document.getElementById("probAway").innerText = aProb + "%";
  elModelAway.innerText = factor > 0 ? `${aProb}% ➔ ${mAway}%` : `${mAway}%`;
  document.getElementById("priceAwayInfo").innerText = `Bid: $${aBid.toFixed(2)} | Ask: $${aAsk.toFixed(2)}`;
}

async function placeMatchOrder(outcomeKey) {
  if (!currentMatch) return;
  const target = currentMatch[outcomeKey];
  const sizeId = outcomeKey === "home" ? "sizeHome" : (outcomeKey === "draw" ? "sizeDraw" : "sizeAway");
  const size = document.getElementById(sizeId).value || "1";
  const side = target.side || "BID";

  const modeEl = document.querySelector('input[name="execMode"]:checked');
  const isPostOnly = modeEl && modeEl.value === "post_only";

  let rawPrice = isPostOnly ? (target.raw_bid || target.best_bid || "0.220000") : (side === "BID" ? (target.raw_ask || target.best_ask || "0.230000") : (target.raw_bid || target.best_bid || "0.220000"));
  let priceNum = parseFloat(rawPrice) || 0.23;

  addLog(`POST https://trade.pascal.trade/api/v1/orders -> ${side} ${size}x ${target.symbol} (${target.label}) @ $${priceNum.toFixed(2)} | post_only: ${isPostOnly} | builder: EzUh...69Rt`, "log-warn");

  try {
    const res = await fetch("/api/place-order", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        symbol: target.symbol,
        label: target.label,
        side: side,
        price: String(rawPrice),
        size: String(size),
        post_only: isPostOnly
      })
    }).then(r => r.json());

    const pResp = res.pascal_response || {};
    const d = pResp.data || {};
    const ord = d.order || {};
    const fills = d.fills || [];
    const execPrice = parseFloat(res.executed_price || priceNum);
    const feePaid = (fills.length > 0 && fills[0].builder_fee_paid_usd) ? fills[0].builder_fee_paid_usd : (parseFloat(size) * execPrice * (1 - execPrice) * 0.02).toFixed(6);
    const orderId = ord.order_id || ord.client_order_id || String(Date.now());

    addLog(`✅ <strong>ORDER ACCEPTED BY PASCAL MAINNET:</strong><br>• order_id: <code>${orderId}</code><br>• symbol: <code>${target.symbol}</code> (${target.label}) | side: <code>${side}</code> | size: <code>${size}</code> @ <code>$${execPrice.toFixed(2)}</code><br>• builder_pubkey: <code>EzUh...69Rt</code> | builder_fee_paid_usd: <code>$${feePaid}</code>`, "log-ok");

    document.getElementById("userHoldingTxt").innerText = `You hold ${size} ${target.label}`;
    document.getElementById("holdingPillBox").style.borderColor = "#10b981";
    setTimeout(() => onSelectMatch(), 900);
  } catch (err) {
    addLog(`⚠️ Local error: ${err.message}`, "log-warn");
  }
}

window.onload = () => {
  makePascalLogoTransparent();
  updateModeStyle();
  addLog("HaLoWave PitchPulse initialized. Trader (HHyH...zUn8) & Builder (EzUh...69Rt) keys active.", "log-ok");
  loadMatches(false);
};
</script>
</body>
</html>
"""


def format_holder_size(pos_val):
    if isinstance(pos_val, dict):
        for k in ("size", "contracts", "position", "amount", "value"):
            if k in pos_val:
                return str(pos_val[k])
        return json.dumps(pos_val)
    return str(pos_val)


class PitchPulseHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, obj, code=200):
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            raw = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        if path in IMAGE_ALIASES:
            local_file = resolve_local_image(path)
            if local_file and os.path.exists(local_file):
                with open(local_file, "rb") as f:
                    data = f.read()
                self.send_response(200)
                ctype = "image/png" if local_file.lower().endswith(".png") else "image/jpeg"
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

        if path == "/api/matches":
            qs = urllib.parse.parse_qs(parsed.query)
            force = qs.get("refresh", ["0"])[0] == "1"
            match_list = extract_soccer_matches(force_refresh=force)
            self.send_json({
                "matches": match_list,
                "owner_pubkey": CONFIG["owner_pubkey"],
                "builder_pubkey": CONFIG["builder_pubkey"]
            })
            return

        if path == "/api/match-details":
            qs = urllib.parse.parse_qs(parsed.query)
            symbols_str = qs.get("symbols", [""])[0]
            sym_list = [s.strip() for s in symbols_str.split(",") if s.strip()]
            books_out = {}
            holders_list = []
            holding_text = None
            available_cash = 2.97

            if sym_list:
                joined = ",".join(urllib.parse.quote(s) for s in sym_list[:10])
                b_res = http_json(f"{DATA_API}/api/v1/books?symbols={joined}")
                book_depth_fallback = []
                if isinstance(b_res, dict) and b_res.get("status") == "success":
                    books = b_res.get("data", {}).get("books", {})
                    for s_key, sb in books.items():
                        bids = sb.get("bids", [])
                        asks = sb.get("asks", [])
                        books_out[s_key] = {
                            "best_bid": f"{float(bids[0][0]):.2f}" if bids else None,
                            "best_ask": f"{float(asks[0][0]):.2f}" if asks else None,
                            "raw_bid": str(bids[0][0]) if bids else None,
                            "raw_ask": str(asks[0][0]) if asks else None
                        }
                        if bids:
                            book_depth_fallback.append({
                                "owner": f"{s_key}",
                                "side": f"BID @ ${float(bids[0][0]):.2f}",
                                "position": f"{bids[0][1]} contracts"
                            })
                        if asks:
                            book_depth_fallback.append({
                                "owner": f"{s_key}",
                                "side": f"ASK @ ${float(asks[0][0]):.2f}",
                                "position": f"{asks[0][1]} contracts"
                            })

                h_res = http_json(f"{DATA_API}/api/v1/top-holders?symbols={joined}&limit=10")
                if isinstance(h_res, dict) and h_res.get("status") == "success":
                    all_h = h_res.get("data", {}).get("holders", {})
                    for s_k in sym_list:
                        h_map = all_h.get(s_k, {})
                        short_tag = s_k.split(".")[-1] if "." in s_k else ""
                        for item in h_map.get("longs", []):
                            holders_list.append({
                                "owner": item.get("owner", ""),
                                "side": f"LONG ({short_tag})",
                                "position": format_holder_size(item.get("position", ""))
                            })
                        for item in h_map.get("shorts", []):
                            holders_list.append({
                                "owner": item.get("owner", ""),
                                "side": f"SHORT ({short_tag})",
                                "position": format_holder_size(item.get("position", ""))
                            })

                if not holders_list and book_depth_fallback:
                    holders_list = book_depth_fallback[:5]

                if CONFIG["owner_pubkey"]:
                    acc = http_json(f"{DATA_API}/api/v1/accounts/{CONFIG['owner_pubkey']}")
                    if isinstance(acc, dict) and acc.get("status") == "success":
                        acc_data = acc.get("data", {})
                        # collateral_usd di Pascal riporta già il collaterale libero aggiornato!
                        available_cash = float(acc_data.get("collateral_usd") or 2.97)
                        positions = acc_data.get("positions", [])
                        orders = acc_data.get("orders", [])

                        match_pos = [p for p in positions if p.get("symbol") in sym_list and float(p.get("size", 0)) != 0]
                        match_ord = [o for o in orders if o.get("symbol") in sym_list]
                        if match_pos:
                            sz = match_pos[0].get("size", "0")
                            sym_p = match_pos[0].get("symbol", "")
                            short_lbl = "Draw" if "DRAW" in sym_p else sym_p.split(".")[-1]
                            holding_text = f"You hold {sz} {short_lbl}"
                        elif match_ord:
                            tot_ord_sz = sum(int(float(o.get("size", 1))) for o in match_ord)
                            sym_o = match_ord[0].get("symbol", "")
                            short_lbl = "Draw" if "DRAW" in sym_o else sym_o.split(".")[-1]
                            holding_text = f"You hold {tot_ord_sz} {short_lbl} (Order)"

            self.send_json({
                "books": books_out,
                "holders": holders_list,
                "holding_text": holding_text,
                "available_cash_usd": available_cash
            })
            return

        return super().do_GET()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

            if self.path == "/api/cancel-orders":
                res_c = reset_account_orders_and_positions()
                self.send_json(res_c)
                return

            if self.path == "/api/place-order":
                symbol = body.get("symbol")
                side = body.get("side", "BID")
                price = body.get("price", "0.230000")
                size = body.get("size", "1")
                post_only = bool(body.get("post_only", False))

                resp, b_note, exec_p = execute_pascal_order_clean(symbol, side, price, size, post_only=post_only)

                self.send_json({
                    "status": resp.get("status", "unknown") if isinstance(resp, dict) else "unknown",
                    "pascal_response": resp,
                    "builder_note": b_note,
                    "executed_price": exec_p
                })
                return
        except Exception as e:
            self.send_json({
                "status": "error",
                "pascal_response": {"status": "error", "message": str(e)},
                "builder_note": CONFIG["builder_pubkey"]
            })


if __name__ == "__main__":
    port = 8080
    print("============================================================")
    print(" HaLoWave PitchPulse x Pascal Server Running")
    print(f" Open in browser: http://localhost:{port}")
    print("============================================================")
    server = HTTPServer(("127.0.0.1", port), PitchPulseHandler)
    server.serve_forever()