# FamilySearch Image Downloader

Streamlit-приложение для загрузки DeepZoom-плиток FamilySearch и сборки полного
документа в один JPEG-файл.

## Streamlit Community Cloud

1. Откройте [share.streamlit.io](https://share.streamlit.io/).
2. Нажмите **Create app** и выберите этот GitHub-репозиторий.
3. Укажите ветку `main` и файл `app.py`.
4. Нажмите **Deploy**. Дополнительные системные пакеты и secrets не нужны.

В облаке выберите `Cookie header`. Чтобы получить его:

1. Откройте нужный документ FamilySearch в Chrome и войдите в аккаунт.
2. Откройте DevTools (`Cmd+Option+I`) и вкладку **Network**.
3. Обновите страницу, выберите запрос, содержащий `image_files`.
4. В **Request Headers** скопируйте значение заголовка `Cookie`.
5. Вставьте его в защищенное поле приложения.

Cookie используется только в памяти текущей Streamlit-сессии и не записывается
в файлы, логи или GitHub. Разворачивайте приложение как private app и не
передавайте cookie другим людям.

## Локальный запуск на macOS

Локально приложение умеет автоматически использовать активный вход из Chrome,
Chrome Canary, Edge или Brave.

```bash
./run.command
```

После запуска откройте [http://127.0.0.1:8501](http://127.0.0.1:8501).

## Ограничение авторизации

Streamlit Cloud не может читать cookies локального браузера из-за изоляции
доменов и серверной архитектуры. Официальная интеграция FamilySearch требует
зарегистрированного OAuth app key, redirect URI и допуска к production. Доступ
сторонних приложений к историческим изображениям также ограничен FamilySearch,
поэтому облачный режим использует временную пользовательскую web-сессию.

Официальная документация:

- [FamilySearch Authentication](https://developers.familysearch.org/main/docs/authentication)
- [FamilySearch Getting Started](https://developers.familysearch.org/main/docs/getting-started)
- [Streamlit Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
