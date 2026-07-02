"""
Configura todos os GitHub Actions Secrets do repositório Gaspy-APBR
automaticamente a partir do .env local + credenciais YouTube.

Uso:
    python setup_github_secrets.py

Requer um GitHub Personal Access Token (PAT) com escopo: repo (ou secrets)
Crie em: https://github.com/settings/tokens → Generate new token (classic)
Escopos necessários: repo (Full control of private repositories)
"""

import os
import sys
import base64
import json
import requests
from pathlib import Path

# ── Configuração ─────────────────────────────────────────────────────────────

REPO_OWNER = "diogoeduardo777"
REPO_NAME  = "Projeto-Gaspy"
REPO_FULL  = f"{REPO_OWNER}/{REPO_NAME}"

BASE_DIR    = Path(__file__).parent / "shorts-pipeline"
ENV_FILE    = BASE_DIR / ".env"
SECRETS_JSON = BASE_DIR / "client_secrets.json"
TOKEN_JSON   = BASE_DIR / "token.json"

# ── Helpers ───────────────────────────────────────────────────────────────────

def read_env(path):
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    from nacl import encoding, public
    pk = public.PublicKey(public_key_b64.encode(), encoding.Base64Encoder())
    box = public.SealedBox(pk)
    encrypted = box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def get_repo_public_key(session, repo):
    r = session.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key")
    r.raise_for_status()
    data = r.json()
    return data["key_id"], data["key"]


def set_secret(session, repo, key_id, public_key, name, value):
    encrypted = encrypt_secret(public_key, value)
    r = session.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{name}",
        json={"encrypted_value": encrypted, "key_id": key_id},
    )
    if r.status_code in (201, 204):
        print(f"  [OK] {name}")
    else:
        print(f"  [ERRO] {name} -> {r.status_code}: {r.text[:120]}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Gaspy-APBR — Configuração de GitHub Secrets")
    print("=" * 60)
    print()
    print("Crie um PAT em: github.com/settings/tokens")
    print("Tipo: classic  |  Escopos: [x] repo")
    print()
    pat = input("Cole seu GitHub PAT aqui: ").strip().lstrip("﻿")
    if not pat:
        print("PAT vazio — abortando.")
        sys.exit(1)

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })

    # Verifica autenticação
    me = session.get("https://api.github.com/user")
    if me.status_code != 200:
        print(f"Token inválido: {me.status_code} {me.text[:80]}")
        sys.exit(1)
    print(f"Autenticado como: {me.json()['login']}\n")

    # Lê chave pública do repositório
    print(f"Repositório: {REPO_FULL}")
    key_id, public_key = get_repo_public_key(session, REPO_FULL)
    print(f"Chave pública obtida (key_id: {key_id})\n")

    # Lê valores do .env
    env = read_env(ENV_FILE)

    # Base64 das credenciais YouTube
    yt_client_b64 = base64.b64encode(SECRETS_JSON.read_bytes()).decode() if SECRETS_JSON.exists() else ""
    yt_token_b64  = base64.b64encode(TOKEN_JSON.read_bytes()).decode()    if TOKEN_JSON.exists()   else ""

    # Mapa de secrets a configurar
    secrets = {
        # LLM
        "GROQ_API_KEY":   env.get("GROQ_API_KEY", ""),
        "GROQ_MODEL":     env.get("GROQ_MODEL", "llama-3.3-70b-versatile"),

        # Imagens
        "UNSPLASH_ACCESS_KEY": env.get("UNSPLASH_ACCESS_KEY", ""),

        # Afiliados
        "AMAZON_AFFILIATE_TAG":      env.get("AMAZON_AFFILIATE_TAG", ""),
        "SHOPEE_AFFILIATE_ID":        env.get("SHOPEE_AFFILIATE_ID", ""),
        "MERCADOLIVRE_AFFILIATE_ID":  env.get("MERCADOLIVRE_AFFILIATE_ID", ""),

        # Kling AI
        "KLING_ACCESS_KEY": env.get("KLING_ACCESS_KEY", ""),
        "KLING_SECRET_KEY": env.get("KLING_SECRET_KEY", ""),

        # YouTube
        "YOUTUBE_AUTO_UPLOAD":  env.get("YOUTUBE_AUTO_UPLOAD", "true"),
        "YOUTUBE_PRIVACY":      env.get("YOUTUBE_PRIVACY", "public"),
        "YOUTUBE_CLIENT_SECRETS": yt_client_b64,
        "YOUTUBE_TOKEN":          yt_token_b64,

        # Pipeline
        "ACTIVE_NICHE":      env.get("ACTIVE_NICHE", "tech"),
        "TELEGRAM_CHANNEL":  env.get("TELEGRAM_CHANNEL", ""),
    }

    # Remove secrets vazios (não sobrescreve com vazio)
    skip = {k for k, v in secrets.items() if not v}
    if skip:
        print(f"Pulando (valores vazios): {', '.join(sorted(skip))}\n")

    print("Configurando secrets:")
    for name, value in secrets.items():
        if name in skip:
            print(f"  [SKIP] {name} (vazio - pulado)")
            continue
        set_secret(session, REPO_FULL, key_id, public_key, name, value)

    print()
    print("Pronto! Verifique em:")
    print(f"  https://github.com/{REPO_FULL}/settings/secrets/actions")


if __name__ == "__main__":
    main()
