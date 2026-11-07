import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import keyring


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "github.json"
KEYRING_SERVICE = "AUTOMATE-CLASSES-GITHUB"
VARIABLE_NAME = "PROGRAMMING_PROFILE_JSON"


def save_github_config(repository: str, token: str | None = None) -> dict:
    repository = repository.strip()
    if repository.count("/") != 1:
        raise ValueError("El repositorio debe tener formato propietario/repositorio.")
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps({"repository": repository}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if token:
        keyring.set_password(KEYRING_SERVICE, repository, token.strip())
    return github_status()


def github_status() -> dict:
    repository = os.getenv("GITHUB_REPOSITORY", "")
    if CONFIG_PATH.exists():
        repository = json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("repository", repository)
    return {
        "repository": repository,
        "token_configured": bool(_token(repository)),
        "variable_name": VARIABLE_NAME,
    }


def publish_profile(profile: dict) -> dict:
    status = github_status()
    repository = status["repository"]
    token = _token(repository)
    if not repository or not token:
        return {"published": False, "reason": "github_no_configurado"}

    value = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
    variable_url = f"https://api.github.com/repos/{repository}/actions/variables/{VARIABLE_NAME}"
    try:
        _request(variable_url, token, "PATCH", {"name": VARIABLE_NAME, "value": value})
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise RuntimeError(_github_error(error)) from error
        collection_url = f"https://api.github.com/repos/{repository}/actions/variables"
        try:
            _request(collection_url, token, "POST", {"name": VARIABLE_NAME, "value": value})
        except urllib.error.HTTPError as create_error:
            raise RuntimeError(_github_error(create_error)) from create_error
    return {"published": True, "repository": repository, "variable_name": VARIABLE_NAME}


def _token(repository: str) -> str:
    token = os.getenv("GITHUB_CONFIG_TOKEN", "")
    if repository:
        try:
            token = keyring.get_password(KEYRING_SERVICE, repository) or token
        except Exception:
            pass
    return token


def _request(url: str, token: str, method: str, payload: dict) -> None:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "automate-classes",
        },
    )
    with urllib.request.urlopen(request, timeout=20):
        pass


def _github_error(error: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(error.read().decode("utf-8"))
        message = body.get("message", error.reason)
    except Exception:
        message = error.reason
    return f"GitHub respondió {error.code}: {message}"
