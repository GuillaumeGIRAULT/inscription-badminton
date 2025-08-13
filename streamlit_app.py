from datetime import datetime, date
from pathlib import Path
import pandas as pd
import streamlit as st
import gspread

# ------------------ Config ------------------
MAX_PLACES = 50
LABS = ["Ma1","Ma2","Bo","ÇA","IS","DE","BS","YS","CL","DA","ME","SH","AM","EU","SS","FL","QG"]
STATIC_DIR = Path("static")
IMG_FORM = STATIC_DIR / "badmington.jpg"
IMG_PLAN = STATIC_DIR / "plan.png"
IMG_ACCES = STATIC_DIR / "acces.png"

# Admin password: can be overridden via Streamlit Secrets
ADMIN_PASSWORD = st.secrets.get("admin_password", "jD9!wX4@Lm82Qz")

# Google Sheets configuration via Secrets
# In Streamlit Cloud → Settings → Secrets, define:
# [gcp_service_account]
# ... (full JSON key)
# [gsheet]
# spreadsheet_name = "Inscriptions Badminton"
# worksheet_title = "Feuille 1"
SHEET_NAME = st.secrets.get("gsheet", {}).get("spreadsheet_name", "Inscriptions Badminton")
WORKSHEET_TITLE = st.secrets.get("gsheet", {}).get("worksheet_title", None)  # default: first sheet

# Expected headers in the sheet
HEADERS = ["nom", "prenom", "email", "laboratoire", "accompagnants", "commentaire", "created_at"]

# ------------------ Google Sheets helpers ------------------
@st.cache_resource(show_spinner=False)
def get_gsheet_client():
    # Authenticate using the service account dict from secrets
    sa_dict = st.secrets["gcp_service_account"]
    gc = gspread.service_account_from_dict(sa_dict)
    return gc

@st.cache_resource(show_spinner=False)
def get_worksheet():
    gc = get_gsheet_client()
    # Open spreadsheet by name
    sh = gc.open(SHEET_NAME)
    # Pick worksheet
    if WORKSHEET_TITLE:
        ws = sh.worksheet(WORKSHEET_TITLE)
    else:
        ws = sh.sheet1
    # Ensure headers exist
    values = ws.get_all_values()
    if not values:
        ws.append_row(HEADERS)
    else:
        # If headers present but not matching, ensure at least columns exist
        if [h.strip().lower() for h in values[0]] != HEADERS:
            # Try to set the first row to our headers (non-destructive if already in place)
            ws.update('A1', [HEADERS])
    return ws

# Read entire sheet into DataFrame (excluding header row)
def gsheet_to_df(ws) -> pd.DataFrame:
    rows = ws.get_all_records()  # returns list of dicts, using first row as header
    if not rows:
        return pd.DataFrame(columns=HEADERS)
    df = pd.DataFrame(rows)
    # Normalize dtypes
    if "accompagnants" in df.columns:
        df["accompagnants"] = pd.to_numeric(df["accompagnants"], errors="coerce").fillna(0).astype(int)
    return df

def nom_prenom_deja_inscrit(ws, nom: str, prenom: str) -> bool:
    df = gsheet_to_df(ws)
    if df.empty or not {"nom", "prenom"}.issubset(df.columns):
        return False
    n = (nom or "").strip().lower()
    p = (prenom or "").strip().lower()
    return ((df["nom"].astype(str).str.strip().str.lower() == n) &
            (df["prenom"].astype(str).str.strip().str.lower() == p)).any()

# Append one inscription (values must follow HEADERS order)
def append_inscription(ws, data: dict):
    row = [data.get("nom",""), data.get("prenom",""), data.get("email",""),
           data.get("laboratoire",""), int(data.get("accompagnants",0)),
           data.get("commentaire",""), data.get("created_at","")]
    ws.append_row(row)

# ------------------ Business logic ------------------
def get_places_stats(ws):
    df = gsheet_to_df(ws)
    count_inscrits = len(df)  # one row per salarié inscrit
    sum_accomp = int(df["accompagnants"].sum()) if not df.empty else 0
    total = count_inscrits + sum_accomp
    restantes = MAX_PLACES - total
    return max(total, 0), max(restantes, 0)

# ------------------ UI ------------------
st.set_page_config(page_title="Inscription Badminton", page_icon="🏸", layout="centered")

st.title("🏸 Matinée Badminton – Inscription")

colL, colR = st.columns([2,1])
with colL:
    st.markdown(
        "> **Activité privée, hors temps de travail**  \n> Réservée au personnel des laboratoires de Rouen (accompagnants possibles, **priorité aux salariés**)."
    )
    st.write("**Lieu :** Gymnase du lycée Val de Seine, 5–11 Avenue Georges Braque, 76120 Le Grand‑Quevilly")
    st.write("**Date :** Dimanche 28/09/2025 matin")
with colR:
    if IMG_FORM.exists():
        st.image(str(IMG_FORM), use_container_width=True, caption="Affiche")

# Init worksheet resource once
try:
    WS = get_worksheet()
except Exception as e:
    st.error("Impossible d'accéder à Google Sheets. Vérifie les *secrets* et les droits de partage de la feuille avec le compte de service.")
    st.exception(e)
    st.stop()

tab_inscription, tab_admin = st.tabs(["📝 S'inscrire", "🔐 Admin"])

with tab_inscription:
    # Auth simple pour l'inscription
    if "inscription_ok" not in st.session_state:
        st.session_state.inscription_ok = False

    if not st.session_state.inscription_ok:
        with st.form("login_inscription", border=True):
            pwd_insc = st.text_input("Mot de passe pour accéder à l'inscription", type="password")
            ok_insc = st.form_submit_button("Valider")
        if ok_insc:
            if pwd_insc == "LaboratoireBIOLBS2025":
                st.session_state.inscription_ok = True
                st.rerun()
            else:
                st.error("Mot de passe incorrect.")
        st.stop()
    total, restantes = get_places_stats(WS)
    st.markdown(f"**Places restantes : {restantes}**  _(capacité totale {MAX_PLACES})_")
    pct = int(100 * (MAX_PLACES - restantes) / MAX_PLACES)
    st.progress(pct, text=f"{MAX_PLACES - restantes}/{MAX_PLACES} places prises – {restantes} restantes")

    # Ouverture des accompagnants à partir du 01/09/2025
    OPEN_DATE = date(2025, 9, 1)
    today = date.today()
    accomp_open = today >= OPEN_DATE
    if not accomp_open:
        st.info("ℹ️ Les accompagnants seront **ouverts à partir du 01/09/2025**. Les salariés peuvent s’inscrire dès maintenant.")

    if restantes <= 0:
        st.error("Complet – il n'y a plus de places disponibles.")
        st.stop()

    with st.form("form_inscription", border=True):
        col1, col2 = st.columns(2)
        with col1:
            nom = st.text_input("Nom *", value="", placeholder="Dupont")
            email = st.text_input("Email *", value="", placeholder="prenom.nom@exemple.com")
        with col2:
            prenom = st.text_input("Prénom*", value="")
            laboratoire = st.selectbox("Laboratoire*", LABS, index=0)

        # Priorité aux salariés : accompagnants ouverts seulement à partir du 01/09/2025
        if accomp_open:
            max_accomp = max(restantes - 1, 0)
            accompagnants = st.number_input(
                "Accompagnants (optionnel)",
                min_value=0, max_value=int(max_accomp), value=0, step=1,
                help="Priorité aux salariés : les accompagnants sont limités selon les places restantes."
            )
        else:
            accompagnants = 0  # champ caché/forcé à 0 avant ouverture

        commentaire = st.text_area("Commentaire", value="", height=80, placeholder="Allergies, niveau débutant, préférences…")
        submitted = st.form_submit_button("S'inscrire")

        if submitted:
            if not nom.strip() or not prenom.strip() or not email.strip():
                st.warning("Merci de remplir tous les champs obligatoires (*).")
                st.stop()

            # Blocage des doublons par Nom + Prénom
            if nom_prenom_deja_inscrit(WS, nom, prenom):
                st.warning("Cette personne est déjà inscrite. Si vous devez modifier votre inscription, contactez l’organisateur.")
                st.stop()

            # Recalcul juste avant écriture pour éviter contention
            _, r = get_places_stats(WS)
            if r <= 0:
                st.error("Désolé, c'est complet maintenant.")
                st.stop()

            max_accomp_now = max(r - 1, 0)
            accomp_enregistre = min(accompagnants, max_accomp_now)

            data = {
                "nom": nom.strip(),
                "prenom": prenom.strip(),
                "email": email.strip(),
                "laboratoire": laboratoire,
                "accompagnants": int(accomp_enregistre),
                "commentaire": commentaire.strip(),
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            try:
                append_inscription(WS, data)
                if accomp_enregistre < accompagnants:
                    st.info(f"Inscription enregistrée. Les accompagnants ont été ajustés à {accomp_enregistre} en fonction des places restantes (priorité aux salariés).")
                else:
                    st.success("Inscription enregistrée. À bientôt sur le terrain !")
                st.toast("Inscription confirmée ✅")
                st.balloons()
            except Exception as e:
                st.error("Échec de l'enregistrement dans Google Sheets. Vérifie les droits/quotas.")
                st.exception(e)

    with st.expander("🗺️ Plan & Accès"):
        if IMG_PLAN.exists():
            st.image(str(IMG_PLAN), caption="Plan", use_container_width=True)
        if IMG_ACCES.exists():
            st.image(str(IMG_ACCES), caption="Accès", use_container_width=True)
        st.link_button("Ouvrir l’itinéraire (Google Maps)", "https://maps.google.com/?q=5-11+Avenue+Georges+Braque+76120")

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
        df = gsheet_to_df(WS)
        total, restantes = get_places_stats(WS)
        k1, k2, k3 = st.columns(3)
        k1.metric("Capacité", MAX_PLACES)
        k2.metric("Places prises", MAX_PLACES - restantes)
        k3.metric("Restantes", restantes)

        lab_filter = st.multiselect("Filtrer par laboratoire", LABS, [])
        if lab_filter and not df.empty:
            df = df[df["laboratoire"].isin(lab_filter)]

        # --- Analytics par laboratoire ---
        if df.empty:
            st.info("Aucune inscription pour le moment.")
        else:
            # Calcul par labo
            agg = (
                df.groupby("laboratoire", dropna=False)
                  .agg(inscrits=("laboratoire", "size"), accompagnants=("accompagnants", "sum"))
                  .reset_index()
            )
            agg["inscrits"] = agg["inscrits"].fillna(0).astype(int)
            agg["accompagnants"] = agg["accompagnants"].fillna(0).astype(int)
            agg["total"] = agg["inscrits"] + agg["accompagnants"]

            # S'assurer que tous les LABS apparaissent, même à 0
            full = pd.DataFrame({"laboratoire": LABS})
            agg = full.merge(agg, on="laboratoire", how="left").fillna(0)
            for col in ["inscrits", "accompagnants", "total"]:
                agg[col] = agg[col].astype(int)

            st.subheader("Répartition par laboratoire")
            metric = st.radio("Choisir l'indicateur à afficher", ["inscrits", "accompagnants", "total"], index=2, horizontal=True)
            chart_df = agg.set_index("laboratoire")[[metric]]
            st.bar_chart(chart_df)

            with st.expander("Détails par laboratoire"):
                st.dataframe(agg.rename(columns={"inscrits":"Inscrits","accompagnants":"Accompagnants","total":"Total (avec accompagnants)"}), use_container_width=True, hide_index=True)

        st.dataframe(df, use_container_width=True, hide_index=True)

        # Export CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Exporter en CSV", data=csv, file_name="inscriptions.csv", mime="text/csv")

        if st.button("Se déconnecter"):
            st.session_state.admin_ok = False
            st.rerun()
