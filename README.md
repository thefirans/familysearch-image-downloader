# FamilySearch Image Downloader

A Streamlit application that downloads FamilySearch DeepZoom tiles and assembles
an entire document image into a single JPEG file.

## Run locally on macOS

The application automatically uses an active FamilySearch session from Chrome,
Chrome Canary, Edge, or Brave. The interface only requires a document URL.

```bash
./run.command
```

Open [http://127.0.0.1:8501](http://127.0.0.1:8501) after the server starts.

Workflow:

1. Paste a FamilySearch document URL.
2. Select **Download JPEG**.
3. The assembled JPEG downloads automatically.

## Authentication limitation

The zero-configuration workflow is local by design. A hosted server cannot read
an authenticated session from a user's local browser. An official hosted
integration requires a registered FamilySearch OAuth application key, a redirect
URI, production approval, and sufficient image-access permissions.

Official documentation:

- [FamilySearch Authentication](https://developers.familysearch.org/main/docs/authentication)
- [FamilySearch Getting Started](https://developers.familysearch.org/main/docs/getting-started)
- [Streamlit Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
