import requests, os, json, hashlib
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText

# ---------------- CONFIG ----------------
ORIGIN = "AMD"
MAX_PRICE = 20000
CURRENCY = "INR"
DAYS_AHEAD = 90

KIWI_KEY = os.environ["KIWI_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT = os.environ["TELEGRAM_CHAT_ID"]

EMAIL_FROM = os.environ["EMAIL_FROM"]
EMAIL_TO = os.environ["EMAIL_TO"]
EMAIL_PASS = os.environ["EMAIL_PASS"]

DATA_FILE = "sent_deals.json"

# ----------------------------------------

def load_data():
    return json.load(open(DATA_FILE)) if os.path.exists(DATA_FILE) else {}

def save_data(d):
    json.dump(d, open(DATA_FILE, "w"), indent=2)

def hash_key(d):
    k = f"{d['flyTo']}{d['dTime']}{d['aTime']}{d['price']}"
    return hashlib.md5(k.encode()).hexdigest()

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"})

def send_email(html):
    m = MIMEText(html, "html")
    m["Subject"] = "✈️ Flight Price Drop Alert (Round Trip)"
    m["From"] = EMAIL_FROM
    m["To"] = EMAIL_TO

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_FROM, EMAIL_PASS)
        s.send_message(m)

def main():
    db = load_data()

    today = datetime.now().strftime("%d/%m/%Y")
    future = (datetime.now() + timedelta(days=DAYS_AHEAD)).strftime("%d/%m/%Y")

    url = "https://api.tequila.kiwi.com/v2/search"
    headers = {"apikey": KIWI_KEY}

    params = {
        "fly_from": ORIGIN,
        "fly_to": "anywhere",
        "date_from": today,
        "date_to": future,
        "return_from": today,
        "return_to": future,
        "price_to": MAX_PRICE,
        "curr": CURRENCY,
        "limit": 40
    }

    res = requests.get(url, headers=headers, params=params).json()

    for d in res.get("data", []):
        if d.get("countryTo", {}).get("code") == "IN":
            continue

        key = hash_key(d)
        price = d["price"]
        prev = db.get(key)

        status = "✨🆕 NEW DEAL"
        emoji = "✨"

        if prev:
            if price >= prev["price"]:
                continue
            drop = prev["price"] - price
            pct = round((drop / prev["price"]) * 100, 1)
            emoji = "🔥🔻" if drop >= 2000 else "🔻"
            status = f"{emoji} PRICE DROP ₹{drop} ({pct}%)"

        db[key] = {"price": price}

        html = f"""
        <h2>{status}</h2>
        <b>Route:</b> AMD → {d['cityTo']} ({d['flyTo']}) → AMD<br>
        <b>Depart:</b> {datetime.fromtimestamp(d['dTime']).strftime('%d %b %Y')}<br>
        <b>Return:</b> {datetime.fromtimestamp(d['aTime']).strftime('%d %b %Y')}<br>
        <b>Airline:</b> {", ".join(d['airlines'])}<br>
        <b>Stops:</b> {len(d['route'])//2 - 1}<br><br>

        <h1>₹{price}</h1>
        <a href="{d['deep_link']}">🔗 Book Now</a>
        """

        tg = f"""{status}
AMD → {d['flyTo']} → AMD
💰 ₹{price}
📅 {datetime.fromtimestamp(d['dTime']).strftime('%d %b')} – {datetime.fromtimestamp(d['aTime']).strftime('%d %b')}
🔗 {d['deep_link']}
"""

        send_email(html)
        send_telegram(tg)

    save_data(db)

if __name__ == "__main__":
    main()
``
