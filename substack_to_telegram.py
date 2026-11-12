#!/usr/bin/env python3
"""
Publica automaticamente no Telegram os novos posts do Substack.

Variáveis de ambiente:
  TELEGRAM_BOT_TOKEN  token do bot (do @BotFather)
  TELEGRAM_CHAT_ID    @usuario_do_canal ou ID numérico (ex.: -1001234567890)
  FEED_URL            (opcional) padrão: https://estudosnacionais.substack.com/feed
  STATE_FILE          (opcional) padrão: state.json

Na primeira execução, apenas registra os posts existentes (não publica nada),
para não inundar o canal com posts antigos.
"""
import html
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

FEED_URL = os.environ.get("FEED_URL", "https://estudosnacionais.substack.com/feed")
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
MAX_SEEN = 200  # quantos GUIDs guardar


def fetch_feed():
    req = urllib.request.Request(
        FEED_URL,
        headers={"User-Agent": "Mozilla/5.0 (substack-telegram-bot)"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        guid = (it.findtext("guid") or link).strip()
        desc = (it.findtext("description") or "").strip()
        items.append({"title": title, "link": link, "guid": guid, "desc": desc})
    return items  # mais recente primeiro


def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_state(seen):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"seen": seen[:MAX_SEEN]}, f, ensure_ascii=False, indent=2)


def send_telegram(item):
    text = f"<b>{html.escape(item['title'])}</b>"
    if item["desc"]:
        text += f"\n\n{html.escape(item['desc'])}"
    text += f"\n\n{html.escape(item['link'])}"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "false",
    }).encode()
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    with urllib.request.urlopen(url, data=data, timeout=30) as r:
        resp = json.loads(r.read())
    if not resp.get("ok"):
        raise RuntimeError(f"Telegram recusou: {resp}")


def main():
    if not TOKEN or not CHAT_ID:
        sys.exit("Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.")

    items = fetch_feed()
    state = load_state()

    if state is None:
        save_state([i["guid"] for i in items])
        print(f"Primeira execução: {len(items)} posts registrados, nada enviado.")
        return

    seen = state.get("seen", [])
    new = [i for i in items if i["guid"] not in seen]
    # envia do mais antigo para o mais novo
    for item in reversed(new):
        send_telegram(item)
        print(f"Enviado: {item['title']}")
        seen.insert(0, item["guid"])
        save_state(seen)  # salva a cada envio, evita duplicar se falhar no meio
        time.sleep(2)

    if not new:
        print("Nenhum post novo.")


if __name__ == "__main__":
    main()
