import os
import sqlite3
import requests
import base64
import telebot
from telebot import types
import threading
from flask import Flask

# ================= [ FLASK WEB SERVER FOR RENDER (NO SLEEP) ] =================
app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7 without sleeping!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ================= [ CONFIGURATION ] =================
BOT_TOKEN = "8855766112:AAFrm_h0BnN8ADOruSFasB0HKUOUum09N_4"
ADMIN_ID = 8701781484

GITHUB_TOKEN = os.getenv("GH_TOKEN") if os.getenv("GH_TOKEN") else "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"
REPO_OWNER = "GodForYou2" 
REPO_NAME = "Approval" 
FILE_PATH = "key.txt" 
RESELLER_FILE_PATH = "resellers.txt" 

bot = telebot.TeleBot(BOT_TOKEN)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

# --- GitHub မှ Key ရော Reseller ပါ ဒေတာပြန်ဆွဲယူမည့် (Auto-Restore) စနစ် ---
def pull_data_from_github():
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    headers["Accept"] = "application/vnd.github.v3+json"
    
    # 1. Pull Keys Data
    try:
        url_keys = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        res_k = requests.get(url_keys, headers=headers)
        file_content_keys = None
        
        if res_k.status_code == 200:
            content_b64 = res_k.json().get("content", "")
            if content_b64:
                file_content_keys = base64.b64decode(content_b64).decode("utf-8")
        else:
            raw_url_keys = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{FILE_PATH}"
            res_raw_k = requests.get(raw_url_keys)
            if res_raw_k.status_code == 200:
                file_content_keys = res_raw_k.text

        if file_content_keys:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM auth_keys")
            for line in file_content_keys.split("\n"):
                if " | " in line:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) == 4:
                        cursor.execute("""
                            INSERT OR IGNORE INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by) 
                            VALUES (?, ?, ?, ?, ?)
                        """, (parts[0], parts[1], parts[2], parts[3], ADMIN_ID))
            conn.commit()
            conn.close()
            print("[+] Success: Keys data restored.")
    except Exception as e: print(f"[-] Keys Pull Exception: {str(e)}")

    # 2. Pull Resellers Data
    try:
        file_content_resellers = None
        url_resellers = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{RESELLER_FILE_PATH}"
        res_r = requests.get(url_resellers, headers=headers)
        
        if res_r.status_code == 200:
            content_b64 = res_r.json().get("content", "")
            if content_b64:
                file_content_resellers = base64.b64decode(content_b64).decode("utf-8")
        else:
            raw_url_resellers = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{RESELLER_FILE_PATH}"
            res_raw_r = requests.get(raw_url_resellers)
            if res_raw_r.status_code == 200:
                file_content_resellers = res_raw_r.text

        if file_content_resellers:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            # ဒေတာဟောင်း ရှင်းထုတ်သည်
            cursor.execute("DELETE FROM users WHERE tg_id != ?", (ADMIN_ID,))
            
            lines = file_content_resellers.split("\n")
            for line in lines:
                line = line.strip()
                if not line: continue
                
                if "|" in line:
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) == 2:
                        clean_id = parts[0].replace(" ", "")
                        if clean_id.isdigit():
                            target_tg_id = int(clean_id)
                            user_role = 'admin' if target_tg_id == ADMIN_ID else 'reseller'
                            cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role) VALUES (?, ?, ?)", (target_tg_id, parts[1], user_role))
            
            # Main Admin ကို Database ထဲတွင် အမြဲရှိနေအောင် သေချာ ထည့်သွင်းထားမည်
            cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role) VALUES (?, ?, 'admin')", (ADMIN_ID, 'Main_Admin'))
            conn.commit()
            conn.close()
            print("[+] Success: Resellers database updated smoothly.")
        else:
            print("[-] Error: Could not fetch resellers data from GitHub.")
    except Exception as e: print(f"[-] Resellers Pull Exception: {str(e)}")

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS auth_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        target_id TEXT,
        key_string TEXT UNIQUE, 
        unit_val TEXT, 
        duration_type TEXT, 
        added_by INTEGER
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        tg_id INTEGER PRIMARY KEY, 
        username TEXT, 
        role TEXT
    )''')
    cursor.execute("INSERT OR IGNORE INTO users (tg_id, username, role) VALUES (?, ?, ?)", (ADMIN_ID, 'Main_Admin', 'admin'))
    conn.commit()

    cursor.execute("PRAGMA table_info(auth_keys)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'target_id' not in columns:
        try:
            cursor.execute("ALTER TABLE auth_keys ADD COLUMN target_id TEXT")
            conn.commit()
        except: pass
    if 'unit_val' not in columns:
        try:
            cursor.execute("ALTER TABLE auth_keys ADD COLUMN unit_val TEXT")
            cursor.execute("ALTER TABLE auth_keys ADD COLUMN duration_type TEXT")
            conn.commit()
        except: pass
    conn.close()

init_db()
pull_data_from_github()

# --- GitHub Auto Sync Functions ---
def sync_db_to_github():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys")
        rows = cursor.fetchall()
        conn.close()
        
        content_lines = []
        for row in rows:
            tid = row[0] if row[0] else "NoID"
            kstr = row[1] if row[1] else "NoKey"
            uval = row[2] if row[2] else "0"
            dtype = row[3] if row[3] else "d"
            content_lines.append(f"{tid} | {kstr} | {uval} | {dtype}")
            
        file_content = "\n".join(content_lines)
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        
        res = requests.get(url, headers=headers)
        sha = res.json().get('sha') if res.status_code == 200 else None
        payload = {
            "message": "Bot Auto Sync Keys",
            "content": base64.b64encode(file_content.encode('utf-8')).decode('utf-8')
        }
        if sha: payload["sha"] = sha
        requests.put(url, headers=headers, json=payload)
        return True
    except Exception as e:
        print(f"[-] Keys Sync Error: {str(e)}")
        return False

def sync_resellers_to_github():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id, username FROM users")
        rows = cursor.fetchall()
        conn.close()
        
        content_lines = []
        for row in rows:
            content_lines.append(f"{row[0]} | {row[1]}")
            
        file_content = "\n".join(content_lines)
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{RESELLER_FILE_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        
        res = requests.get(url, headers=headers)
        sha = res.json().get('sha') if res.status_code == 200 else None
        payload = {
            "message": "Bot Auto Sync Resellers List",
            "content": base64.b64encode(file_content.encode('utf-8')).decode('utf-8')
        }
        if sha: payload["sha"] = sha
        requests.put(url, headers=headers, json=payload)
        return True
    except Exception as e:
        print(f"[-] Resellers Sync Error: {str(e)}")
        return False

# --- Roles & Permissions Checks ---
def is_admin(user_id): 
    return user_id == ADMIN_ID

def is_reseller(user_id):
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE tg_id = ? AND role = 'reseller'", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def get_key_owner_by_id(target_id_str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT added_by FROM auth_keys WHERE target_id = ?", (target_id_str,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_user_name(user_id):
    if user_id == ADMIN_ID: return "Main_Admin"
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE tg_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else f"Unknown ({user_id})"

# --- Custom Menu Keyboard ---
def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("➕ Add Key", "🔑 My Keys", "✏️ Edit Key", "🗑 Delete Key")
    if is_admin(user_id):
        markup.add("👤 Create Reseller", "📊 Reseller List", "🗑 Delete Reseller", "🌐 View All Keys")
    return markup

user_states = {}
reseller_temp_data = {}
MENU_BUTTONS = ["➕ Add Key", "🔑 My Keys", "✏️ Edit Key", "🗑 Delete Key", "👤 Create Reseller", "📊 Reseller List", "🗑 Delete Reseller", "🌐 View All Keys"]

# ================= [ BOT HANDLERS ] =================

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    user_states[user_id] = None 
    pull_data_from_github()
    if not is_reseller(user_id):
        bot.reply_to(message, "🚫 သင်သည် စနစ်သုံးခွင့်မရှိသေးပါ။ Admin ထံ ခွင့်ပြုချက်တောင်းပါ။")
        return
    bot.send_message(message.chat.id, "👋 မင်္ဂလာပါ! အောက်ပါ Menu ခလုတ်များကို အသုံးပြုနိုင်ပါပြီ။", reply_markup=get_main_keyboard(user_id))

# 1. Create Reseller
@bot.message_handler(func=lambda msg: msg.text == "👤 Create Reseller" and is_admin(msg.from_user.id))
def admin_create_reseller(message):
    user_states[message.from_user.id] = 'waiting_for_reseller_id'
    bot.reply_to(message, "👤 Reseller အသစ်လုပ်မည့်သူ၏ **Telegram User ID** (ဂဏန်းသီးသန့်) ကို ပို့ပေးပါ-", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'waiting_for_reseller_id' and msg.text not in MENU_BUTTONS)
def process_reseller_id(message):
    admin_id = message.from_user.id
    try:
        reseller_id = int(message.text.strip())
        reseller_temp_data[admin_id] = reseller_id
        user_states[admin_id] = 'waiting_for_reseller_name'
        bot.reply_to(message, f"✍️ ID `{reseller_id}` အတွက် သတ်မှတ်မည့် **Reseller နာမည်** ကို ပို့ပေးပါ-", parse_mode="Markdown")
    except: 
        bot.reply_to(message, "❌ မှားယွင်းနေပါသည်။ Telegram ID (ဂဏန်းသီးသန့်) ကိုသာ ပို့ပေးပါ။")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'waiting_for_reseller_name' and msg.text not in MENU_BUTTONS)
def process_reseller_name(message):
    admin_id = message.from_user.id
    reseller_name = message.text.strip()
    reseller_id = reseller_temp_data.get(admin_id)

    if not reseller_id:
        bot.reply_to(message, "❌ အချိန်လွန်သွားပါပြီ။ လူသစ်ပြန်ဆောက်ပေးပါ။")
        user_states[admin_id] = None
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role) VALUES (?, ?, 'reseller')", (reseller_id, reseller_name))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ **အောင်မြင်ပါသည်!**\n👤 နာမည်: `{reseller_name}`\n🆔 ID: `{reseller_id}` အား Reseller ခန့်အပ်ပြီးပါပြီ။ Cloud သို့ အော်တိုသိမ်းဆည်းနေပါသည်...", parse_mode="Markdown")
        sync_resellers_to_github()
        
    except Exception as e:
        bot.reply_to(message, f"❌ သိမ်းဆည်းရာတွင် အမှားအယွင်းရှိခဲ့သည်- {str(e)}")
    
    user_states[admin_id] = None
    if admin_id in reseller_temp_data: del reseller_temp_data[admin_id]

# 2. Reseller List (Special Character Error များကို ကျော်လွှားရန် HTML စနစ်သို့ ပြောင်းလဲထားသည်)
@bot.message_handler(func=lambda msg: msg.text == "📊 Reseller List")
def admin_view_resellers(message):
    user_id = message.from_user.id
    user_states[user_id] = None
    
    if not is_admin(user_id):
        return bot.reply_to(message, "🚫 သင်သည် Admin မဟုတ်သဖြင့် ဤစာရင်းအား ကြည့်ရှုခွင့် မရှိပါ။")
        
    pull_data_from_github()
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id, username, role FROM users")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows: 
            return bot.reply_to(message, "📭 Database ထဲတွင် အသုံးပြုသူစာရင်း လုံးဝမရှိသေးပါ။")
        
        # HTML formatting သုံးပြီး Telegram စာသားပုံစံ ပြင်ဆင်သည်
        res = f"👥 <b>အသုံးပြုသူ စာရင်းစုစုပေါင်း:</b> {len(rows)} ဦး\n\n"
        for r in rows:
            role_tag = "👑 Admin" if r[2] == 'admin' else "👤 Reseller"
            # နာမည်ထဲတွင် 特殊符号များ ပါခဲ့ပါက ကာကွယ်ရန် HTML escape အနည်းငယ် သုံးသည်
            clean_name = str(r[1]).replace("<", "&lt;").replace(">", "&gt;")
            res += f"• <b>{clean_name}</b> (ID: {r[0]}) - [{role_tag}]\n"
            
        bot.reply_to(message, res, parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"❌ စာရင်းထုတ်ရာတွင် Error တစ်ခု တက်သွားပါသည်: {str(e)}")

# 3. Delete Reseller
@bot.message_handler(func=lambda msg: msg.text == "🗑 Delete Reseller" and is_admin(msg.from_user.id))
def admin_delete_reseller_menu(message):
    user_states[message.from_user.id] = None
    pull_data_from_github()
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT tg_id, username FROM users WHERE role = 'reseller'")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 ဖျက်ရန် Reseller စာရင်း မရှိသေးပါ။")

    markup = types.InlineKeyboardMarkup(row_width=1)
    for r in rows:
        markup.add(types.InlineKeyboardButton(text=f"❌ {r[1]} (ID: {r[0]})", callback_data=f"del_reseller_{r[0]}"))
    bot.send_message(message.chat.id, "🗑 **ဖျက်ထုတ်လိုသော Reseller နာမည်အား နှိပ်ပါ-**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_reseller_"))
def callback_delete_reseller(call):
    if not is_admin(call.from_user.id): return bot.answer_callback_query(call.id, "🚫 သင်သည် Admin မဟုတ်သဖြင့် ဖျက်ခွင့်မရှိပါ။")
    reseller_id = int(call.data.replace("del_reseller_", ""))
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE tg_id = ?", (reseller_id,))
        name_row = cursor.fetchone()
        r_name = name_row[0] if name_row else f"{reseller_id}"
        cursor.execute("DELETE FROM users WHERE tg_id = ?", (reseller_id,))
        conn.commit()
        conn.close()
        
        sync_resellers_to_github()
        
        bot.answer_callback_query(call.id, f"✅ {r_name} အား ဖြုတ်ချပြီးပါပြီ။")
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                              text=f"🗑 **အောင်မြင်ပါသည်!**\n👤 Reseller: `_{r_name}_` (ID: `{reseller_id}`) အား စနစ်အတွင်းမှ ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="Markdown")
    except Exception as e: bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

# 4. View All Keys
@bot.message_handler(func=lambda msg: msg.text == "🌐 View All Keys" and is_admin(msg.from_user.id))
def admin_view_all_keys(message):
    user_states[message.from_user.id] = None
    pull_data_from_github()
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, unit_val, duration_type, added_by FROM auth_keys")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 Database ထဲတွင် Key မရှိသေးပါ။")
    res = f"🌐 **Database အတွင်းရှိ Key အားလုံးစာရင်း ({len(rows)} ခု):**\n\n"
    for r in rows: 
        owner_name = get_user_name(r[4])
        res += f"🆔 `{r[0]}` | 🔑 `{r[1]}` | {r[2]} | {r[3]} (By: *{owner_name}*)\n"
    bot.reply_to(message, res, parse_mode="Markdown")

# 5. Add Key
@bot.message_handler(func=lambda msg: msg.text == "➕ Add Key" and is_reseller(msg.from_user.id))
def cmd_addkey(message):
    user_states[message.from_user.id] = 'waiting_for_key'
    msg_text = ("✍️ ကျေးဇူးပြု၍ Key အချက်အလက်ကို အောက်ပါပုံစံအတိုင်း တိကျစွာ ပို့ပေးပါ-\n\n`ID | Key | Unit | Duration`\n\n💡 **ပုံစံနမူနာ:**\n• `F4AFA83F4F1577DE | XYZ-KEY-999 | 3 | d`")
    bot.reply_to(message, msg_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'waiting_for_key' and msg.text not in MENU_BUTTONS)
def process_key_data(message):
    user_id = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 4: return bot.reply_to(message, "❌ ပုံစံမမှန်ပါ။ `ID | Key | Unit | Duration` အတိုင်း ပြန်လည်ပေးပို့ပါ။")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by) VALUES (?, ?, ?, ?, ?)", (parts[0], parts[1], parts[2], parts[3], user_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ Key အချက်အလက် သိမ်းဆည်းပြီးပါပြီ။ Cloud သို့ လှမ်းပို့နေပါသည်...")
        sync_db_to_github()
        user_states[user_id] = None
    except: bot.reply_to(message, "❌ ဤ Key သည် Database ထဲမှာ ရှိနှင့်နေပြီးသား ဖြစ်ပါသည်။")

# 6. View My Keys
@bot.message_handler(func=lambda msg: msg.text == "🔑 My Keys" and is_reseller(msg.from_user.id))
def cmd_mykeys(message):
    user_states[message.from_user.id] = None
    pull_data_from_github()
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string FROM auth_keys WHERE added_by = ?", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 သင်ထည့်သွင်းထားသော Key မရှိသေးပါ။")
    res = "🔑 **သင်ထည့်သွင်းထားသော Key များ:**\n\n"
    for r in rows: res += f"• ID: `{r[0]}` -> Key: `{r[1]}`\n"
    bot.reply_to(message, res, parse_mode="Markdown")

# 7. Edit Key (Device ID အား အခြေခံ၍ ကျန်ရှိသော အချက်အလက် ၃ ခုလုံး ပြင်ဆင်သည့်စနစ်)
@bot.message_handler(func=lambda msg: msg.text == "✏️ Edit Key" and is_reseller(msg.from_user.id))
def cmd_editkey(message):
    user_states[message.from_user.id] = 'waiting_for_edit_data'
    msg_text = ("✏️ **ပြင်ဆင်လိုသော အချက်အလက်ကို အောက်ပါပုံစံအတိုင်း ပို့ပေးပါ-**\n\n"
                "`ရှာမည့်DeviceID | Keyသစ် | Unitသစ် | Durationသစ်`\n\n"
                "💡 **ပုံစံနမူနာ:**\n`F4AFA83F4F1577DE | NEW-KEY-888 | 5 | m`")
    bot.reply_to(message, msg_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'waiting_for_edit_data' and msg.text not in MENU_BUTTONS)
def process_edit_key(message):
    user_id = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 4: 
        user_states[user_id] = None # ပုံစံမမှန်ရင် State ပိတ်ပြီး ပြန်ထွက်သည်
        return bot.reply_to(message, "❌ ပုံစံမမှန်ပါ။ `DeviceID | Keyသစ် | Unitသစ် | Durationသစ်` အတိုင်း ပြန်လည်စစ်ဆေးပါ။")
    
    target_device_id = parts[0]  # ရှာဖွေမည့် Device ID
    new_key = parts[1]           # အစားထိုးမည့် Key သစ်
    new_unit = parts[2]          # အစားထိုးမည့် Unit သစ်
    new_duration = parts[3]      # အစားထိုးမည့် Duration သစ်
    
    pull_data_from_github()
    
    # ဤ Device ID ကို မည်သူက ထည့်သွင်းခဲ့သလဲ အရင်ရှာဖွေစစ်ဆေးသည်
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT added_by FROM auth_keys WHERE target_id = ?", (target_device_id,))
    result = cursor.fetchone()
    conn.close()
    
    owner_id = result[0] if result else None
    if owner_id is None: 
        user_states[user_id] = None
        return bot.reply_to(message, "❌ ဤ Device ID ကို Database ထဲတွင် ရှာမတွေ့ပါ။")
    if owner_id != user_id and not is_admin(user_id): 
        user_states[user_id] = None
        return bot.reply_to(message, "🚫 သင်သည် ဤ Key အား ပြင်ဆင်ခွင့်မရှိပါ။")
        
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # ရှေ့ဆုံးက Device ID ကို အခြေခံပြီး ကျန်တဲ့ Key, Unit, Duration သုံးခုလုံးကို လိုက်ပြင်သည့် Logic
        cursor.execute("""
            UPDATE auth_keys 
            SET key_string=?, unit_val=?, duration_type=? 
            WHERE target_id=?
        """, (new_key, new_unit, new_duration, target_device_id))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✏️ Device ID `{target_device_id}` ၏ အချက်အလက်များကို ပြင်ဆင်ပြီးပါပြီ။ Cloud သို့ Update လုပ်နေသည်...")
        sync_db_to_github()
        user_states[user_id] = None
    except Exception as e: 
        user_states[user_id] = None
        bot.reply_to(message, f"❌ ပြင်ဆင်မှု မှားယွင်းနေပါသည်- {str(e)}")

# 8. Delete Key
@bot.message_handler(func=lambda msg: msg.text == "🗑 Delete Key" and is_reseller(msg.from_user.id))
def cmd_delete_key_trigger(message):
    user_states[message.from_user.id] = 'waiting_for_del_id'
    bot.reply_to(message, "🗑 ဖျက်လိုသော **Device ID** (ဥပမာ - `F4AFA83F4F1577DE`) ကို ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'waiting_for_del_id' and msg.text not in MENU_BUTTONS)
def process_delete_key_by_id(message):
    user_id = message.from_user.id
    id_to_del = message.text.strip()
    
    pull_data_from_github()
    
    owner_id = get_key_owner_by_id(id_to_del)
    if owner_id is None: return bot.reply_to(message, f"❌ ID `{id_to_del}` အား ရှာမတွေ့ပါ။")
    if owner_id != user_id and not is_admin(user_id): return bot.reply_to(message, "🚫 ဖျက်ခွင့်မရှိပါ။")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM auth_keys WHERE target_id = ?", (id_to_del,))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ ID `{id_to_del}` ၏ Key အား ဖျက်ပြီးပါပြီ။ Cloud သို့ ပို့နေသည်...")
        sync_db_to_github()
        user_states[user_id] = None
    except Exception as e: bot.reply_to(message, f"❌ Error: {str(e)}")

# --- Main Run ---
if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    print("[+] Flask Web Server + Telegram Bot Running 24/7 on Render...")
    bot.infinity_polling()
