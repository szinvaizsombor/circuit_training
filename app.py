import streamlit as st
import random
from datetime import date
import workout_logic as wl
import class_history as ch
import music_discovery as md
import spotify_api as spa

# Mintaadatok inicializálása, ha üres a fájl
wl.init_sample_data()

st.set_page_config(page_title="Köredzés Generáló", page_icon="🏋️‍♂️", layout="centered")

# Spotify bejelentkezés után ide tér vissza a böngésző (?code=... a URL-ben)
if "code" in st.query_params and spa.is_configured():
    spa.handle_callback(st.session_state, st.query_params["code"])
    st.query_params.clear()
    st.rerun()
if "error" in st.query_params:
    st.error(f"A Spotify bejelentkezés nem sikerült: {st.query_params['error']}")
    st.query_params.clear()

st.title("🏋️‍♂️ Köredzés Generáló App")


# --- SEGÉDFÜGGVÉNYEK ---

def get_pool(sp):
    """A fő playlist számai, session-önként egyszer betöltve. Hiba esetén None."""
    if "pool" not in st.session_state:
        with st.spinner("Fő playlist betöltése..."):
            try:
                tracks = spa.fetch_playlist_tracks(sp)
            except PermissionError as e:
                st.error(str(e))
                return None
            st.session_state.pool = tracks
    return st.session_state.pool


def get_recommendations(sp, pool):
    """Last.fm ajánlások, megkeresve a Spotify-on. Session-önként egyszer fut."""
    if "recs" not in st.session_state:
        pool_ids = {t["id"] for t in pool}
        seeds = [{"artists": t["artists"], "title": t["title"]} for t in pool]
        raw = md.recommend(seeds, n=40, blocked=md.load_user_data()["blocked"])

        found = []
        for r in raw:
            t = spa.search_track(sp, r["artist"], r["title"])
            if t and t["id"] not in pool_ids and all(f["id"] != t["id"] for f in found):
                found.append({**t, "reasons": r["reasons"], "lastfm": (r["artist"], r["title"])})
        st.session_state.recs = found
    return st.session_state.recs


def spotify_ready():
    """Igaz, ha be vagyunk jelentkezve és a fő playlist betöltődött; különben kiírja, mi hiányzik."""
    if not spa.is_configured():
        st.warning("Hiányzik a SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET a .env fájlból.")
        return False
    if "spotify_token" not in st.session_state:
        st.write("Ehhez jelentkezz be a Spotify fiókoddal.")
        # target="_self": ugyanebben a fülben nyílik meg, nem újban
        st.markdown(
            f'<a href="{spa.get_login_url(st.session_state)}" target="_self">🎧 Bejelentkezés Spotify-jal</a>',
            unsafe_allow_html=True,
        )
        return False
    return pool is not None


def class_and_day_picker(key):
    """Óra + dátum választó. Visszaad: (óra, "ÉÉÉÉ-HH-NN") vagy (None, None), ha nincs óra."""
    classes = ch.load_classes()
    if not classes:
        st.info("Még nincs óra. Az **Órák** fülön hozhatsz létre egyet.")
        return None, None
    by_id = {c["id"]: c for c in classes}
    col_cls, col_day = st.columns(2)
    with col_cls:
        class_id = st.selectbox(
            "Óra",
            options=list(by_id),
            format_func=lambda i: f"{by_id[i]['name']} ({by_id[i]['minutes']} perc)",
            key=f"{key}_class",
        )
    with col_day:
        day = st.date_input("Alkalom napja", value=date.today(), format="YYYY.MM.DD", key=f"{key}_day")
    return by_id[class_id], day.isoformat()


def last_played_label(ago):
    if ago is None:
        return "még nem szólt"
    if ago == 0:
        return "előző alkalommal"
    return f"{ago + 1} alkalommal ezelőtt"


def session_summary(session):
    workout = f"✅ {len(session['workout'])} gyakorlat" if session["workout"] else "➖ nincs edzés"
    if session["playlist_id"]:
        music = f"✅ [{len(session['track_ids'])} szám]({session['playlist_url']})"
    elif session["track_ids"]:
        music = f"{len(session['track_ids'])} szám (playlist törölve)"
    else:
        music = "➖ nincs playlist"
    return f"**{session['date']}** · {workout} · {music}"


def delete_session_button(cls, session):
    """🗑️ gomb megerősítéssel. Az alkalom Spotify playlistjét is törli, ha be vagyunk jelentkezve."""
    with st.popover("🗑️", help="Alkalom törlése"):
        st.warning(f"Biztosan törlöd a(z) **{session['date']}** alkalmat?")
        if session["playlist_id"]:
            if sp:
                st.caption("A hozzá tartozó Spotify playlist is törlődik.")
            else:
                st.caption("A Spotify playlist megmarad, mert nem vagy bejelentkezve.")
        if st.button("Igen, töröld", key=f"delsess_{cls['id']}_{session['date']}", type="primary"):
            if session["playlist_id"] and sp:
                spa.delete_playlist(sp, session["playlist_id"])
            ch.delete_session(cls["id"], session["date"])
            st.rerun()


# A Spotify beágyazott lejátszója. Teljes számokat akkor játszik le, ha a
# böngészőben be vagy jelentkezve a Spotify-ba (open.spotify.com), különben
# csak 30 mp-es előzeteseket. Ez független az app saját bejelentkezésétől.

def embed_track(track_id):
    st.iframe(f"https://open.spotify.com/embed/track/{track_id}?utm_source=generator", height=80)


def embed_playlist(playlist_id, height=380, version=0):
    # A "v" paraméter csak arra kell, hogy új URL legyen -> a böngésző újratölti a lejátszót
    st.iframe(f"https://open.spotify.com/embed/playlist/{playlist_id}?utm_source=generator&v={version}", height=height)


def refresh_main_playlist():
    """A fő playlist újratöltése a Spotify-ról, és a beágyazott lejátszó frissítése."""
    st.session_state.pop("pool", None)
    st.session_state.embed_version = st.session_state.get("embed_version", 0) + 1


def preview_toggle(track_id, key):
    """🎧 gomb, ami ki-be kapcsolja a szám lejátszóját (egyszerre csak egy látszik)."""
    playing = st.session_state.get("preview_id") == track_id
    if st.button("⏹️" if playing else "🎧", key=key, help="Meghallgatás"):
        st.session_state.preview_id = None if playing else track_id
        st.rerun()
    return playing


# Az óra indítása / bezárása callbackben történik, mert a callback még a
# script újrafutása ELŐTT lefut - így be tudjuk állítani, melyik fül legyen
# nyitva (st.session_state["tab"]), mielőtt a fülek létrejönnek.

def start_class(cls, day):
    st.session_state.active_session = {"class_id": cls["id"], "date": day}
    st.session_state.tab = f"🏁 {cls['name']}"


def close_class():
    st.session_state.pop("active_session", None)
    st.session_state.tab = "🗓️ Órák"


# --- SPOTIFY ---
# Ha be vagyunk jelentkezve, a fő playlistet egyszer betöltjük, és minden fül ezt használja.
sp = None
pool = None
if spa.is_configured() and "spotify_token" in st.session_state:
    sp = spa.get_client(st.session_state)
    pool = get_pool(sp)

# --- FÜLEK ---
active = st.session_state.get("active_session")
active_class = ch.get_class(active["class_id"]) if active else None
active_session = ch.get_session(active_class, active["date"]) if active_class else None

tab_labels = [
    "🗓️ Órák",
    "🎲 Edzés generálása",
    "🎵 Playlist generálása",
    "📋 Gyakorlatok listája",
    "➕ Új gyakorlat hozzáadása",
    "🎧 Fő playlist",
    "🔍 Zenefelfedezés",
]
# Az elindított óra csak akkor jelenik meg külön fülként, ha van ilyen
if active_session:
    tab_labels.insert(1, f"🏁 {active_class['name']}")
if st.session_state.get("tab") not in tab_labels:
    st.session_state.tab = tab_labels[0]

# key + on_change="rerun": így a megnyitott fül a session_state["tab"]-ban van,
# és kódból is át lehet váltani egy másik fülre.
tabs = dict(zip(tab_labels, st.tabs(tab_labels, key="tab", on_change="rerun")))

# --- ÓRÁK ---
with tabs["🗓️ Órák"]:
    st.header("Órák")

    with st.expander("➕ Új óra"):
        with st.form("new_class_form", clear_on_submit=True):
            class_name = st.text_input("Óra neve", placeholder="pl. Kedd esti TRX")
            class_minutes = st.number_input("Hossz (perc)", min_value=10, max_value=120, value=45, step=5)
            if st.form_submit_button("Mentés", type="primary"):
                if not class_name.strip():
                    st.error("Az óra nevét kötelező megadni!")
                else:
                    ch.add_class(class_name.strip(), int(class_minutes))
                    st.rerun()

    classes = ch.load_classes()
    today = date.today().isoformat()
    if not classes:
        st.info("Még nincs óra. Hozz létre egyet fent!")

    for cls in classes:
        with st.container(border=True):
            col_title, col_edit, col_del = st.columns([6, 1, 1])
            with col_title:
                st.subheader(cls["name"])
                st.caption(f"{cls['minutes']} perc")

            with col_edit:
                with st.popover("✏️"):
                    with st.form(f"edit_class_{cls['id']}"):
                        e_name = st.text_input("Óra neve", value=cls["name"], key=f"e_name_{cls['id']}")
                        e_minutes = st.number_input("Hossz (perc)", min_value=10, max_value=120, value=cls["minutes"], step=5, key=f"e_min_{cls['id']}")
                        if st.form_submit_button("💾 Mentés", type="primary", key=f"e_save_{cls['id']}"):
                            ch.update_class(cls["id"], e_name.strip() or cls["name"], int(e_minutes))
                            st.rerun()

            with col_del:
                with st.popover("🗑️"):
                    st.warning(f"Biztosan törlöd a(z) **{cls['name']}** órát az összes alkalmával együtt?")
                    if st.button("Igen, töröld", key=f"del_class_{cls['id']}", type="primary"):
                        ch.delete_class(cls["id"])
                        st.rerun()

            upcoming = [s for s in cls["sessions"] if s["date"] >= today]
            past = [s for s in cls["sessions"] if s["date"] < today]

            if not upcoming:
                st.caption("Nincs mai vagy későbbi alkalom. Az edzés- és playlist generálásnál rendelhetsz hozzá.")
            for s in upcoming:
                col_info, col_start, col_del = st.columns([6, 2, 1])
                with col_info:
                    st.markdown(session_summary(s))
                with col_start:
                    st.button("🏁 Indítás", key=f"start_{cls['id']}_{s['date']}", on_click=start_class, args=(cls, s["date"]))
                with col_del:
                    delete_session_button(cls, s)

            if past:
                with st.expander(f"Korábbi alkalmak ({len(past)})"):
                    for s in reversed(past):
                        col_info, col_start, col_pl, col_del = st.columns([5, 1, 1, 1])
                        with col_info:
                            st.markdown(session_summary(s))
                        with col_start:
                            st.button("🏁", key=f"start_{cls['id']}_{s['date']}", on_click=start_class, args=(cls, s["date"]), help="Indítás")
                        with col_pl:
                            # A régi playlistek törölhetők a Spotify-ról - a számok listája
                            # megmarad, így a rotáció továbbra is tudja, mi szólt.
                            if s["playlist_id"] and sp:
                                if st.button("🧹", key=f"delpl_{s['playlist_id']}", help="Playlist törlése a Spotify-ról"):
                                    spa.delete_playlist(sp, s["playlist_id"])
                                    ch.forget_playlist(cls["id"], s["playlist_id"])
                                    st.rerun()
                        with col_del:
                            delete_session_button(cls, s)

# --- ELINDÍTOTT ÓRA ---
if active_session:
    with tabs[f"🏁 {active_class['name']}"]:
        col_title, col_close = st.columns([5, 1])
        with col_title:
            st.header(f"🏁 {active_class['name']}")
            st.caption(active_session["date"])
        with col_close:
            st.button("✖️ Bezárás", on_click=close_class)

        if active_session["playlist_id"]:
            embed_playlist(active_session["playlist_id"])
            if sp and st.button("▶️ Lejátszás a telefonon / hangszórón", help="Ott indítja el, ahol a Spotify nyitva van"):
                error = spa.play_playlist(sp, active_session["playlist_id"])
                if error:
                    st.error(error)
                else:
                    st.toast("Lejátszás elindítva 🎶")
        else:
            st.info("Ehhez az alkalomhoz még nincs playlist (Playlist generálása fül).")

        st.subheader("Gyakorlatok")
        if not active_session["workout"]:
            st.info("Ehhez az alkalomhoz még nincs edzés (Edzés generálása fül).")
        for i, ex in enumerate(active_session["workout"], 1):
            st.markdown(f"### {i}. {ex['name']}")
            details = []
            if ex.get("equipment"):
                details.append("🛠️ " + ", ".join(ex["equipment"]))
            if ex.get("type"):
                details.append("🎯 " + ", ".join(ex["type"]))
            if details:
                st.caption(" | ".join(details))
            if ex.get("description"):
                st.write(ex["description"])

# --- EDZÉS GENERÁLÁSA ---
with tabs["🎲 Edzés generálása"]:
    st.header("Generálj egy új köredzést")

    all_equipment = wl.get_all_equipment()
    all_types = wl.get_all_types()

    num_exercises = st.number_input(
        "Hány gyakorlatból álljon a köredzés?", 
        min_value=1, 
        max_value=15, 
        value=4
    )

    st.subheader("Gyakorlatok szűrése pozíciónként:")

    slot_requirements = []
    for i in range(int(num_exercises)):
        st.markdown(f"**{i+1}. Gyakorlat pozíciója:**")
        col_eq, col_tp = st.columns(2)

        with col_eq:
            eq_sel = st.multiselect(
                "Eszköz(ök):", 
                options=all_equipment,
                key=f"slot_eq_{i}",
                help="Ha üres, bármilyen eszköz elfogadott."
            )
        with col_tp:
            tp_sel = st.multiselect(
                "Típus(ok):", 
                options=all_types,
                key=f"slot_tp_{i}",
                help="Ha üres, bármilyen típus elfogadott."
            )

        slot_requirements.append({"equipment": eq_sel, "type": tp_sel})

    st.write("") # Térköz
    if st.button("🚀 Edzés Generálása", type="primary"):
        workout = wl.generate_workout_by_slots(slot_requirements)
        st.session_state.current_workout = workout
        st.session_state.slot_requirements = slot_requirements

    # Generált edzés megjelenítése és szerkesztése
    if "current_workout" in st.session_state and st.session_state.current_workout:
        st.divider()
        st.subheader("🏋️ A generált köredzésed:")

        workout = st.session_state.current_workout
        reqs = st.session_state.get("slot_requirements", [{"equipment": [], "type": []} for _ in workout])

        for i, ex in enumerate(workout):
            with st.container():
                st.markdown("---")
                c_info, c_up, c_down = st.columns([6, 1, 1])

                with c_info:
                    eq_str = ", ".join(ex.get("equipment", [])) if ex.get("equipment") else "Nincs megadva"
                    tp_str = ", ".join(ex.get("type", [])) if ex.get("type") else "Nincs megadva"

                    st.markdown(f"### {i+1}. {ex['name']}")
                    st.write(f"🛠️ **Eszköz:** `{eq_str}` | 🎯 **Típus:** `{tp_str}`")

                    req_eq_str = ", ".join(reqs[i]["equipment"]) if (i < len(reqs) and reqs[i]["equipment"]) else "Bármelyik"
                    req_tp_str = ", ".join(reqs[i]["type"]) if (i < len(reqs) and reqs[i]["type"]) else "Bármelyik"
                    st.caption(f"📍 Pozíció elvárás -> Eszköz: *{req_eq_str}* | Típus: *{req_tp_str}*")

                    if ex.get("description"):
                        st.caption(f"ℹ️ {ex['description']}")

                # Fel mozgatás
                with c_up:
                    if i > 0:
                        if st.button("⬆️", key=f"up_{i}_{ex.get('id', i)}"):
                            workout[i], workout[i-1] = workout[i-1], workout[i]
                            if i < len(reqs):
                                reqs[i], reqs[i-1] = reqs[i-1], reqs[i]
                            st.session_state.current_workout = workout
                            st.session_state.slot_requirements = reqs
                            st.rerun()

                # Le mozgatás
                with c_down:
                    if i < len(workout) - 1:
                        if st.button("⬇️", key=f"down_{i}_{ex.get('id', i)}"):
                            workout[i], workout[i+1] = workout[i+1], workout[i]
                            if i < len(reqs):
                                reqs[i], reqs[i+1] = reqs[i+1], reqs[i]
                            st.session_state.current_workout = workout
                            st.session_state.slot_requirements = reqs
                            st.rerun()

                # Csere lehetőség az adott kategóriáknak megfelelő gyakorlatokból
                cur_req = reqs[i] if i < len(reqs) else {"equipment": [], "type": []}
                matching_exercises = wl.get_matching_exercises(
                    selected_equipment=cur_req["equipment"],
                    selected_types=cur_req["type"]
                )

                # Legördülő lista összeállítása: 1. elem a véletlenszerű opció
                dropdown_options = ["🎲 Véletlenszerű (Random)"] + [
                    f"{m['name']}  [🛠️ {', '.join(m.get('equipment', []))} | 🎯 {', '.join(m.get('type', []))}]"
                    for m in matching_exercises
                ]

                with st.expander(f"🔄 Gyakorlat cseréje a(z) {i+1}. helyen ({len(matching_exercises)} szűrt találatból)"):
                    selected_swap_label = st.selectbox(
                        "Válassz új gyakorlatot a listából:",
                        options=dropdown_options,
                        key=f"swap_select_{i}"
                    )

                    if st.button("Csere végrehajtása", key=f"btn_swap_{i}"):
                        selected_idx = dropdown_options.index(selected_swap_label)

                        if selected_idx == 0:
                            current_id = ex.get("id")
                            other_matching = [m for m in matching_exercises if m.get("id") != current_id]
                            if other_matching:
                                chosen = random.choice(other_matching)
                            elif matching_exercises:
                                chosen = random.choice(matching_exercises)
                            else:
                                chosen = ex
                            workout[i] = chosen
                        else:
                            chosen = matching_exercises[selected_idx - 1]
                            workout[i] = chosen

                        st.session_state.current_workout = workout
                        st.rerun()

        st.divider()
        st.subheader("📌 Hozzárendelés egy alkalomhoz")
        cls, day = class_and_day_picker("assign_workout")
        if cls and st.button("📌 Hozzárendelés", type="primary"):
            ch.assign_workout(cls["id"], day, workout)
            st.success(f"Az edzés hozzá lett rendelve: {cls['name']}, {day}")

# --- PLAYLIST GENERÁLÁSA ---
with tabs["🎵 Playlist generálása"]:
    st.header("Playlist generálása")

    if spotify_ready():
        cls, day = class_and_day_picker("playlist")
        if cls:
            n_new = st.slider("Új (felfedezett) számok", min_value=0, max_value=10, value=2)

            if st.button("🎲 Playlist generálása", type="primary"):
                new_tracks = []
                if n_new:
                    with st.spinner("Új számok keresése (első alkalommal kb. 1 perc)..."):
                        played = {tid for s in cls["sessions"] if s["date"] != day for tid in s["track_ids"]}
                        new_tracks = [t for t in get_recommendations(sp, pool) if t["id"] not in played]
                tracks = ch.build_session(cls, day, pool, new_tracks, n_new)
                st.session_state.draft = {"class_id": cls["id"], "day": day, "tracks": tracks}

            draft = st.session_state.get("draft")
            if draft and draft["class_id"] == cls["id"] and draft["day"] == day:
                tracks = draft["tracks"]
                total_min = sum(t["duration_ms"] for t in tracks) / 60000
                st.subheader(f"{len(tracks)} szám, {total_min:.0f} perc")

                for i, t in enumerate(tracks):
                    col_info, col_play = st.columns([8, 1])
                    with col_info:
                        new_badge = " 🆕" if t["is_new"] else ""
                        st.markdown(f"**{i + 1}. {', '.join(t['artists'])} – {t['title']}**{new_badge}")
                        st.caption(last_played_label(t["last_played"]))
                    with col_play:
                        playing = preview_toggle(t["id"], key=f"prev_draft_{i}")
                    if playing:
                        embed_track(t["id"])

                existing = ch.get_session(cls, day)
                if existing and existing["playlist_id"]:
                    st.caption("Ennek az alkalomnak már van playlistje - mentéskor a régi törlődik a Spotify-ról.")
                if st.button("💾 Mentés Spotify-ra és hozzárendelés", type="primary"):
                    with st.spinner("Mentés..."):
                        pl = spa.create_playlist(
                            sp, f"{cls['name']} – {day}", [t["uri"] for t in tracks], "Köredzés Generáló"
                        )
                        old_id = ch.assign_playlist(cls["id"], day, [t["id"] for t in tracks], pl["id"], pl["url"])
                        if old_id:
                            spa.delete_playlist(sp, old_id)
                    del st.session_state["draft"]
                    st.session_state.saved_playlist = pl["id"]
                    st.rerun()

            if st.session_state.get("saved_playlist"):
                session = ch.get_session(cls, day)
                if session and session["playlist_id"] == st.session_state.saved_playlist:
                    st.success(f"Elmentve és hozzárendelve: {cls['name']}, {day}")
                    embed_playlist(session["playlist_id"])

# --- GYAKORLATOK LISTÁZÁSA, SZERKESZTÉSE ÉS TÖRLESE ---
with tabs["📋 Gyakorlatok listája"]:
    st.header("Meglévő gyakorlatok kezelése")

    all_equipment = wl.get_all_equipment()
    all_types = wl.get_all_types()

    # Szűrés a listához
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        filter_eq = st.multiselect("Szűrés eszköz szerint:", options=all_equipment, key="list_filter_eq")
    with col_f2:
        filter_tp = st.multiselect("Szűrés típus szerint:", options=all_types, key="list_filter_tp")

    filtered_exercises = wl.get_matching_exercises(filter_eq, filter_tp)

    if not filtered_exercises:
        st.info("Nem található a feltételeknek megfelelő gyakorlat az adatbázisban.")
    else:
        st.caption(f"Összesen {len(filtered_exercises)} gyakorlat megjelenítve:")
        for ex in filtered_exercises:
            eq_str = ", ".join(ex.get("equipment", [])) if ex.get("equipment") else "-"
            tp_str = ", ".join(ex.get("type", [])) if ex.get("type") else "-"

            with st.expander(f"**{ex['name']}**  *(🛠️ {eq_str} | 🎯 {tp_str})*"):
                st.write(f"**Leírás:** {ex.get('description', 'Nincs leírás megadva.')}")
                st.write("")

                col_btn_edit, col_btn_del = st.columns([1, 1])

                # --- SZERKESZTÉS POPOVER ---
                with col_btn_edit:
                    with st.popover("✏️ Szerkesztés", use_container_width=True):
                        st.subheader(f"'{ex['name']}' szerkesztése")

                        with st.form(key=f"edit_form_{ex['id']}"):
                            edit_name = st.text_input("Gyakorlat neve", value=ex["name"])

                            st.markdown("**🛠️ Eszközök**")
                            edit_selected_eq = st.multiselect(
                                "Már létező eszközök:", 
                                options=all_equipment, 
                                default=[item for item in ex.get("equipment", []) if item in all_equipment],
                                key=f"edit_sel_eq_{ex['id']}"
                            )
                            edit_new_eq = st.text_input(
                                "Új eszköz(ök) hozzáadása (vesszővel elválasztva):",
                                key=f"edit_new_eq_{ex['id']}"
                            )

                            st.markdown("**🎯 Típusok / Izomcsoportok**")
                            edit_selected_tp = st.multiselect(
                                "Már létező típusok:", 
                                options=all_types, 
                                default=[item for item in ex.get("type", []) if item in all_types],
                                key=f"edit_sel_tp_{ex['id']}"
                            )
                            edit_new_tp = st.text_input(
                                "Új típus(ok) hozzáadása (vesszővel elválasztva):",
                                key=f"edit_new_tp_{ex['id']}"
                            )

                            edit_desc = st.text_area("Leírás", value=ex.get("description", ""))

                            save_btn = st.form_submit_button("💾 Módosítások mentése", type="primary")

                            if save_btn:
                                if not edit_name.strip():
                                    st.error("A gyakorlat neve nem lehet üres!")
                                else:
                                    # Eszközök összefésülése
                                    final_eq = list(edit_selected_eq)
                                    if edit_new_eq.strip():
                                        for item in [x.strip() for x in edit_new_eq.split(",") if x.strip()]:
                                            if item not in final_eq:
                                                final_eq.append(item)

                                    # Típusok összefésülése
                                    final_tp = list(edit_selected_tp)
                                    if edit_new_tp.strip():
                                        for item in [x.strip() for x in edit_new_tp.split(",") if x.strip()]:
                                            if item not in final_tp:
                                                final_tp.append(item)

                                    wl.update_exercise(
                                        ex["id"], 
                                        edit_name.strip(), 
                                        final_eq, 
                                        final_tp, 
                                        edit_desc.strip()
                                    )
                                    st.success("Sikeres módosítás!")
                                    st.rerun()

                # --- TÖRLESE POPOVER (MEGERŐSÍTÉSSEL) ---
                with col_btn_del:
                    with st.popover("🗑️ Törlés", use_container_width=True):
                        st.warning(f"Biztosan törölni szeretnéd a(z) **{ex['name']}** gyakorlatot?")
                        if st.button("Igen, töröld véglegesen", key=f"confirm_del_{ex['id']}", type="primary"):
                            wl.delete_exercise(ex["id"])
                            st.success(f"A(z) '{ex['name']}' törölve lett!")
                            st.rerun()

# --- ÚJ GYAKORLAT HOZZÁADÁSA ---
with tabs["➕ Új gyakorlat hozzáadása"]:
    st.header("Új gyakorlat rögzítése")

    all_equipment = wl.get_all_equipment()
    all_types = wl.get_all_types()

    with st.form("add_exercise_form", clear_on_submit=True):
        name = st.text_input("Gyakorlat neve (pl. TRX Guggolás)")

        st.markdown("---")
        st.subheader("🛠️ Eszköz kategória")
        selected_eq = st.multiselect("Már létező eszközök kiválasztása:", options=all_equipment)
        new_eq_input = st.text_input(
            "Új eszköz(ök) hozzáadása (ha nincs a fenti listában, vesszővel elválasztva):",
            placeholder="pl. Csiga, Gumiszalag"
        )

        st.markdown("---")
        st.subheader("🎯 Típus / Izomcsoport kategória")
        selected_tp = st.multiselect("Már létező típusok kiválasztása:", options=all_types)
        new_tp_input = st.text_input(
            "Új típus(ok) hozzáadása (ha nincs a fenti listában, vesszővel elválasztva):",
            placeholder="pl. Felsőtest, Bicepsz"
        )

        st.markdown("---")
        description = st.text_area("Rövid leírás (nem kötelező)")

        submitted = st.form_submit_button("Mentés az adatbázisba", type="primary")

        if submitted:
            if not name.strip():
                st.error("A gyakorlat nevét kötelező megadni!")
            else:
                final_eq = list(selected_eq)
                if new_eq_input.strip():
                    new_eqs = [item.strip() for item in new_eq_input.split(",") if item.strip()]
                    for item in new_eqs:
                        if item not in final_eq:
                            final_eq.append(item)

                final_tp = list(selected_tp)
                if new_tp_input.strip():
                    new_tps = [item.strip() for item in new_tp_input.split(",") if item.strip()]
                    for item in new_tps:
                        if item not in final_tp:
                            final_tp.append(item)

                result = wl.add_exercise(name.strip(), final_eq, final_tp, description.strip())

                if result is None:
                    st.error(f"❌ A(z) '{name.strip()}' nevű gyakorlat már létezik az adatbázisban!")
                else:
                    st.success(f"A(z) '{name}' gyakorlat sikeresen elmentve!")
                    st.rerun()

# --- FŐ PLAYLIST ---
with tabs["🎧 Fő playlist"]:
    st.header("Fő playlist")

    if spotify_ready():
        embed_playlist(spa.MAIN_PLAYLIST_ID, version=st.session_state.get("embed_version", 0))
        st.caption(f"{len(pool)} szám a fő playlistben.")

        col_reload, col_logout = st.columns(2)
        with col_reload:
            if st.button("🔄 Frissítés", help="Lejátszó és számlista újratöltése (pl. ha új számot adtál hozzá)"):
                refresh_main_playlist()
                st.rerun()
        with col_logout:
            if st.button("🚪 Kijelentkezés"):
                for key in ["spotify_token", "pool", "recs", "draft"]:
                    st.session_state.pop(key, None)
                st.rerun()

# --- ZENEFELFEDEZÉS ---
with tabs["🔍 Zenefelfedezés"]:
    st.header("Zenefelfedezés")

    if spotify_ready():
        st.caption(
            "Hasonló számok a fő playlist alapján (Last.fm). "
            "🎧 = meghallgatás, 👍 = hozzáadás a fő playlisthez, 👎 = ne ajánlja többet."
        )
        if st.button("🔍 Ajánlások keresése", type="primary"):
            st.session_state.pop("recs", None)
            with st.spinner("Keresés (első alkalommal kb. 1 perc)..."):
                get_recommendations(sp, pool)

        for t in st.session_state.get("recs", []):
            with st.container(border=True):
                col_info, col_play, col_up, col_down = st.columns([6, 1, 1, 1])
                with col_info:
                    st.markdown(f"**{', '.join(t['artists'])} – {t['title']}**")
                    st.caption(" · ".join(t["reasons"][:3]))
                with col_play:
                    playing = preview_toggle(t["id"], key=f"prev_rec_{t['id']}")
                with col_up:
                    if st.button("👍", key=f"like_{t['id']}", help="Hozzáadás a fő playlisthez"):
                        spa.add_to_playlist(sp, [t["uri"]])
                        pool.append(t)
                        st.session_state.recs.remove(t)
                        st.session_state.embed_version = st.session_state.get("embed_version", 0) + 1
                        st.rerun()
                with col_down:
                    if st.button("👎", key=f"dislike_{t['id']}", help="Ne ajánlja többet"):
                        md.block_track(*t["lastfm"])
                        st.session_state.recs.remove(t)
                        st.rerun()
                if playing:
                    embed_track(t["id"])
