import streamlit as st
import workout_logic as wl

# Oldal beállításai
st.set_page_config(page_title="Köredzés Generáló", page_icon="🏋️‍♂️", layout="centered")

st.title("🏋️‍♂️ Köredzés Generáló App")

# Lapfülek létrehozása a felületen
tab1, tab2 = st.tabs(["📋 Gyakorlatok listája", "➕ Új gyakorlat hozzáadása"])

# --- 1. TAB: GYAKORLATOK LISTÁZÁSA ---
with tab1:
    st.header("Meglévő gyakorlatok")
    exercises = wl.load_exercises()
    
    if not exercises:
        st.info("Még nincsenek gyakorlatok az adatbázisban.")
    else:
        for ex in exercises:
            # Összecsukható kártyák a gyakorlatoknak
            cats = ", ".join(ex.get("categories", []))
            with st.expander(f"**{ex['name']}**  *(Kategóriák: {cats})*"):
                st.write(f"**Leírás:** {ex.get('description', 'Nincs leírás megadva.')}")

# --- 2. TAB: ÚJ GYAKORLAT HOZZÁADÁSA ---
with tab2:
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
                # Kategóriák feldolgozása listává
                categories = [c.strip() for c in categories_str.split(",") if c.strip()]
                
                wl.add_exercise(name.strip(), categories, description.strip())
                st.success(f"A(z) '{name}' gyakorlat sikeresen elmentve!")
                st.rerun()  # Újratölti az oldalt, hogy az új elem azonnal látszódjon