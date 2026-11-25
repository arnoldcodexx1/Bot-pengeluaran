import os
import re
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import pytz

app = Flask(__name__)

# --- SETTING ---
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "botgacor123")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
WITA = pytz.timezone("Asia/Makassar")
DATA_FILE = "data.json"

# --- DATABASE SEDERHANA (JSON) ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def parse_uang(teks):
    teks = teks.lower().replace(".", "").replace(",", "").strip()
    # 50k, 50rb, 50 ribu, 1,5jt, 1.5jt
    m = re.search(r"(\d+(?:\.\d+)?)\s*(jt|juta|k|rb|ribu)?", teks)
    if not m:
        return None
    angka = float(m.group(1))
    satuan = m.group(2)
    if satuan in ["jt", "juta"]:
        angka *= 1000000
    elif satuan in ["k", "rb", "ribu"]:
        angka *= 1000
    return int(angka)

def format_rupiah(n):
    return f"Rp {n:,}".replace(",", ".")

def kirim_wa(to, pesan):
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print(f"[SIMULASI KE {to}]: {pesan}")
        return
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": pesan}}
    try:
        requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print("Gagal kirim WA:", e)

def olah_pesan(sender, teks):
    teks_asli = teks.strip()
    teks_low = teks_asli.lower()
    data = load_data()
    if sender not in data:
        data[sender] = []
    hari_ini = datetime.now(WITA).strftime("%Y-%m-%d")

    # --- MENU ---
    if teks_low in ["halo", "hai", "hi", "menu", "help", "mulai", "start"]:
        return ("🤖 *BOT PENGELUARAN GACOR* 🤖\n\n"
                "Cara pake, tinggal chat aja:\n"
                "• `makan 50k` -> catat makan 50rb\n"
                "• `bensin 30rb` -> catat bensin\n"
                "• `jajan 15k` -> catat jajan\n\n"
                "Perintah lain:\n"
                "• `LAPORAN` -> total hari ini\n"
                "• `LAPORAN MINGGU` -> total 7 hari\n"
                "• `LAPORAN BULAN` -> total bulan ini\n"
                "• `RIWAYAT` -> 10 terakhir\n"
                "• `HAPUS TERAKHIR` -> hapus yang salah catat\n"
                "• `HAPUS SEMUA` -> reset total")

    # --- LAPORAN ---
    if teks_low.startswith("laporan"):
        items = data[sender]
        now = datetime.now(WITA)
        if "minggu" in teks_low:
            batas = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            pilih = [x for x in items if x["tanggal"] >= batas]
            judul = "📊 LAPORAN 7 HARI TERAKHIR"
        elif "bulan" in teks_low:
            pilih = [x for x in items if x["tanggal"].startswith(now.strftime("%Y-%m"))]
            judul = f"📊 LAPORAN BULAN {now.strftime('%B %Y')}"
        else:
            pilih = [x for x in items if x["tanggal"] == hari_ini]
            judul = "📊 LAPORAN HARI INI"
        if not pilih:
            return "Belum ada pengeluaran di periode ini. Masih aman dompet lu 😎"
        total = sum(x["nominal"] for x in pilih)
        per_kategori = {}
        for x in pilih:
            per_kategori[x["kategori"]] = per_kategori.get(x["kategori"], 0) + x["nominal"]
        teks = f"{judul}\nTotal: *{format_rupiah(total)}*\n\nRincian:\n"
        for k, v in sorted(per_kategori.items(), key=lambda x: -x[1]):
            teks += f"• {k.capitalize()}: {format_rupiah(v)}\n"
        return teks

    if teks_low == "riwayat":
        items = data[sender][-10:]
        if not items:
            return "Belum ada riwayat. Coba catat dulu: `makan 20k`"
        teks = "🧾 *10 TRANSAKSI TERAKHIR*\n\n"
        for i, x in enumerate(reversed(items), 1):
            teks += f"{i}. {x['kategori']} - {format_rupiah(x['nominal'])} ({x['tanggal']})\n"
        return teks

    if teks_low == "hapus terakhir":
        if data[sender]:
            hapus = data[sender].pop()
            save_data(data)
            return f"✅ Dihapus: {hapus['kategori']} {format_rupiah(hapus['nominal'])}"
        return "Gak ada yang bisa dihapus."

    if teks_low == "hapus semua":
        data[sender] = []
        save_data(data)
        return "🗑️ Semua data lu udah di-reset. Mulai dari 0 lagi!"

    # --- CATAT PENGELUARAN: "makan 50k" ---
    parts = teks_asli.split()
    if len(parts) >= 2:
        nominal = parse_uang(parts[-1])
        kategori = " ".join(parts[:-1]).lower()
        if nominal and kategori:
            data[sender].append({
                "kategori": kategori,
                "nominal": nominal,
                "tanggal": hari_ini,
                "jam": datetime.now(WITA).strftime("%H:%M")
            })
            save_data(data)
            total_hari_ini = sum(x["nominal"] for x in data[sender] if x["tanggal"] == hari_ini)
            return (f"✅ Dicatat!\n"
                    f"{kategori.capitalize()}: *{format_rupiah(nominal)}*\n"
                    f"Total hari ini: *{format_rupiah(total_hari_ini)}*\n\n"
                    f"Ketik `LAPORAN` buat liat total.")

    return ("Hmm gak ngerti pang 😅\n"
            "Contoh yang bener: `makan 50k`\n"
            "Ketik `MENU` buat liat semua perintah.")

@app.route("/")
def home():
    return "Bot Pengeluaran Aktif ✅"

@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Gagal verifikasi", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()
    try:
        entry = body["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            msg = entry["messages"][0]
            sender = msg["from"]
            teks = msg["text"]["body"]
            balasan = olah_pesan(sender, teks)
            kirim_wa(sender, balasan)
    except Exception as e:
        print("Error webhook:", e)
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)