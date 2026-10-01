"""
Spotify kapcsolat: bejelentkezés (OAuth), playlist olvasás, mentés, lejátszás.

Hogyan működik az OAuth bejelentkezés?
1. Az app egy linket mutat a Spotify bejelentkező oldalára. A linkben benne van
   az app azonosítója (client_id), a kért jogosultságok (scope) és hogy hova
   küldje vissza a felhasználót (redirect_uri).
2. A felhasználó belép a Spotify oldalán és jóváhagyja a jogosultságokat.
3. A Spotify visszairányít a redirect_uri-ra, egy egyszer használatos kóddal:
   http://127.0.0.1:8501/?code=AQB...
   Ez maga a Streamlit app, ezért az app.py a URL-ből (st.query_params) olvassa ki.
4. Ezt a kódot a client_secret-tel együtt beváltjuk egy tokenre. A token
   egy kb. 1 órán át érvényes "belépőkártya", amit minden API kéréshez mellékelünk.
   Mellé kapunk egy refresh_token-t, amivel lejárat után újat kérhetünk
   anélkül, hogy a felhasználónak újra be kellene lépnie.

Miért st.session_state-ben tároljuk a tokent?
- A Streamlit minden kattintásnál újrafuttatja az egész scriptet, így a sima
  változók elvesznek. A session_state túléli az újrafuttatást.
- Böngészőfülenként külön session van, tehát mindenki a saját tokenjét látja.
  Ha fájlba mentenénk (a spotipy alapból egy .cache fájlt ír), akkor az app
  mindenkinek ugyanazzal a fiókkal dolgozna.
- Hátránya: oldal-frissítés (F5) után új session indul, és újra be kell lépni.
"""

import os

import spotipy
from dotenv import load_dotenv
from spotipy.cache_handler import CacheHandler
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

# A Spotify a "localhost"-ot nem fogadja el, csak a 127.0.0.1-et.
# Ugyanezt kell beírni a Spotify Developer Dashboardon is, betűre pontosan.
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8501")

# Az óráknál használt fő playlist ("Köredzés").
MAIN_PLAYLIST_ID = os.environ.get("SPOTIFY_MAIN_PLAYLIST_ID", "5kr2MXhGk0YKFM9rcdJ4mr")

# Jogosultságok, amiket a bejelentkezésnél kérünk. Csak annyit kérünk,
# amennyi tényleg kell - a felhasználó ezt a listát látja a jóváhagyásnál.
SCOPES = [
    "playlist-read-private",        # saját (privát) playlistek olvasása
    "playlist-read-collaborative",  # közös playlistek olvasása
    "playlist-modify-public",       # óra-playlistek létrehozása, számok hozzáadása
    "playlist-modify-private",
    "user-read-playback-state",     # milyen eszközön szól a Spotify
    "user-modify-playback-state",   # lejátszás indítása (Premium kell hozzá)
]


def is_configured():
    """Be vannak-e állítva a Spotify kulcsok a .env-ben?"""
    return bool(os.environ.get("SPOTIFY_CLIENT_ID") and os.environ.get("SPOTIFY_CLIENT_SECRET"))


# ---------------------------------------------------------------------------
# Bejelentkezés
# ---------------------------------------------------------------------------

class SessionCacheHandler(CacheHandler):
    """
    A spotipy egy "cache handler"-en keresztül olvassa és írja a tokent.
    Ez a változat a Streamlit session_state-be teszi (a spotipy-ban van
    hasonló Flaskhoz és Djangohoz is, Streamlithez nincs).

    Ennek az az előnye, hogy amikor a token lejár és a spotipy magától
    frissíti, az új token automatikusan visszakerül a session_state-be.
    """

    def __init__(self, session, key="spotify_token"):
        self.session = session
        self.key = key

    def get_cached_token(self):
        return self.session.get(self.key)

    def save_token_to_cache(self, token_info):
        self.session[self.key] = token_info


def get_auth_manager(session):
    # A client_id és client_secret a SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET
    # környezeti változókból jön (a .env-ből). A secret-et soha ne tedd a kódba!
    return SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=REDIRECT_URI,
        scope=" ".join(SCOPES),
        cache_handler=SessionCacheHandler(session),
        open_browser=False,  # nem nyitunk böngészőt, a linket a UI mutatja
    )


def get_login_url(session):
    """Az 1. lépés linkje: ide küldjük a felhasználót bejelentkezni."""
    return get_auth_manager(session).get_authorize_url()


def handle_callback(session, code):
    """
    A 4. lépés: a visszakapott kódot tokenre váltjuk. A token a cache
    handleren keresztül magától bekerül a session-be.
    A kód csak egyszer használható, ezért utána ki kell venni a URL-ből.
    """
    get_auth_manager(session).get_access_token(code, as_dict=False, check_cache=False)


def get_client(session):
    """
    Spotify kliens a session tokenjével. Az auth_manager-en keresztül a
    spotipy minden kérés előtt ellenőrzi a tokent, és ha lejárt, frissíti.
    """
    return spotipy.Spotify(auth_manager=get_auth_manager(session))


# ---------------------------------------------------------------------------
# Olvasás
# ---------------------------------------------------------------------------

def _simplify_track(t):
    """A Spotify track objektumából csak azt tartjuk meg, ami nekünk kell."""
    return {
        "id": t["id"],
        "uri": t["uri"],
        "title": t["name"],
        "artists": [a["name"] for a in t["artists"]],
        "duration_ms": t["duration_ms"],
        "url": t.get("external_urls", {}).get("spotify", ""),
    }


def fetch_playlist_tracks(sp, playlist_id=MAIN_PLAYLIST_ID):
    """
    A playlist összes száma. A Spotify egyszerre max 50 elemet ad vissza
    ("lapozás"): a válaszban a "next" mező a következő oldal címe, ha van.
    Fejlesztői módban csak saját vagy közös playlist tartalma olvasható.
    """
    tracks = []
    try:
        page = sp.playlist_items(playlist_id, limit=50, additional_types=("track",))
    except spotipy.SpotifyException as e:
        # 403 = a playlist nem a bejelentkezett felhasználóé (és nem is közös)
        if e.http_status == 403:
            raise PermissionError(
                "Ezt a playlistet a Spotify csak a tulajdonosának vagy közreműködőnek "
                "mutatja meg. Jelentkezz be a tulajdonos fiókjával, vagy állíts be egy "
                "saját playlistet (SPOTIFY_MAIN_PLAYLIST_ID a .env-ben)."
            ) from e
        raise
    while page:
        for entry in page["items"]:
            # 2026 óta a mező neve "item", régebben "track" volt
            t = entry.get("item") or entry.get("track")
            # Helyi fájloknak és törölt számoknak nincs ID-ja, ezeket kihagyjuk
            if t and t.get("id") and t.get("type", "track") == "track":
                tracks.append(_simplify_track(t))
        page = sp.next(page) if page.get("next") else None
    return tracks


def search_track(sp, artist, title):
    """
    Egy Last.fm-ből jött ajánlás (előadó + cím) megkeresése a Spotify-on.
    A keresés több találatot ad; azt fogadjuk el, ahol az előadó is egyezik,
    különben egy azonos című, de teljesen más szám jöhetne be.
    """
    queries = [f'track:"{title}" artist:"{artist}"', f"{artist} {title}"]
    for q in queries:
        # Bejelentkezett felhasználónál a Spotify magától a fiók országában keres
        result = sp.search(q=q, type="track", limit=5)
        for t in result["tracks"]["items"]:
            if any(a["name"].lower() == artist.lower() for a in t["artists"]):
                return _simplify_track(t)
    return None


# ---------------------------------------------------------------------------
# Írás és lejátszás
# ---------------------------------------------------------------------------

def create_playlist(sp, name, track_uris, description=""):
    """
    Új playlist a bejelentkezett felhasználónál, a megadott számokkal.
    A spotipy current_user_playlist_create függvénye a POST /me/playlists
    végpontot hívja, ami a 2026-os változások után is működik.
    """
    playlist = sp.current_user_playlist_create(name, public=False, description=description)
    # Egyszerre max 100 szám adható hozzá
    for i in range(0, len(track_uris), 100):
        sp.playlist_add_items(playlist["id"], track_uris[i:i + 100])
    return {"id": playlist["id"], "url": playlist["external_urls"]["spotify"]}


def add_to_playlist(sp, track_uris, playlist_id=MAIN_PLAYLIST_ID):
    sp.playlist_add_items(playlist_id, track_uris)


def delete_playlist(sp, playlist_id):
    """
    A Spotify-on igazából nem lehet playlistet törölni, csak "leiratkozni"
    róla - ha a tulajdonos iratkozik le, eltűnik a könyvtárából.
    A spotipy current_user_unfollow_playlist-je még a régi, 2026-ban
    megszűnt végpontot hívja, ezért az újat (DELETE /me/library) közvetlenül.
    """
    sp._delete("me/library", uris=f"spotify:playlist:{playlist_id}")


def play_playlist(sp, playlist_id):
    """
    Lejátszás indítása. Feltételek: Premium, és a Spotify legyen nyitva
    valamelyik eszközön (telefon, gép, hangszóró).
    Ha egyik eszköz sem aktív, az elsőt választjuk ki.
    Visszaad: None ha sikerült, különben a hibaüzenet.
    """
    devices = sp.devices()["devices"]
    if not devices:
        return "Nincs elérhető eszköz - nyisd meg a Spotify-t a telefonon vagy a gépen."
    active = next((d for d in devices if d["is_active"]), devices[0])
    try:
        sp.start_playback(device_id=active["id"], context_uri=f"spotify:playlist:{playlist_id}")
    except spotipy.SpotifyException as e:
        return f"Nem sikerült elindítani: {e.msg}"
    return None
