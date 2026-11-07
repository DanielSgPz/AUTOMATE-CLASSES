import os
import json
from pathlib import Path
from dataclasses import dataclass

import keyring


CONNECTION_PATH = Path(__file__).resolve().parent.parent / "config" / "connection.json"
KEYRING_SERVICE = "AUTOMATE-CLASSES-SMART"


@dataclass(frozen=True)
class SmartCredentials:
    url: str
    username: str
    password: str


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str | None
    chat_id: str | None


def _cargar_env_local() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        linea = line.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue

        key, value = linea.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def load_smart_credentials() -> SmartCredentials:
    _cargar_env_local()

    saved = {}
    if CONNECTION_PATH.exists():
        saved = json.loads(CONNECTION_PATH.read_text(encoding="utf-8"))

    url = saved.get("url") or os.getenv(
        "SMART_LOGIN_URL", "https://schoolpack.smart.edu.co/idiomas/alumnos.aspx"
    )
    username = saved.get("username") or os.getenv("SMART_USERNAME")
    password = None
    if saved.get("username"):
        try:
            password = keyring.get_password(KEYRING_SERVICE, saved["username"])
        except Exception:
            password = None
    password = password or os.getenv("SMART_PASSWORD")

    missing = [name for name, value in {
        "SMART_USERNAME": username,
        "SMART_PASSWORD": password,
    }.items() if not value]

    if missing:
        raise RuntimeError(
            "Faltan variables de entorno para Smart: " + ", ".join(missing)
        )

    return SmartCredentials(url=url, username=username, password=password)


def save_smart_credentials(url: str, username: str, password: str | None = None) -> None:
    url = url.strip()
    username = username.strip()
    if not url or not username:
        raise ValueError("La URL y el usuario son obligatorios.")

    CONNECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    previous_username = None
    if CONNECTION_PATH.exists():
        previous_username = json.loads(CONNECTION_PATH.read_text(encoding="utf-8")).get("username")
    CONNECTION_PATH.write_text(
        json.dumps({"url": url, "username": username}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if previous_username and previous_username != username:
        try:
            keyring.delete_password(KEYRING_SERVICE, previous_username)
        except Exception:
            pass
    if password:
        keyring.set_password(KEYRING_SERVICE, username, password)


def smart_credentials_status() -> dict:
    _cargar_env_local()
    saved = {}
    if CONNECTION_PATH.exists():
        saved = json.loads(CONNECTION_PATH.read_text(encoding="utf-8"))
    username = saved.get("username") or os.getenv("SMART_USERNAME", "")
    url = saved.get("url") or os.getenv(
        "SMART_LOGIN_URL", "https://schoolpack.smart.edu.co/idiomas/alumnos.aspx"
    )
    password_configured = bool(os.getenv("SMART_PASSWORD"))
    if saved.get("username"):
        try:
            password_configured = password_configured or bool(
                keyring.get_password(KEYRING_SERVICE, saved["username"])
            )
        except Exception:
            pass
    return {
        "url": url,
        "username": username,
        "password_configured": password_configured,
    }


def load_telegram_config() -> TelegramConfig:
    _cargar_env_local()

    return TelegramConfig(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    )
