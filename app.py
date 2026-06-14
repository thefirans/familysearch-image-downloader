from __future__ import annotations

import base64
import json
import tempfile
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from downloader import DownloadError, download_document


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
st.info(
    "Before downloading, sign in to FamilySearch in Chrome, Chrome Canary, "
    "Microsoft Edge, or Brave on this computer."
)

with st.form("download", clear_on_submit=False):
    document_url = st.text_input(
        "Document URL",
        placeholder="https://www.familysearch.org/ark:/61903/3:1:...?i=...",
    )
    submitted = st.form_submit_button(
        "Download JPEG",
        type="primary",
        width="stretch",
    )


def trigger_download(data: bytes, filename: str) -> None:
    encoded = base64.b64encode(data).decode("ascii")
    safe_filename = json.dumps(filename)
    components.html(
        f"""
        <script>
        const binary = atob({json.dumps(encoded)});
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i += 1) {{
          bytes[i] = binary.charCodeAt(i);
        }}
        const url = URL.createObjectURL(new Blob([bytes], {{type: 'image/jpeg'}}));
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = {safe_filename};
        document.documentElement.appendChild(anchor);
        anchor.click();
        anchor.remove();
        setTimeout(() => URL.revokeObjectURL(url), 10000);
        </script>
        """,
        height=0,
    )


if submitted:
    st.session_state.pop("last_result", None)
    if not document_url.strip():
        st.warning("Paste a FamilySearch document URL.")
    else:
        progress_bar = st.progress(0.0)
        status = st.empty()

        def update_progress(value: float, message: str) -> None:
            progress_bar.progress(value)
            status.write(message)

        try:
            result = download_document(
                document_url,
                DOWNLOAD_DIR,
                jpeg_quality=95,
                workers=12,
                progress=update_progress,
            )
        except DownloadError as error:
            progress_bar.empty()
            status.empty()
            st.error(str(error))
        except Exception:
            progress_bar.empty()
            status.empty()
            st.error("The download failed. Please try again.")
        else:
            image_bytes = result.path.read_bytes()
            st.session_state["last_result"] = {
                "bytes": image_bytes,
                "name": result.path.name,
                "width": result.width,
                "height": result.height,
            }
            progress_bar.progress(1.0)
            status.success("Download ready")
            trigger_download(image_bytes, result.path.name)

if "last_result" in st.session_state:
    result = st.session_state["last_result"]
    st.image(result["bytes"], width="stretch")
    st.caption(f'{result["width"]} x {result["height"]} px')
    st.download_button(
        "Download JPEG again",
        data=result["bytes"],
        file_name=result["name"],
        mime="image/jpeg",
        width="stretch",
    )
