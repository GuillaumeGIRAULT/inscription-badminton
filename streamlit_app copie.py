# streamlit_app.py
import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st
from pathlib import Path

DB_FILE = "inscriptions.db"
MAX_PLACES = 50

LABS = ["Ma1","Ma2","BO","CA","IS","DE","BS","YS","CL","DA","ME","SH","AM","EU","SS","FL","GQ"]
STATIC_DIR = Path("static")
IMG_FORM = STATIC_DIR / "badmington.jpg"
IMG_PLAN = STATIC_DIR / "plan.png"
IMG_ACCES = STATIC_DIR / "acces.png"

ADMIN_PASSWORD = "admin123"  # à changer

# ------------------ DB ------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS inscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            email TEXT NOT NULL,
            laboratoire TEXT,
            accompagnants INTEGER,
            commentaire TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_places_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*), COALESCE(SUM(accompagnants),0) FROM inscriptions")
    count_inscrits, sum_accomp = c.fetchone()
    conn.close()
    total = (count_inscrits or 0) + (sum_accomp or 0)
    restantes = MAX_PLACES - total
    return max(total, 0), max(restantes, 0)

def insert_inscription(nom, prenom, email, laboratoire, accompagnants, commentaire):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO inscriptions (nom, prenom, email, laboratoire, accompagnants, commentaire, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (nom, prenom, email, laboratoire, accompagnants, commentaire, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()

def fetch_all():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT id, nom, prenom, email, laboratoire, accompagnants, commentaire, created_at "
        "FROM inscriptions ORDER BY id DESC",
        conn
    )
    conn.close()
    return df

# ------------------ UI ------------------
init_db()
st.set_page_config(page_title="Inscription Badminton", page_icon="🏸", layout="centered")

st.title("🏸 Matinée Badminton – Inscription")
st.caption("Activité privée, hors temps de travail. Réservée au personnel des laboratoires de Rouen (accompagnants possibles, priorité aux salariés).")

with st.container(border=True):
    st.subheader("Infos pratiques")
    st.write("**Lieu :** Gymnase du lycée Val de Seine, 5–11 Avenue Georges Braque, 76120 Le Grand‑Quevilly")
    st.write("**Date :** Dimanche 28/09/2025 matin")

tab_inscription, tab_admin = st.tabs(["📝 S'inscrire", "🔐 Admin"])

with tab_inscription:
    total, restantes = get_places_stats()
    st.markdown(f"**Places restantes : {restantes}**  _(capacité totale {MAX_PLACES})_")

    if IMG_FORM.exists():
        st.image(str(IMG_FORM), use_container_width=False, caption="Affiche")

    if restantes <= 0:
        st.error("Complet – il n'y a plus de places disponibles.")
        st.stop()

    with st.form("form_inscription", border=True):
        col1, col2 = st.columns(2)
        with col1:
            nom = st.text_input("Nom*", value="")
            email = st.text_input("Email*", value="")
        with col2:
            prenom = st.text_input("Prénom*", value="")
            laboratoire = st.selectbox("Laboratoire*", LABS, index=0)

        # Priorité aux salariés : on garde au moins 1 place pour la personne,
        # donc on limite le nombre d'accompagnants au reste.
        max_accomp = max(restantes - 1, 0)
        accompagnants = st.number_input(
            "Nombre d'accompagnants (optionnel, priorité aux salariés)",
            min_value=0, max_value=int(max_accomp), value=0, step=1
        )

        commentaire = st.text_area("Commentaire", value="", height=80)
        submitted = st.form_submit_button("S'inscrire")

        if submitted:
            if not nom.strip() or not prenom.strip() or not email.strip():
                st.warning("Merci de remplir tous les champs obligatoires (*).")
                st.stop()

            # recalculer juste avant d’enregistrer pour éviter la course
            _, r = get_places_stats()
            if r <= 0:
                st.error("Désolé, c'est complet maintenant.")
                st.stop()

            max_accomp_now = max(r - 1, 0)
            accomp_enregistre = min(accompagnants, max_accomp_now)

            insert_inscription(nom.strip(), prenom.strip(), email.strip(), laboratoire, int(accomp_enregistre), commentaire.strip())
            if accomp_enregistre < accompagnants:
                st.info(f"Inscription enregistrée. Les accompagnants ont été ajustés à {accomp_enregistre} en fonction des places restantes (priorité aux salariés).")
            else:
                st.success("Inscription enregistrée. À bientôt sur le terrain !")

    # Images plan / accès sous le formulaire
    if IMG_PLAN.exists():
        st.image(str(IMG_PLAN), caption="Plan", use_container_width=True)
    if IMG_ACCES.exists():
        st.image(str(IMG_ACCES), caption="Accès", use_container_width=True)

with tab_admin:
    # Auth simple
    if "admin_ok" not in st.session_state:
        st.session_state.admin_ok = False

    if not st.session_state.admin_ok:
        with st.form("login_admin", border=True):
            pwd = st.text_input("Mot de passe admin", type="password")
            ok = st.form_submit_button("Se connecter")
        if ok:
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_ok = True
                st.rerun()
            else:
                st.error("Mot de passe incorrect.")
    else:
        df = fetch_all()
        total, restantes = get_places_stats()
        st.write(f"**Capacité :** {MAX_PLACES} — **Inscrits (avec accompagnants) :** {MAX_PLACES - restantes} — **Restantes :** {restantes}")
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Export CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Exporter en CSV", data=csv, file_name="inscriptions.csv", mime="text/csv")

        if st.button("Se déconnecter"):
            st.session_state.admin_ok = False
            st.rerun()