import streamlit as st
import random
import workout_logic as wl

# Mintaadatok inicializálása, ha üres a fájl
wl.init_sample_data()

st.set_page_config(page_title="Köredzés Generáló", page_icon="🏋️‍♂️", layout="centered")

st.title("🏋️‍♂️ Köredzés Generáló App")

# Lapfülek létrehozása
tab1, tab2, tab3 = st.tabs([
    "🎲 Edzés generálása", 
    "📋 Gyakorlatok listája", 
    "➕ Új gyakorlat hozzáadása"
])

# --- 1. TAB: EDZÉS GENERÁLÁSA ÉS SZERKESZTÉSE ---
with tab1:
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

# --- 2. TAB: GYAKORLATOK LISTÁZÁSA, SZERKESZTÉSE ÉS TÖRLESE ---
with tab2:
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

# --- 3. TAB: ÚJ GYAKORLAT HOZZÁADÁSA ---
with tab3:
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