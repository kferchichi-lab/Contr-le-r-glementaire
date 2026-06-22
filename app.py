import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO

# Configuration de la page
st.set_page_config(page_title="Gestion de Conformité Réglementaire", layout="wide")

# --- INITIALISATION DE LA BASE DE DONNÉES ---
def init_db():
    conn = sqlite3.connect('conformite.db')
    c = conn.cursor()
    # Table des rapports
    c.execute('''CREATE TABLE IF NOT EXISTS rapports 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, equipement TEXT, date_installation DATE, date_controle DATE, nom_fichier TEXT, fichier BLOB)''')
    # Table de planification
    c.execute('''CREATE TABLE IF NOT EXISTS planification 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, equipement TEXT, prochain_controle DATE, responsable TEXT, contrat TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- FONCTIONS DE GESTION DE LA DB ---
def ajouter_rapport(equipement, date_inst, date_ctrl, nom_f, octets_f):
    conn = sqlite3.connect('conformite.db')
    c = conn.cursor()
    c.execute("INSERT INTO rapports (equipement, date_installation, date_controle, nom_fichier, fichier) VALUES (?, ?, ?, ?, ?)",
              (equipement, date_inst, date_ctrl, nom_f, octets_f))
    conn.commit()
    conn.close()

def ajouter_planification(equipement, date_prox, resp, contrat):
    conn = sqlite3.connect('conformite.db')
    c = conn.cursor()
    c.execute("INSERT INTO planification (equipement, prochain_controle, responsable, contrat) VALUES (?, ?, ?, ?)",
              (equipement, date_prox, resp, contrat))
    conn.commit()
    conn.close()

def charger_rapports():
    conn = sqlite3.connect('conformite.db')
    df = pd.read_sql_query("SELECT id, equipement, date_installation, date_controle, nom_fichier FROM rapports", conn)
    conn.close()
    return df

def charger_planification():
    conn = sqlite3.connect('conformite.db')
    df = pd.read_sql_query("SELECT * FROM planification", conn)
    conn.close()
    return df

# --- AUTHENTIFICATION SIMPLIFIÉE (Système de Rôles) ---
st.sidebar.title("🔐 Connexion")
role = st.sidebar.selectbox("Choisissez votre profil :", ["Visiteur (Lecture seule)", "Administrateur (Modification)"])

est_admin = False
if role == "Administrateur (Modification)":
    mot_de_passe = st.sidebar.text_input("Mot de passe :", type="password")
    if mot_de_passe == "admin123":  # Changez ce mot de passe
        st.sidebar.success("Accès Administrateur Activé")
        est_admin = True
    elif mot_de_passe != "":
        st.sidebar.error("Mot de passe incorrect")

# --- TITRE PRINCIPAL ---
st.title("📋 Plateforme de Contrôle Réglementaire & Conformité")
st.write("Scannez le code QR pour accéder directement aux documents et planning de l'établissement.")

# --- CRÉATION DES ONGLETS ---
onglet1, onglet2, onglet3 = st.tabs(["📂 Gestion des Rapports", "📅 Maîtrise & Planification", "📱 Générateur QR Code"])

# ==========================================
# PARTIE 1 : GESTION DES RAPPORTS
# ==========================================
with onglet1:
    st.header("Historique des rapports de contrôle")
    
    # Zone d'ajout pour l'administrateur
    if est_admin:
        with st.expander("➕ Ajouter un nouveau rapport (Admin)"):
            with st.form("form_rapport", clear_on_submit=True):
                eq = st.text_input("Nom de l'équipement :")
                d_inst = st.date_input("Date d'installation :")
                d_ctrl = st.date_input("Date du contrôle réglementaire :")
                fichier_uploade = st.file_uploader("Téléverser le rapport (PDF)", type=["pdf"])
                soumettre = st.form_submit_button("Enregistrer le rapport")
                
                if soumettre and fichier_uploade and eq:
                    ajouter_rapport(eq, d_inst, d_ctrl, fichier_uploade.name, fichier_uploade.read())
                    st.success(f"Rapport pour {eq} ajouté avec succès !")

    # Filtres de recherche
    st.subheader("🔍 Filtres de recherche")
    col1, col2 = st.columns(2)
    df_rapp = charger_rapports()
    
    if not df_rapp.empty:
        with col1:
            liste_eq = ["Tous"] + list(df_rapp['equipement'].unique())
            filtre_eq = st.selectbox("Filtrer par équipement :", liste_eq)
        with col2:
            filtre_date = st.date_input("Filtrer par date d'installation après le :", value=datetime(2020, 1, 1))
        
        # Application des filtres
        df_filtre = df_rapp.copy()
        df_filtre['date_installation'] = pd.to_datetime(df_filtre['date_installation']).dt.date
        if filtre_eq != "Tous":
            df_filtre = df_filtre[df_filtre['equipement'] == filtre_eq]
        df_filtre = df_filtre[df_filtre['date_installation'] >= filtre_date]
        
        # Affichage du tableau des rapports
        st.write(f"**{len(df_filtre)} rapport(s) trouvé(s) :**")
        for idx, row in df_filtre.iterrows():
            with st.container():
                col_info, col_dl = st.columns([3, 1])
                col_info.write(f"🛠️ **{row['equipement']}** | Installé le : {row['date_installation']} | Contrôlé le : {row['date_controle']}")
                
                # Récupération du fichier binaire pour le téléchargement
                conn = sqlite3.connect('conformite.db')
                c = conn.cursor()
                c.execute("SELECT fichier FROM rapports WHERE id=?", (row['id'],))
                blob_fichier = c.fetchone()[0]
                conn.close()
                
                col_dl.download_button(
                    label="📥 Télécharger / Imprimer",
                    data=blob_fichier,
                    file_name=row['nom_fichier'],
                    mime="application/pdf",
                    key=f"dl_{row['id']}"
                )
                st.markdown("---")
    else:
        st.info("Aucun rapport disponible pour le moment.")

# ==========================================
# PARTIE 2 : MAÎTRISE & PLANIFICATION
# ==========================================
with onglet2:
    st.header("Suivi du Planning & Responsabilités")
    
    if est_admin:
        with st.expander("➕ Planifier un prochain contrôle (Admin)"):
            with st.form("form_planif", clear_on_submit=True):
                eq_p = st.text_input("Nom de l'équipement à contrôler :")
                d_prox = st.date_input("Date du prochain contrôle :")
                resp = st.text_input("Responsable / Prestataire en charge :")
                contrat = st.selectbox("Statut du contrat de conformité :", ["Sous contrat (Actif)", "Hors contrat", "À renouveler"])
                soumettre_p = st.form_submit_button("Planifier")
                
                if soumettre_p and eq_p:
                    ajouter_planification(eq_p, d_prox, resp, contrat)
                    st.success(f"Planification enregistrée pour {eq_p}.")

    # Affichage du tableau de bord
    df_plan = charger_planification()
    if not df_plan.empty:
        st.subheader("🗓️ Tableau de bord de suivi")
        
        # Coloration des alertes visuelles simples
        df_plan['prochain_controle'] = pd.to_datetime(df_plan['prochain_controle']).dt.date
        st.dataframe(df_plan[["equipement", "prochain_controle", "responsable", "contrat"]], use_container_width=True)
    else:
        st.info("Aucune planification enregistrée.")

# ==========================================
# PARTIE 3 : GÉNÉRATEUR DE CODE QR
# ==========================================
with onglet3:
    st.header("Générer le Code QR d'accès")
    st.write("Entrez l'URL finale de votre application une fois déployée pour générer le code QR à coller sur vos machines.")
    
    url_app = st.text_input("URL de la plateforme :", value="https://share.streamlit.io/votre-compte/votre-app")
    
    if st.button("Générer le Code QR"):
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url_app)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buf = BytesIO()
        img.save(buf, format="PNG")
        byte_im = buf.getvalue()
        
        st.image(byte_im, caption="Code QR prêt à être scanné", width=250)
        st.download_button(label="💾 Télécharger l'image du QR Code", data=byte_im, file_name="qr_code_plateforme.png", mime="image/png")
