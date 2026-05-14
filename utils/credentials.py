import os
from pathlib import Path
from dataclasses import dataclass


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

    url = os.getenv("SMART_LOGIN_URL", "https://schoolpack.smart.edu.co/idiomas/alumnos.aspx")
    username = os.getenv("SMART_USERNAME")
    password = os.getenv("SMART_PASSWORD")

    missing = [name for name, value in {
        "SMART_USERNAME": username,
        "SMART_PASSWORD": password,
    }.items() if not value]

    if missing:
        raise RuntimeError(
            "Faltan variables de entorno para Smart: " + ", ".join(missing)
        )

    return SmartCredentials(url=url, username=username, password=password)


def load_telegram_config() -> TelegramConfig:
    _cargar_env_local()

    return TelegramConfig(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    )