from __future__ import annotations

import hashlib
import html
import io
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, unquote, urlparse

import requests
from Crypto.Cipher import AES
from PIL import Image


TILE_SIZE = 256
TILE_OVERLAP = 1
MAX_GRID_SIDE = 100
MAX_TILES = 2_500
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137 Safari/537.36"
)

ProgressCallback = Callable[[float, str], None]


class DownloadError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentLink:
    original_url: str
    ark_id: str
    image_index: int | None

    @property
    def page_number(self) -> int | None:
        return self.image_index + 1 if self.image_index is not None else None

    @property
    def safe_id(self) -> str:
        return self.ark_id.removeprefix("3:1:")

    @property
    def filename(self) -> str:
        suffix = f"_page_{self.page_number}" if self.page_number is not None else ""
        return f"familysearch_{self.safe_id}{suffix}.jpg"


@dataclass(frozen=True)
class BrowserProfile:
    label: str
    cookie_db: Path
    keychain_service: str


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    width: int
    height: int
    level: int
    columns: int
    rows: int
    browser_profile: str


def parse_familysearch_url(raw_url: str) -> DocumentLink:
    cleaned = html.unescape(raw_url.strip())
    cleaned = unquote(cleaned.replace("&amp%3B", "&").replace("%26amp%253B", "&"))

    match = re.search(r"/ark:/61903/(3:1:[A-Za-z0-9-]+)", cleaned)
    if not match:
        raise DownloadError("Не найден идентификатор FamilySearch формата 3:1:...")

    parsed = urlparse(cleaned)
    if parsed.hostname not in {"familysearch.org", "www.familysearch.org"}:
        raise DownloadError("Поддерживаются только ссылки с сайта familysearch.org")

    query = parse_qs(parsed.query)
    index = None
    if query.get("i"):
        try:
            index = int(query["i"][0])
        except ValueError:
            pass

    return DocumentLink(cleaned, match.group(1), index)


def discover_browser_profiles() -> list[BrowserProfile]:
    home = Path.home()
    candidates = [
        (
            "Google Chrome",
            home / "Library/Application Support/Google/Chrome",
            "Chrome Safe Storage",
        ),
        (
            "Google Chrome Canary",
            home / "Library/Application Support/Google/Chrome Canary",
            "Chrome Safe Storage",
        ),
        (
            "Microsoft Edge",
            home / "Library/Application Support/Microsoft Edge",
            "Microsoft Edge Safe Storage",
        ),
        (
            "Brave Browser",
            home / "Library/Application Support/BraveSoftware/Brave-Browser",
            "Brave Safe Storage",
        ),
    ]

    profiles: list[BrowserProfile] = []
    for browser_name, root, keychain_service in candidates:
        if not root.exists():
            continue
        profile_dirs = [root / "Default", *sorted(root.glob("Profile *"))]
        for profile_dir in profile_dirs:
            cookie_db = profile_dir / "Cookies"
            if cookie_db.exists():
                profile_name = "Default" if profile_dir.name == "Default" else profile_dir.name
                profiles.append(
                    BrowserProfile(
                        f"{browser_name} - {profile_name}", cookie_db, keychain_service
                    )
                )
    return profiles


def _safe_storage_password(service: str) -> bytes:
    result = subprocess.run(
        ["security", "find-generic-password", "-w", "-s", service],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise DownloadError(
            f"Не удалось прочитать ключ '{service}' из Связки ключей macOS."
        )
    return result.stdout.rstrip(b"\n")


def _decrypt_cookie(host: str, encrypted: bytes, key: bytes) -> str:
    if not encrypted or not encrypted.startswith(b"v10"):
        return ""

    ciphertext = encrypted[3:]
    if len(ciphertext) % AES.block_size:
        return ""

    decrypted = AES.new(key, AES.MODE_CBC, iv=b" " * 16).decrypt(ciphertext)
    padding = decrypted[-1]
    if padding < 1 or padding > AES.block_size:
        return ""
    decrypted = decrypted[:-padding]

    host_hash = hashlib.sha256(host.encode("utf-8")).digest()
    if decrypted.startswith(host_hash):
        decrypted = decrypted[len(host_hash) :]
    return decrypted.decode("utf-8")


def _cookie_header(profile: BrowserProfile) -> str:
    password = _safe_storage_password(profile.keychain_service)
    key = hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1003, 16)

    with tempfile.TemporaryDirectory(prefix="familysearch-cookies-") as temp_dir:
        copied_db = Path(temp_dir) / "Cookies"
        shutil.copy2(profile.cookie_db, copied_db)
        connection = sqlite3.connect(copied_db)
        try:
            rows = connection.execute(
                """
                SELECT host_key, name, encrypted_value, value
                FROM cookies
                WHERE host_key LIKE '%familysearch.org%'
                ORDER BY host_key, name
                """
            ).fetchall()
        finally:
            connection.close()

    cookies: list[str] = []
    for host, name, encrypted, plain in rows:
        try:
            value = plain or _decrypt_cookie(host, encrypted, key)
        except (UnicodeDecodeError, ValueError):
            continue
        if value:
            cookies.append(f"{name}={value}")

    if not cookies:
        raise DownloadError(
            f"В профиле '{profile.label}' не найдены cookies FamilySearch. "
            "Откройте FamilySearch в этом браузере и войдите в аккаунт."
        )
    return "; ".join(cookies)


def normalize_cookie_header(raw_cookie_header: str) -> str:
    value = raw_cookie_header.strip()
    if value.lower().startswith("cookie:"):
        value = value.split(":", 1)[1].strip()
    if "\r" in value or "\n" in value:
        raise DownloadError("Cookie header должен быть одной строкой.")
    if "=" not in value:
        raise DownloadError("Cookie header не похож на строку cookies FamilySearch.")
    return value


class TileClient:
    def __init__(self, document: DocumentLink, cookie_header: str) -> None:
        self.document = document
        self.headers = {
            "Cookie": cookie_header,
            "Referer": document.original_url,
            "User-Agent": USER_AGENT,
        }

    def tile_url(self, level: int, column: int, row: int) -> str:
        return (
            "https://sg30p0.familysearch.org/service/records/storage/"
            f"deepzoomcloud/dz/v1/{self.document.ark_id}/image_files/"
            f"{level}/{column}_{row}.jpg"
        )

    def get_tile(self, level: int, column: int, row: int, timeout: int = 25) -> bytes:
        response = requests.get(
            self.tile_url(level, column, row),
            headers=self.headers,
            timeout=timeout,
        )
        if response.status_code in {401, 403}:
            raise DownloadError(
                "FamilySearch отклонил авторизацию. Обновите страницу документа и "
                "повторно получите Cookie header или войдите в выбранном браузере."
            )
        if response.status_code == 404:
            raise FileNotFoundError
        response.raise_for_status()
        return response.content

    def probe(self, level: int, column: int, row: int) -> tuple[bytes, tuple[int, int]] | None:
        try:
            data = self.get_tile(level, column, row, timeout=15)
        except FileNotFoundError:
            return None
        try:
            size = Image.open(io.BytesIO(data)).size
        except Exception as error:
            raise DownloadError("FamilySearch вернул поврежденную плитку изображения.") from error
        return data, size


def _find_working_client(
    document: DocumentLink,
    profiles: list[BrowserProfile],
    preferred_label: str | None,
) -> tuple[TileClient, BrowserProfile]:
    ordered = profiles
    if preferred_label:
        ordered = sorted(profiles, key=lambda profile: profile.label != preferred_label)

    errors: list[str] = []
    for profile in ordered:
        try:
            client = TileClient(document, _cookie_header(profile))
            if client.probe(8, 0, 0) is not None:
                return client, profile
        except Exception as error:
            errors.append(f"{profile.label}: {error}")

    details = "\n".join(errors[-3:])
    raise DownloadError(
        "Не удалось использовать активный вход FamilySearch ни в одном браузере.\n"
        "Откройте документ в Chrome, войдите в аккаунт и повторите попытку."
        + (f"\n\n{details}" if details else "")
    )


def _detect_level(client: TileClient) -> int:
    highest = None
    for level in range(0, 19):
        if client.probe(level, 0, 0) is not None:
            highest = level
        elif highest is not None:
            break
    if highest is None:
        raise DownloadError("Не удалось найти DeepZoom-плитки этого документа.")
    return highest


def _detect_grid(
    client: TileClient, level: int, tile_dir: Path
) -> tuple[int, int]:
    columns = 0
    for column in range(MAX_GRID_SIDE):
        result = client.probe(level, column, 0)
        if result is None:
            break
        data, _ = result
        (tile_dir / f"{column}_0.jpg").write_bytes(data)
        columns = column + 1

    rows = 0
    for row in range(MAX_GRID_SIDE):
        result = client.probe(level, 0, row)
        if result is None:
            break
        data, _ = result
        (tile_dir / f"0_{row}.jpg").write_bytes(data)
        rows = row + 1

    if not columns or not rows:
        raise DownloadError("Не удалось определить размер сетки изображения.")
    if columns * rows > MAX_TILES:
        raise DownloadError("Изображение содержит слишком много плиток для безопасной обработки.")
    return columns, rows


def download_document(
    raw_url: str,
    output_dir: Path,
    preferred_profile: str | None = None,
    cookie_header: str | None = None,
    jpeg_quality: int = 95,
    workers: int = 10,
    progress: ProgressCallback | None = None,
) -> DownloadResult:
    document = parse_familysearch_url(raw_url)

    def report(value: float, message: str) -> None:
        if progress:
            progress(max(0.0, min(1.0, value)), message)

    report(0.02, "Проверяю вход в FamilySearch")
    if cookie_header:
        auth_source = "Cookie header"
        client = TileClient(document, normalize_cookie_header(cookie_header))
        try:
            if client.probe(8, 0, 0) is None:
                raise DownloadError("Не удалось открыть изображение с указанными cookies.")
        except requests.RequestException as error:
            raise DownloadError(f"Ошибка соединения с FamilySearch: {error}") from error
    else:
        profiles = discover_browser_profiles()
        if not profiles:
            raise DownloadError(
                "На этом сервере нет локального браузера. Вставьте Cookie header FamilySearch."
            )
        client, profile = _find_working_client(document, profiles, preferred_profile)
        auth_source = profile.label
    report(0.08, f"Используется {auth_source}")

    level = _detect_level(client)
    report(0.13, f"Найден максимальный уровень качества: {level}")

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="familysearch-tiles-") as temp_dir:
        tile_dir = Path(temp_dir)
        columns, rows = _detect_grid(client, level, tile_dir)
        total = columns * rows
        report(0.18, f"Сетка {columns} x {rows}, плиток: {total}")

        def fetch(column: int, row: int) -> Path:
            path = tile_dir / f"{column}_{row}.jpg"
            if path.exists() and path.stat().st_size:
                return path

            last_error: Exception | None = None
            for attempt in range(4):
                try:
                    data = client.get_tile(level, column, row, timeout=30)
                    Image.open(io.BytesIO(data)).verify()
                    path.write_bytes(data)
                    return path
                except Exception as error:
                    last_error = error
                    time.sleep(0.35 * (attempt + 1))
            raise DownloadError(f"Не удалось скачать плитку {column}_{row}: {last_error}")

        jobs = [(column, row) for row in range(rows) for column in range(columns)]
        completed = 0
        with ThreadPoolExecutor(max_workers=max(1, min(16, workers))) as executor:
            futures = [executor.submit(fetch, column, row) for column, row in jobs]
            for future in as_completed(futures):
                future.result()
                completed += 1
                report(
                    0.18 + 0.65 * completed / total,
                    f"Скачано плиток: {completed} / {total}",
                )

        last_width = Image.open(tile_dir / f"{columns - 1}_0.jpg").size[0]
        last_height = Image.open(tile_dir / f"0_{rows - 1}.jpg").size[1]
        width = (
            last_width
            if columns == 1
            else (columns - 1) * TILE_SIZE - TILE_OVERLAP + last_width
        )
        height = (
            last_height
            if rows == 1
            else (rows - 1) * TILE_SIZE - TILE_OVERLAP + last_height
        )
        if width <= 0 or height <= 0 or width * height > 250_000_000:
            raise DownloadError("Получен некорректный размер итогового изображения.")

        report(0.88, f"Склеиваю изображение {width} x {height}")
        canvas = Image.new("RGB", (width, height), "black")
        for row in range(rows):
            for column in range(columns):
                tile = Image.open(tile_dir / f"{column}_{row}.jpg").convert("RGB")
                x = max(0, column * TILE_SIZE - TILE_OVERLAP)
                y = max(0, row * TILE_SIZE - TILE_OVERLAP)
                canvas.paste(tile, (x, y))

        output_path = output_dir / document.filename
        canvas.save(
            output_path,
            "JPEG",
            quality=max(70, min(100, jpeg_quality)),
            subsampling=0,
            optimize=True,
        )

    report(1.0, "Готово")
    return DownloadResult(
        path=output_path,
        width=width,
        height=height,
        level=level,
        columns=columns,
        rows=rows,
        browser_profile=auth_source,
    )
