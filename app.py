import streamlit as st
import workout_logic as wl

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
    
    all_categories = wl.get_all_categories()
    
    col_cat, col_num = st.columns([2, 1])
    with col_cat:
        selected_cats = st.multiselect(
            "Szűrés kategóriák szerint (ha üres = mind):", 
            options=all_categories
        )
    with col_num:
        exercise_count = st.number_input(
            "Gyakorlatok száma:", 
            min_value=1, 
            max_value=20, 
            value=5
        )
    
    if st.button("🚀 Edzés Generálása", type="primary"):
        workout = wl.generate_workout(selected_cats, exercise_count)
        if not workout:
            st.warning("Nem található a feltételeknek megfelelő gyakorlat az adatbázisban.")
        else:
            # Mentsük el a munkamenetbe (session_state), hogy az gombnyomásokra ne tűnjön el
            st.session_state.current_workout = workout
            st.session_state.last_selected_cats = selected_cats

    # Ha van generált edzés, megjelenítjük és szerkeszthetővé tesszük
    if "current_workout" in st.session_state and st.session_state.current_workout:
        st.divider()
        st.subheader("🏋️ A generált köredzésed:")
        
        workout = st.session_state.current_workout
        cats_used = st.session_state.get("last_selected_cats", [])

        for i, ex in enumerate(workout):
            with st.container():
                c_info, c_up, c_down, c_swap = st.columns([5, 1, 1, 2])
                
                with c_info:
                    cats_str = ", ".join(ex.get("categories", []))
                    st.markdown(f"**{i+1}. {ex['name']}** `[{cats_str}]`")
                    if ex.get("description"):
                        st.caption(ex["description"])
                
                # Fel mozgatás
                with c_up:
                    if i > 0:
                        if st.button("⬆️", key=f"up_{i}_{ex['id']}"):
                            workout[i], workout[i-1] = workout[i-1], workout[i]
                            st.session_state.current_workout = workout
                            st.rerun()
                            
                # Le mozgatás
                with c_down:
                    if i < len(workout) - 1:
                        if st.button("⬇️", key=f"down_{i}_{ex['id']}"):
                            workout[i], workout[i+1] = workout[i+1], workout[i]
                            st.session_state.current_workout = workout
                            st.rerun()
                            
                # Csere egy másik gyakorlatra
                with c_swap:
                    if st.button("🔄 Csere", key=f"swap_{i}_{ex['id']}"):
                        replacement = wl.get_replacement_exercise(workout, cats_used)
                        if replacement:
                            workout[i] = replacement
                            st.session_state.current_workout = workout
                            st.rerun()
                        else:
                            st.error("Nincs több elérhető gyakorlat!")

# --- 2. TAB: GYAKORLATOK LISTÁZÁSA ---
with tab2:
    st.header("Meglévő gyakorlatok")
    exercises = wl.load_exercises()
    
    if not exercises:
        st.info("Még nincsenek gyakorlatok az adatbázisban.")
    else:
        for ex in exercises:
            cats = ", ".join(ex.get("categories", []))
            with st.expander(f"**{ex['name']}**  *(Kategóriák: {cats})*"):
                st.write(f"**Leírás:** {ex.get('description', 'Nincs leírás megadva.')}")

# --- 3. TAB: ÚJ GYAKORLAT HOZZÁADÁSA ---
with tab3:
    st.header("Új gyakorlat rögzítése")
    
    with st.form("add_exercise_form", clear_on_submit=True):
        name = st.text_input("Gyakorlat neve (pl. Fekvenyomás)")
        description = st.text_area("Rövid leírás (nem kötelező)")
        categories_str = st.text_input(
            "Kategóriák (vesszővel elválasztva)", 
            placeholder="pl. Mell, Kar, Súlyzós"
        )
        
        submitted = st.form_submit_button("Mentés az adatbázisba")
        
        if submitted:
            if not name.strip():
                st.error("A gyakorlat nevét kötelező megadni!")
            else:
                categories = [c.strip() for c in categories_str.split(",") if c.strip()]
                wl.add_exercise(name.strip(), categories, description.strip())
                st.success(f"A(z) '{name}' gyakorlat sikeresen elmentve!")
                st.rerun()