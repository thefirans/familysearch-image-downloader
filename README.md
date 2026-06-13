# FamilySearch Image Downloader

A Streamlit application that downloads FamilySearch DeepZoom tiles and assembles
an entire document image into a single JPEG file.

## Deploy on Streamlit Community Cloud

1. Open [share.streamlit.io](https://share.streamlit.io/).
2. Select **Create app** and choose this GitHub repository.
3. Select the `main` branch and set the entrypoint to `app.py`.
4. Select **Deploy**. No system packages or Streamlit secrets are required.

Select `Cookie header` when running in the cloud. To obtain the header:

1. Open the required FamilySearch document in Chrome and sign in.
2. Open DevTools (`Cmd+Option+I`) and select the **Network** tab.
3. Refresh the page and select a request containing `image_files`.
4. In **Request Headers**, copy the value of the `Cookie` header.
5. Paste that value into the application's password-protected input.

The Cookie header is kept only in memory for the current Streamlit session. It
is not written to files, logs, or GitHub. Deploy the application as a private app
and do not share your Cookie header with anyone.

## Run locally on macOS

When running locally, the application can automatically use an active
FamilySearch session from Chrome, Chrome Canary, Edge, or Brave.

```bash
./run.command
```

Open [http://127.0.0.1:8501](http://127.0.0.1:8501) after the server starts.

## Authentication limitation

Streamlit Community Cloud cannot read cookies from a user's local browser because
the application runs on a remote server and under a different domain. An official
FamilySearch integration requires a registered OAuth application key, a redirect
URI, and production approval. FamilySearch also restricts third-party access to
historical record images, so the cloud mode uses the user's temporary web session.

Official documentation:

- [FamilySearch Authentication](https://developers.familysearch.org/main/docs/authentication)
- [FamilySearch Getting Started](https://developers.familysearch.org/main/docs/getting-started)
- [Streamlit Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
