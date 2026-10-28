import streamlit as st
from pathlib import Path

from src.auth.ui import entry_principal

PAGES = Path(__file__).resolve().parent / "pages"

def main():
    st.set_page_config(page_title="BMT Lubuk Malako BI System", layout="wide", initial_sidebar_state="expanded")
    # The public shell is styled before authentication I/O or sidebar markup.
    from src.ui.executive import load_styles
    load_styles()
    principal = entry_principal()
    if principal is None:
        return
    pages = {}
    if "admin" in principal.roles:
        pages["Admin"] = [
            st.Page(PAGES / "admin_upload.py", title="Unggah & validasi", url_path="admin-validasi", default=True),
            st.Page(PAGES / "admin_history.py", title="Riwayat unggahan", url_path="admin-riwayat"),
        ]
    if "executive" in principal.roles:
        pages["Pimpinan"] = [st.Page(PAGES / "executive_home.py", title="Beranda",
                                     url_path="pimpinan", default="admin" not in principal.roles),
                               st.Page(PAGES / "executive_quality.py", title="Kualitas Portofolio",
                                       url_path="kualitas-portofolio"),
                               st.Page(PAGES / "executive_monitoring.py", title="Pemantauan & Prioritas",
                                       url_path="pemantauan"),
                               st.Page(PAGES / "executive_concentration.py", title="Konsentrasi Portofolio",
                                       url_path="konsentrasi"),
                               st.Page(PAGES / "executive_marketing.py", title="Portofolio Marketing",
                                       url_path="portofolio-marketing"),
                               st.Page(PAGES / "executive_historical.py",title="Analisis Historis",url_path="analisis-historis"),
                               st.Page(PAGES / "executive_simulation.py",title="Simulasi Jadwal",url_path="simulasi-jadwal"),
                               st.Page(PAGES / "executive_history_trends.py",title="Riwayat & Tren",url_path="riwayat-tren"),
                               st.Page(PAGES / "executive_methodology.py",title="Model & Metodologi",url_path="model-metodologi")]
    navigation = st.navigation(pages, position="hidden")
    if "executive" in principal.roles:
        from src.ui.executive import executive_sidebar
        from src.auth.ui import _logout
        from src.database.read_session import read_session
        from src.ui.page_runtime import loading_frame
        from src.ui.motion import load_motion
        executive_titles={page.title for page in pages['Pimpinan']}
        if navigation.title in executive_titles:
            load_motion(navigation.title,navigation.url_path)
            with read_session(),loading_frame(navigation.title,navigation.url_path):
                executive_sidebar(principal, _logout,active_title=navigation.title)
                navigation.run()
            return
    if 'admin' in principal.roles:
        from src.ui.admin import admin_sidebar
        from src.auth.ui import _logout
        admin_sidebar(principal,_logout,active_title=navigation.title)
    navigation.run()

if __name__ == "__main__":
    main()
