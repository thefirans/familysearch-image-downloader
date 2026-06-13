from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import streamlit as st

from downloader import DownloadError, discover_browser_profiles, download_document


APP_DIR = Path(__file__).resolve().parent
if "session_id" not in st.session_state:
    st.session_state["session_id"] = uuid.uuid4().hex
DOWNLOAD_DIR = (
    Path(tempfile.gettempdir())
    / "familysearch-image-downloader"
    / st.session_state["session_id"]
)

st.set_page_config(
    page_title="FamilySearch Image Downloader",
    layout="centered",
)

st.title("FamilySearch Image Downloader")

profiles = discover_browser_profiles()
profile_labels = [profile.label for profile in profiles]

if profiles:
    auth_mode = st.radio(
        "Авторизация",
        ["Локальный браузер", "Cookie header"],
        horizontal=True,
    )
else:
    auth_mode = "Cookie header"

cookie_header = ""
selected_profile = "Автоматически"

if auth_mode == "Cookie header":
    cookie_header = st.text_input(
        "Cookie header FamilySearch",
        type="password",
        placeholder="fssessionid=...; cf_clearance=...; ...",
        help=(
            "Откройте документ FamilySearch, DevTools > Network, обновите страницу, "
            "выберите запрос image_files и скопируйте значение Request Header 'Cookie'. "
            "Значение хранится только в памяти текущей сессии."
        ),
    )

with st.expander("Настройки", expanded=False):
    if auth_mode == "Локальный браузер":
        selected_profile = st.selectbox(
            "Профиль браузера",
            ["Автоматически", *profile_labels],
            help="В выбранном профиле должен быть выполнен вход на FamilySearch.",
        )
    jpeg_quality = st.slider("Качество JPEG", 80, 100, 95)
    workers = st.slider("Параллельные загрузки", 2, 16, 10)

url = st.text_input(
    "Ссылка на документ",
    placeholder="https://www.familysearch.org/ark:/61903/3:1:...?i=...",
)

if st.button("Скачать и склеить", type="primary", width="stretch"):
    if not url.strip():
        st.warning("Вставьте ссылку FamilySearch.")
    elif auth_mode == "Cookie header" and not cookie_header.strip():
        st.warning("Вставьте Cookie header FamilySearch.")
    else:
        progress_bar = st.progress(0.0)
        status = st.empty()

        def update_progress(value: float, message: str) -> None:
            progress_bar.progress(value)
            status.write(message)

        try:
            result = download_document(
                url,
                DOWNLOAD_DIR,
                preferred_profile=None if selected_profile == "Автоматически" else selected_profile,
                cookie_header=cookie_header if auth_mode == "Cookie header" else None,
                jpeg_quality=jpeg_quality,
                workers=workers,
                progress=update_progress,
            )
        except DownloadError as error:
            status.empty()
            progress_bar.empty()
            st.error(str(error))
        except Exception as error:
            status.empty()
            progress_bar.empty()
            st.error(f"Неожиданная ошибка: {error}")
        else:
            image_bytes = result.path.read_bytes()
            st.session_state["last_result"] = {
                "bytes": image_bytes,
                "name": result.path.name,
                "width": result.width,
                "height": result.height,
                "tiles": result.columns * result.rows,
                "profile": result.browser_profile,
            }
            status.success("Документ готов")

if "last_result" in st.session_state:
    result = st.session_state["last_result"]
    st.image(result["bytes"], caption=result["name"], width="stretch")
    st.caption(
        f'{result["width"]} x {result["height"]} px · '
        f'{result["tiles"]} плиток · {result["profile"]}'
    )
    st.download_button(
        "Скачать JPEG",
        data=result["bytes"],
        file_name=result["name"],
        mime="image/jpeg",
        type="primary",
        width="stretch",
    )
