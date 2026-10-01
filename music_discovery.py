"""
Zene-felfedezés: új számok keresése a meglévő playlist alapján.

Honnan tudjuk, mi "hasonló"?
- A Spotify 2024 óta nem ad ajánlásokat új fejlesztői appoknak, ezért
  a Last.fm-et használjuk. A Last.fm hasonlósága abból jön, hogy emberek milliói
  mit hallgatnak egymás után ("aki X-et hallgatja, az Y-t is") - gyakorlatilag
  ugyanaz a jel, mintha playlisteket néznénk át közös számok után.

Az algoritmus röviden (részletek a recommend() függvénynél):
1. A playlist előadóihoz lekérjük a hasonló előadókat. Ha egy előadó a playlist
   SOK előadójához hasonló, az erős jel -> magas pontszám.
2. A legjobb jelölt előadók legnépszerűbb számai lesznek a jelöltek.
3. Ahol a Last.fm-nek szám-szintű adata is van (track.getSimilar), az extra pont.
4. Műfaj (tag) egyezés alapján még egy kis bónusz.
"""

import json
import math
import os
import re
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

import requests
from dotenv import load_dotenv

# A .env fájlból betölti a kulcsokat környezeti változóba (LASTFM_API_KEY stb.)
load_dotenv()

LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"
CACHE_FILE = "music_cache.json"
CACHE_MAX_AGE = 30 * 24 * 3600  # 30 nap másodpercben

# A pontozás súlyai. Ezekkel érdemes játszani, ha az ajánlások nem tetszenek.
W_ARTIST = 1.0  # hasonló előadó számai
W_TRACK = 2.0   # szám-szintű hasonlóság (ritkább, de pontosabb, ezért többet ér)
W_TAG = 0.5     # műfaj-egyezés bónusz


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
# Minden API-választ elmentünk egy JSON fájlba. Így az első futás lassú
# (több száz kérés), utána viszont szinte azonnali, és nem terheljük az API-t.
# A lock azért kell, mert párhuzamos szálakból is írunk ugyanabba a dict-be.

_cache = None
_cache_lock = threading.Lock()


def _load_cache():
    global _cache
    if _cache is None:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        else:
            _cache = {}
    return _cache


def save_cache():
    with _cache_lock:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_load_cache(), f, ensure_ascii=False)


def _cache_get(key):
    entry = _load_cache().get(key)
    if entry and time.time() - entry["t"] < CACHE_MAX_AGE:
        return entry["v"]
    return None


def _cache_set(key, value):
    with _cache_lock:
        _load_cache()[key] = {"t": time.time(), "v": value}


# ---------------------------------------------------------------------------
# Last.fm
# ---------------------------------------------------------------------------
# Minden Last.fm hívás ugyanúgy néz ki: GET kérés a közös URL-re, a "method"
# paraméter mondja meg, mit kérünk. Bejelentkezés nem kell, csak az API kulcs.
# autocorrect=1: a Last.fm kijavítja az elírt előadóneveket.

def _lastfm(method, **params):
    key = "lastfm|" + method + "|" + json.dumps(params, sort_keys=True, ensure_ascii=False)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    query = {
        "method": method,
        "api_key": os.environ["LASTFM_API_KEY"],
        "format": "json",
        "autocorrect": 1,
        **params,
    }
    try:
        resp = requests.get(LASTFM_URL, params=query, timeout=15)
        data = resp.json()
    except (requests.RequestException, ValueError):
        return {}  # hálózati hiba: nem cache-eljük, legközelebb újrapróbálja

    # Az "error" kulcs pl. akkor jön, ha a Last.fm nem ismeri az előadót.
    # Ezt is cache-eljük, különben minden futásnál újra megkérdeznénk.
    _cache_set(key, data)
    return data


def similar_artists(artist, limit=30):
    """[(előadó, match 0-1)] - a match azt mutatja, mennyire erős a kapcsolat."""
    data = _lastfm("artist.getsimilar", artist=artist, limit=limit)
    items = data.get("similarartists", {}).get("artist", [])
    return [(a["name"], float(a["match"])) for a in items]


def similar_tracks(artist, title, limit=30):
    """[(előadó, cím, match 0-1)] - sok kisebb számnál üres a lista."""
    data = _lastfm("track.getsimilar", artist=artist, track=clean_title(title), limit=limit)
    items = data.get("similartracks", {}).get("track", [])
    return [(t["artist"]["name"], t["name"], float(t["match"])) for t in items]


def artist_top_tracks(artist, limit=5):
    """[(előadó, cím)] - az előadó legtöbbet hallgatott számai a Last.fm-en."""
    data = _lastfm("artist.gettoptracks", artist=artist, limit=limit)
    items = data.get("toptracks", {}).get("track", [])
    return [(t["artist"]["name"], t["name"]) for t in items]


def artist_tags(artist):
    """{tag: súly 0-1} - a műfaj-címkék, amiket a felhasználók adtak az előadónak."""
    data = _lastfm("artist.gettoptags", artist=artist)
    items = data.get("toptags", {}).get("tag", [])[:10]
    return {t["name"].lower(): int(t["count"]) / 100 for t in items if int(t["count"]) > 0}


# ---------------------------------------------------------------------------
# Elutasított ajánlások
# ---------------------------------------------------------------------------
# Ez nem cache, hanem a felhasználó döntése, ezért külön fájlban van
# (a cache bármikor törölhető, ez nem).

USER_DATA_FILE = "music_data.json"


def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data.setdefault("blocked", [])  # [track_key, ...]
    return data


def save_user_data(data):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def block_track(artist, title):
    data = load_user_data()
    key = track_key(artist, title)
    if key not in data["blocked"]:
        data["blocked"].append(key)
        save_user_data(data)


# ---------------------------------------------------------------------------
# Segédfüggvények
# ---------------------------------------------------------------------------

def clean_title(title):
    """'Ocho (BEAUZ & KEVU VIP) [Radio Edit]' -> 'Ocho'. Kereséshez kell."""
    title = re.sub(r"\s*[\(\[].*?[\)\]]", "", title)
    return title.split(" - ")[0].strip()


def track_key(artist, title):
    """Egységes azonosító a duplikációk kiszűréséhez (kisbetű, tisztított cím)."""
    return artist.strip().lower() + "|" + clean_title(title).lower()


def _cosine(a, b):
    """Két {tag: súly} dict hasonlósága 0 és 1 között."""
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return dot / norm if norm else 0.0


def _parallel(func, items, workers=4):
    # A Last.fm kb. 5 kérés/mp-et tűr el, 4 szál ezen belül marad.
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(func, items))


# ---------------------------------------------------------------------------
# Az ajánló
# ---------------------------------------------------------------------------

def build_tag_profile(artists):
    """
    A playlist "műfaj-ujjlenyomata": összeadjuk az előadók tagjeit.
    Ha egy előadónál rossz tagek jönnek (pl. névegyezés miatt egy black metal
    zenekart talál), az a sok többi előadó mellett elhanyagolható lesz.
    """
    profile = Counter()
    for tags in _parallel(artist_tags, artists):
        profile.update(tags)
    return dict(profile.most_common(20))


def recommend(seeds, n=30, blocked=(), top_artists=40, tracks_per_artist=5):
    """
    Új számokat ajánl a seeds (a meglévő playlist) alapján.

    seeds: [{"artists": ["Előadó1", ...], "title": "Cím"}, ...]
    blocked: track_key-ek, amiket a felhasználó már elutasított
    Visszaad: [{"artist", "title", "score", "reasons": [...]}, ...] pontszám szerint
    """
    seed_keys = {track_key(s["artists"][0], s["title"]) for s in seeds}
    excluded = seed_keys | set(blocked)
    my_artists = sorted({s["artists"][0] for s in seeds})

    # 1. lépés: előadó-pontszámok.
    # Minden saját előadóhoz lekérjük a hasonlókat, és összeadjuk a match
    # értékeket. Pl. ha "Sonny Wern" 5 saját előadóhoz is hasonló, 5 match
    # összege lesz a pontja - így jön ki, ki illik a playlist EGÉSZÉHEZ.
    artist_score = defaultdict(float)
    artist_reason = defaultdict(list)
    for mine, sims in zip(my_artists, _parallel(similar_artists, my_artists)):
        for name, match in sims:
            artist_score[name] += match
            artist_reason[name].append(mine)

    # A saját előadók is szerepelhetnek: tőlük is jöhetnek új számok.
    # Kapnak egy alap pontot, hogy ne szoruljanak ki.
    for mine in my_artists:
        artist_score[mine] += 1.0

    # Normalizálás 0-1 közé, hogy a súlyok (W_*) összemérhetők legyenek.
    max_score = max(artist_score.values(), default=1)
    for name in artist_score:
        artist_score[name] /= max_score

    best_artists = sorted(artist_score, key=artist_score.get, reverse=True)[:top_artists]

    # 2. lépés: jelölt számok a legjobb előadóktól.
    scores = defaultdict(float)
    info = {}
    reasons = defaultdict(list)

    def add(artist, title, points, reason):
        key = track_key(artist, title)
        if key in excluded:
            return
        scores[key] += points
        info.setdefault(key, (artist, title))
        if reason not in reasons[key]:
            reasons[key].append(reason)

    for artist, tracks in zip(best_artists, _parallel(lambda a: artist_top_tracks(a, tracks_per_artist), best_artists)):
        if artist in my_artists:
            reason = f"Már szereplő előadó: {artist}"
        else:
            based_on = ", ".join(artist_reason[artist][:3])
            reason = f"Hasonló előadó ({based_on} alapján)"
        for t_artist, t_title in tracks:
            add(t_artist, t_title, W_ARTIST * artist_score[artist], reason)

    # 3. lépés: szám-szintű hasonlóság, ahol van adat.
    # Ha egy szám több saját számhoz is hasonló, mindegyiktől kap pontot.
    sim_lists = _parallel(lambda s: similar_tracks(s["artists"][0], s["title"]), seeds)
    for seed, sims in zip(seeds, sim_lists):
        for t_artist, t_title, match in sims:
            add(t_artist, t_title, W_TRACK * match, f"Hasonló ehhez: {seed['title']}")

    # 4. lépés: műfaj-bónusz. Csak az első ~150 jelöltre számoljuk, mert
    # minden új előadó egy újabb API hívás, a lista alja meg úgysem fér be.
    profile = build_tag_profile(my_artists)
    shortlist = sorted(scores, key=scores.get, reverse=True)[:150]
    cand_artists = sorted({info[k][0] for k in shortlist})
    tag_sim = dict(zip(cand_artists, (_cosine(profile, t) for t in _parallel(artist_tags, cand_artists))))
    for key in shortlist:
        scores[key] += W_TAG * tag_sim.get(info[key][0], 0)

    save_cache()

    ranked = sorted(shortlist, key=scores.get, reverse=True)[:n]
    return [
        {
            "artist": info[k][0],
            "title": info[k][1],
            "score": round(scores[k], 3),
            "reasons": reasons[k],
        }
        for k in ranked
    ]
