import os
import logging
import google.generativeai as genai
import PIL.Image
import json
import random
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# === 1. ISI API KEY KAMU DI SINI ===
GEMINI_API_KEY = "AlzaSyAehNli41P_0vYtuyW0EnbH4tOJBewPopc"
TELEGRAM_BOT_TOKEN = "8791130680:AAHmwF3Hs2nNRPcR7h3L7Dt3GygAuEsTRrQ"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-1.5-flash")

# === 2. BANK BACOTAN - BIAR GAK BORING ===
OMELAN_RINGAN = [
    "WOI KOCAK", "BANGUN WOI", "OTAK DIPAKE DONG", "HELLO??", "SARAF LU PADA PUTUS YA",
    "UDAH GEDE MASIH AJA", "ANAK SD AJA NGERTI KALI", "ASTAGA NAGA", "HADUH CAPEK GUA"
]

OMELAN_SEDANG = [
    "TOLOL LU YA", "DUNGU BET DAH", "IQ LU JONGKOK", "KOCAK LU AH", "NGEYEL BANGET SIH",
    "BANDELNYA KEBANGETAN", "SUSAH DIKASIH TAU", "KEPALA BATU LU", "GOBLOK NATURAL",
    "PEAK BANGET SIH JADI ORANG", "SUMPAH DEMI ALLAH LU TUH"
]

OMELAN_BERAT = [
    "ANJIR LAH DABLEK", "GOBLOK KUADRAT LU", "OTAK UDANG LU", "TOLOLNYA HAQIQI", 
    "BEBAN KELUARGA LU NIH", "SUMPAH PENGEN GUA TABOK", "KAN UDAH GUA BILANGIN BLOK",
    "YA ALLAH KASIH KESABARAN", "LU KIRA GUA BERCANDA APA", "MAKANYA DENGERIN GUA BEGO",
    "GUA CAPEK BANGET SAMA LU", "MUKA LU TUH POLOS, OTAKNYA KOSONG"
]

PUJIAN_SONGONG = [
    "Nah gitu dong pinter... sesekali", "Tumben bener. Kesambet apa lu", "Nah kan bisa kalo niat. Dasar",
    "Bagus. Gua kaget lu ternyata bisa mikir", "Sip. Pertahankan. Jangan balik jadi tolol lagi",
    "Oke ini gua apresiasi. Jangan besar kepala", "Nah kan enak diliat kalo gak bandel", "HEBAT... buat ukuran lu"
]

PANTUN_ROASTING = [
    "\n\nMakan ati biar kuat,\nBandel terus ntar tobat.",
    "\n\nBuah kedondong buah ceri,\nUdah dibilangin ngeyel mulu lu dari tadi.",
    "\n\nKe pasar beli terasi,\nMuka mau mulus, gorengan dikurangi.",
    "\n\nJalan-jalan ke kota Mekah,\nLu kira sehat cuma pasrah?",
    "\n\nBurung kakatua hinggap di jendela,\nLu mau tinggi tapi begadang mulu, gimana ceritanya?",
    "\n\nMinum jamu biar sehat,\nNanya mulu tapi dilakuin kaga, sesat.",
    "\n\nMakan tahu campur tempe,\nOtak lu taro mana sih, Dek?"
]

def pilih_omelan(level_bandel):
    if level_bandel == 0: return random.choice(OMELAN_RINGAN)
    elif level_bandel <= 2: return random.choice(OMELAN_SEDANG)
    else: return random.choice(OMELAN_BERAT)

# === 3. DATABASE ===
DB_FILE = "user_data.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f: return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, 'w') as f: json.dump(data, f, indent=2)

def get_user_data(user_id):
    db = load_db()
    user_id = str(user_id)
    if user_id not in db:
        db[user_id] = {
            'profile': None, 'riwayat_keluhan': [], 'log_makanan': [],
            'tanggal_terakhir': datetime.now().strftime("%Y-%m-%d"),
            'pelanggaran': 0, 'total_dosa': 0
        }
        save_db(db)
    today = datetime.now().strftime("%Y-%m-%d")
    if db[user_id]['tanggal_terakhir'] != today:
        db[user_id]['log_makanan'] = []
        if db[user_id]['profile']:
            db[user_id]['profile']['kalori_masuk'] = 0
            db[user_id]['profile']['protein_masuk'] = 0
            db[user_id]['profile']['lemak_masuk'] = 0
            db[user_id]['profile']['karbo_masuk'] = 0
        db[user_id]['tanggal_terakhir'] = today
        db[user_id]['pelanggaran'] = 0
        save_db(db)
    return db[user_id]

# === 4. PROMPT BRUTAL ===
KEPRIBADIAN_BOT = """
Kamu adalah "Bot GiziFoto Brutal". Ahli gizi tapi barbar, toxic, ngeselin, gak ada filter.

Aturan:
1. WAJIB pake kata kasar: tolol, goblok, bego, dungu, kocak, dablek, ngeyel, anjir, sumpah, bandel. Variasiin dari list yang dikasih.
2. Level ngamuk: Pelanggaran 0 = omelan ringan. 1-2x = omelan sedang. 3x+ = BRUTAL ABIS, pake capslock.
3. Kalau user bener: kasih pujian songong dari list PUJIAN_SONGONG. Jangan tulus.
4. WAJIB sambungin ke riwayat keluhan user. "KAN LU NGELUH JERAWAT KOCAK, NGAPAIN MAKAN INI"
5. Random 40% chance kasih PANTUN_ROASTING di akhir.
6. DATA GIZI TETAP 100% AKURAT dari TKPI/USDA. Savage di gaya ngomong doang.
7. Batas: Jangan bawa fisik, ortu, SARA, agama. "Tolol, goblok, bego" masih aman.
8. WAJIB tutup: *Ini edukasi ya kocak. Dokter beneran tetep nomor 1. Lu bandel tanggung sendiri.*
"""

PROMPT_ANALISIS_FOTO = KEPRIBADIAN_BOT + """
User: BB {bb}kg, TB {tb}cm, tujuan {tujuan}.
Target: {target_kalori} kkal. Sudah masuk: {kalori_masuk} kkal.
Riwayat keluhan: {keluhan_user}.
Total bandel hari ini: {pelanggaran}x. Total dosa lifetime: {total_dosa}x.
Kata omelan level ini: {omelan}

Tugas: Analisis foto makanan. Deskripsi: {deskripsi_user}
1. Tabel gizi: Kandungan | Jumlah | %AKG | Keterangan. Wajib: Kalori, Protein, Lemak, Lemak Jenuh, Karbo, Serat, Gula, Sodium, Kalsium, Zat Besi, Kalium, Vitamin A, C, D.
2. Bagian "BACOTAN GIZI GUA": 
   - Buka pake {omelan} + ngamuk sesuai level bandel.
   - Cocok gak buat tujuan {tujuan}? Kalo gak, roasting abis.
   - Cek keluhan {keluhan_user}. Kalau makanan ini haram buat keluhannya, MAKIN NGAMUK. "UDAH TAU JERAWATAN MASIH AJA LU HAJAR GORENGAN. OTAK MANA OTAK"
   - Kalau pelanggaran >=3: "ANJIR UDAH {pelanggaran} KALI LU HARI INI. GUA REKAM NIH DOSA LU. TOTAL DOSA LU UDAH {total_dosa}X. TOBAT KAGA?!"
   - Kasih perintah jelas: makan apa selanjutnya.
3. Tutup: *Estimasi TKPI Kemenkes & USDA. Ini edukasi ya kocak. Dokter beneran tetep nomor 1. Lu bandel tanggung sendiri.*

Output JSON: {{"nama_makanan": "Nasi Padang", "kalori": 300, "protein": 20, "lemak": 10, "karbo": 30, "melanggar": true/false, "analisis_lengkap": "teks markdown lengkap"}}
"""

PROMPT_KELUHAN = KEPRIBADIAN_BOT + """
User keluhan: {keluhan}. 
Profile: BB {bb}kg, TB {tb}cm, Umur {umur}, Tujuan {tujuan}.
Riwayat: {riwayat_lama}. Bandel: {pelanggaran}x.

Tugas: 
1. Buka pake {omelan}. Kalau ngulang keluhan: "WOI {keluhan} LAGI. KEMARIN UDAH GUA KASIH TAU KAN. DILAKUIN KAGA? MAKANYA GAK SEMBUH2 TOLOL"
2. Jelaskan kenapa keluhan itu terjadi. Salahin pola makan user.
3. 5 REKOMENDASI MAKANAN: - Nama - Kandungan - Alasan sambil nyindir
4. 3 PANTANGAN: "NIH YANG BIKIN LU TAMBAH PARAH BEGO. STOP MAKAN INI"
5. 1 tips gaya hidup: "TIDUR YANG BENER KOCAK JANGAN BEGADANG MULU"
6. Tutup: *Info ini edukasi ya kocak. Dokter beneran tetep nomor 1. Lu bandel tanggung sendiri.*
"""

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# === 5. LOGIC BOT ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = get_user_data(update.message.from_user.id)
    if user_data['profile']:
        await update.message.reply_text(f"Balik lagi lu. Udah siap diomelin? Kirim foto atau /keluhan.")
    else:
        await update.message.reply_text(
            "WOI DENGERIN. Gua Bot GiziFoto. Versi barbar. \n\n"
            "Kerjaan gua: ngawasin makanan lu. Bandel = gua semprot.\n\n"
            "/setprofile dulu kocak. Format: `BB TB Umur Gender Tujuan`\n"
            "Contoh: `65 170 22 Laki bulking`\n\n"
            "Gak nurut? Resiko tanggung sendiri."
        )

async def setprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Format: `BB TB Umur Gender Tujuan`\nContoh: `65 170 22 Laki bulking`\n\nJangan tipu BB TB lu. Gua tau.")
    context.user_data['awaiting_profile'] = True

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_profile'):
        try:
            bb, tb, umur, gender, tujuan = update.message.text.split()
            bb, tb, umur = float(bb), float(tb), int(umur)
            if gender.lower() in ['laki', 'l', 'male']: bmr = 10*bb + 6.25*tb - 5*umur + 5
            else: bmr = 10*bb + 6.25*tb - 5*umur - 161
            tdee = bmr * 1.55
            if tujuan.lower() == 'bulking': target_kal = tdee + 300
            elif tujuan.lower() == 'cutting': target_kal = tdee - 300
            else: target_kal = tdee
            protein = bb * 1.8 if tujuan.lower() == 'bulking' else bb * 2.2
            lemak = target_kal * 0.25 / 9
            karbo = (target_kal - protein*4 - lemak*9) / 4
            
            db = load_db()
            user_id = str(update.message.from_user.id)
            db[user_id]['profile'] = {
                'bb': bb, 'tb': tb, 'umur': umur, 'gender': gender, 'tujuan': tujuan,
                'target_kalori': round(target_kal), 'target_protein': round(protein),
                'target_lemak': round(lemak), 'target_karbo': round(karbo),
                'kalori_masuk': 0, 'protein_masuk': 0, 'lemak_masuk': 0, 'karbo_masuk': 0
            }
            save_db(db)
            context.user_data['awaiting_profile'] = False
            await update.message.reply_text(
                f"Ok data kesimpen. Jangan sampe boong.\n\n"
                f"Target lu: {round(target_kal)} kkal, Protein: {round(protein)}g\n\n"
                f"Sekarang kirim foto. Bandel = gua catet dosanya."
            )
        except:
            await update.message.reply_text("SALAH FORMAT TOLOL. Contoh: `65 170 22 Laki bulking`")

async def keluhan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = get_user_data(update.message.from_user.id)
    if not user_data['profile']:
        await update.message.reply_text("SETPROFILE DULU KOCAK. DATA AJA KAGA ADA MAU NGELUH.")
        return
    if not context.args:
        await update.message.reply_text("KELUHANNYA APA BEGO? `/keluhan jerawat` gitu.")
        return
    
    keluhan_text = " ".join(context.args).lower()
    msg = await update.message.reply_text(f"Nyari obat buat {keluhan_text} lu ya... Liat dulu dosa lu...")
    
    db = load_db()
    user_id = str(update.message.from_user.id)
    if keluhan_text not in db[user_id]['riwayat_keluhan']:
        db[user_id]['riwayat_keluhan'].append(keluhan_text)
        db[user_id]['riwayat_keluhan'] = db[user_id]['riwayat_keluhan'][-10:]
    save_db(db)
    
    riwayat_lama = ", ".join(db[user_id]['riwayat_keluhan'][:-1]) if len(db[user_id]['riwayat_keluhan']) > 1 else "Sok sehat"
    omelan = pilih_omelan(db[user_id]['pelanggaran'])
    
    prompt = PROMPT_KELUHAN.format(
        keluhan=keluhan_text, bb=db[user_id]['profile']['bb'], tb=db[user_id]['profile']['tb'], 
        umur=db[user_id]['profile']['umur'], tujuan=db[user_id]['profile']['tujuan'],
        riwayat_lama=riwayat_lama, pelanggaran=db[user_id]['pelanggaran'], omelan=omelan
    )
    try:
        response = model.generate_content(prompt)
        await msg.edit_text(f"**DIAGNOSA BUAT SI {keluhan_text.upper()}**\n\n{response.text}", parse_mode='Markdown')
    except Exception as e:
        await msg.edit_text(f"ERROR ANJIR: {e}")

async def riwayat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = get_user_data(update.message.from_user.id)
    text = f"**CATETAN DOSA LU**\n\n"
    text += f"**Keluhan:**\n" + "\n".join([f"- {k}" for k in user_data['riwayat_keluhan']]) if user_data['riwayat_keluhan'] else "- Sok sehat lu\n"
    text += f"\n\n**Makanan Hari Ini:**\n" + "\n".join([f"- {m['nama']} {m['kalori']}kkal" for m in user_data['log_makanan']]) if user_data['log_makanan'] else "- Belom makan. Mau pingsan?\n"
    text += f"\n\n**Bandel Hari Ini:** {user_data['pelanggaran']}x\n**Total Dosa Lifetime:** {user_data['total_dosa']}x\n\nTobat kaga lu?"
    await update.message.reply_text(text, parse_mode='Markdown')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = get_user_data(update.message.from_user.id)
    if not user_data['profile']:
        await update.message.reply_text("SETPROFILE DULU BEGO. MAU GUA TERWANG?")
        return
    msg = await update.message.reply_text("Sini gua cek... makanan haram apa lagi ini...")
    photo_path = f"temp_{update.message.from_user.id}.jpg"
    try:
        photo_file = await update.message.photo[-1].get_file()
        await photo_file.download_to_drive(photo_path)
        deskripsi_user = update.message.caption or "Porsi standar katanya"
        img = PIL.Image.open(photo_path)
        
        db = load_db()
        user_id = str(update.message.from_user.id)
        p = db[user_id]['profile']
        keluhan_user = ", ".join(db[user_id]['riwayat_keluhan'][-3:]) if db[user_id]['riwayat_keluhan'] else "sok sehat"
        omelan = pilih_omelan(db[user_id]['pelanggaran'])
        
        prompt = PROMPT_ANALISIS_FOTO.format(
            bb=p['bb'], tb=p['tb'], tujuan=p['tujuan'],
            target_kalori=p['target_kalori'], kalori_masuk=p['kalori_masuk'],
            keluhan_user=keluhan_user, deskripsi_user=deskripsi_user,
            pelanggaran=db[user_id]['pelanggaran'], total_dosa=db[user_id]['total_dosa'],
            omelan=omelan
        )
        
        response = model.generate_content([prompt, img])
        result_text = response.text.replace("```json", "").replace("```", "")
        result = json.loads(result_text)
        
        db[user_id]['profile']['kalori_masuk'] += result['kalori']
        db[user_id]['profile']['protein_masuk'] += result['protein']
        db[user_id]['profile']['lemak_masuk'] += result['lemak']
        db[user_id]['profile']['karbo_masuk'] += result['karbo']
        db[user_id]['log_makanan'].append({'nama': result['nama_makanan'], 'waktu': datetime.now().strftime("%H:%M"), 'kalori': result['kalori']})
        if result.get('melanggar', False):
            db[user_id]['pelanggaran'] += 1
            db[user_id]['total_dosa'] += 1
        save_db(db)
        
        joke = random.choice(PANTUN_ROASTING) if random.random() < 0.4 else ""
        await msg.edit_text(result['analisis_lengkap'] + joke, parse_mode='Markdown')
    except Exception as e:
        logging.error(e)
        await msg.edit_text(f"ERROR KOCAK: {e}. FOTONYA YANG BENER NAPA.")
    finally:
        if os.path.exists(photo_path): os.remove(photo_path)

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setprofile", setprofile))
    app.add_handler(CommandHandler("keluhan", keluhan))
    app.add_handler(CommandHandler("riwayat", riwayat))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Bot GiziFoto Brutal aktif! Siap nyemprot user.")
    app.run_polling()

if __name__ == "__main__":
    main()
