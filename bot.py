import os
import sqlite3
import telebot
import requests
import base64
from telebot import types
import threading
from flask import Flask

# ================= [ FLASK WEB SERVER FOR RENDER (NO SLEEP) ] =================
app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7 without sleeping!"

def run_web_server():
    app.run(host='0.0.0.0', port=8080)

# ================= [ CONFIGURATION ] =================
BOT_TOKEN = "8855766112:AAFrm_h0BnN8ADOruSFasB0HKUOUum09N_4"
ADMIN_ID = 8701781484

GITHUB_TOKEN = os.getenv("GH_TOKEN")
REPO_OWNER = "GodForYou2" 
REPO_NAME = "Approval" 
FILE_PATH = "key.txt" 

bot = telebot.TeleBot(BOT_TOKEN)

# Render ပေါ်တွင် လမ်းကြောင်းမလွဲစေရန် စနစ်တကျပြင်ဆင်ခြင်း
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

# --- GitHub မှ ဒေတာများကို လှမ်းယူပြီး Local DB ထဲသို့ ပြန်ထည့်ပေးမည့် Function ---
def pull_data_from_github():
    if not GITHUB_TOKEN:
        print("[-] Pull Error: GH_TOKEN is not set!")
        return
        
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            content_b64 = res.json().get("content", "")
            if content_b64:
                file_content = base64.b64decode(content_b64).decode("utf-8")
                
                # Local Database ထဲသို့ ဒေတာများ ပြန်လည် ထည့်သွင်းခြင်း
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                
                # အဟောင်းများကို ရှင်းထုတ်ပြီး GitHub က ဒေတာအသစ်တွေပဲ အစားထိုးမည်
                cursor.execute("DELETE FROM keys")
                
                for line in file_content.split("\n"):
                    if " | " in line:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) == 4:
                            cursor.execute("INSERT OR IGNORE INTO keys (target_id, key_string, unit_val, duration_type, added_by) VALUES (?, ?, ?, ?, ?)",
                                           (parts[0], parts[1], parts[2], parts[3], ADMIN_ID))
                conn.commit()
                conn.close()
                print("[+] Success: GitHub Data pulled and restored to Local DB.")
        else:
            print(f"[-] Pull Failed: Status {res.status_code}")
    except Exception as e:
        print(f"[-] Pull Exception: {str(e)}")

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id TEXT,
        key_string TEXT UNIQUE,
        unit_val TEXT,
        duration_type TEXT,
        added_by INTEGER
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS auth_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id TEXT,
        key_string TEXT UNIQUE,
        unit_val TEXT,
        duration_type TEXT,
        added_by INTEGER
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (
        tg_id INTEGER PRIMARY KEY,
        username TEXT,
        role TEXT
    )''')
    conn.commit()
    
    try:
        cursor.execute("INSERT OR IGNORE INTO admins (tg_id, username, role) VALUES (?, ?, ?)", 
                       (ADMIN_ID, "Creator", "creator"))
        conn.commit()
    except Exception as e:
        print(f"Admin init error: {e}")
    finally:
        conn.close()

# Database ကို စဆောက်ပြီးတာနဲ့ GitHub က ဒေတာများကို အော်တိုဆွဲခိုင်းမည်
init_db()
pull_data_from_github()

# --- Helper Functions ---
def is_admin(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM admins WHERE tg_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def sync_to_github():
    if not GITHUB_TOKEN:
        print("[-] Sync Error: GH_TOKEN is not set!")
        return False
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM keys")
    rows = cursor.fetchall()
    conn.close()
    
    content_lines = []
    for r in rows:
        content_lines.append(f"{r[0]} | {r[1]} | {r[2]} | {r[3]}")
    file_content = "\n".join(content_lines)
    
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    sha = None
    r_get = requests.get(url, headers=headers)
    if r_get.status_code == 200:
        sha = r_get.json().get("sha")
        
    content_b64 = base64.b64encode(file_content.encode("utf-8")).decode("utf-8")
    
    payload = {
        "message": "Bot Auto Sync Keys (Format: ID | Key | Unit | Duration)",
        "content": content_b64
    }
    if sha:
        payload["sha"] = sha
        
    r_put = requests.put(url, headers=headers, json=payload)
    return r_put.status_code in [200, 201]

# --- Telegram Bot Handlers ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if is_admin(user_id) or user_id == ADMIN_ID:
        btn_add = types.KeyboardButton("➕ Add Key")
        btn_list = types.KeyboardButton("📋 List Keys")
        btn_sync = types.KeyboardButton("🔄 Force Sync GitHub")
        markup.add(btn_add, btn_list, btn_sync)
        bot.send_message(message.chat.id, "👋 မင်္ဂလာပါ Admin ရှင့်။ Bot Control Panel မှ ကြိုဆိုပါတယ်၊၊", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "❌ သင့်မှာ ဤ Bot ကို အသုံးပြုခွင့် မရှိပါရှင်၊၊")

@bot.message_handler(func=lambda m: m.text == "🔄 Force Sync GitHub")
def force_sync(message):
    if not (is_admin(message.from_user.id) or message.from_user.id == ADMIN_ID): return
    bot.send_message(message.chat.id, "⏳ GitHub ဘက်နှင့် ဒေတာများ အပြန်အလှန် Sync လုပ်နေပါတယ်...")
    pull_data_from_github() 
    if sync_to_github():   
        bot.send_message(message.chat.id, "✅ ဒေတာအားလုံး အပြန်အလှန် ချိတ်ဆက်ကာ Update ဖြစ်သွားပါပြီဗျာ၊၊")
    else:
        bot.send_message(message.chat.id, "❌ GitHub Sync လုပ်ဆောင်ချက် ပျက်ကွက်ခဲ့ပါတယ်။")

@bot.message_handler(func=lambda m: m.text == "➕ Add Key")
def add_key_start(message):
    if not (is_admin(message.from_user.id) or message.from_user.id == ADMIN_ID): return
    msg = bot.send_message(message.chat.id, "📝 ကျေးဇူးပြု၍ Key ဒေတာကို အောက်ပါ Format အတိုင်း ပေးပို့ပေးပါဦးခင်ဗျာ-\n\n`ID | Key | Unit | Duration`\n\n*(ဥပမာ - `12345 | MY-KEY-999 | 1 | Day`)*", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_key_input)

def process_key_input(message):
    if not (is_admin(message.from_user.id) or message.from_user.id == ADMIN_ID): return
    
    text = message.text
    if " | " not in text:
        bot.send_message(message.chat.id, "❌ ပို့လိုက်တဲ့ Format မမှန်ကန်ပါဘူး။")
        return
        
    parts = [p.strip() for p in text.split("|")]
    if len(parts) != 4:
        bot.send_message(message.chat.id, "❌ အချက်အလက် (၄) ခု ပြည့်စုံအောင် ထည့်ပေးရပါမယ်ရှင်၊၊")
        return
        
    target_id, key_string, unit_val, duration_type = parts
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO keys (target_id, key_string, unit_val, duration_type, added_by) VALUES (?, ?, ?, ?, ?)",
                       (target_id, key_string, unit_val, duration_type, message.from_user.id))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"📥 Local Database ထဲသို့ သိမ်းဆည်းပြီးပါပြီ။\n🔑 Key: `{key_string}`\n\n⏳ GitHub သို့ Auto-Sync လုပ်နေပါတယ်...", parse_mode="Markdown")
        
        if sync_to_github():
            bot.send_message(message.chat.id, "🚀 GitHub ပေါ်က `key.txt` ထဲသို့လည်း ဒေတာ ရောက်ရှိသွားပါပြီဗျာ၊၊")
        else:
            bot.send_message(message.chat.id, "⚠️ Local DB ထဲပဲ သိမ်းမိပြီး GitHub ဆီသို့ ဒေတာမရောက်သွားပါ။")
            
    except sqlite3.IntegrityError:
        bot.send_message(message.chat.id, "❌ ဤ Key သည် Database ထဲတွင် ရှိနှင့်ပြီးသား ဖြစ်နေပါတယ်ရှင်၊၊")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error တက်သွားပါသည်- {str(e)}")

@bot.message_handler(func=lambda m: m.text == "📋 List Keys")
def list_keys(message):
    if not (is_admin(message.from_user.id) or message.from_user.id == ADMIN_ID): return
    
    pull_data_from_github()
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM keys")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        bot.send_message(message.chat.id, "📭 လောလောဆယ် Database ထဲမှာ မည်သည့် Key မှ မရှိသေးပါရှင်၊၊")
        return
        
    res_text = "🔑 **လက်ရှိသိမ်းထားသော Key များ စာရင်း**\n\n"
    for i, r in enumerate(rows, start=1):
        res_text += f"{i}. ID: `{r[0]}` | Key: `{r[1]}` | `{r[2]} {r[3]}`\n"
        
    bot.send_message(message.chat.id, res_text, parse_mode="Markdown")

# ================= [ MAIN EXECUTION ] =================
if __name__ == "__main__":
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()
    
    print(f"[+] Render Auto-Restore Bot is running...")
    bot.infinity_polling()
