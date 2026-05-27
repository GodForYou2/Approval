import os
import sqlite3
import requests
import base64
import telebot
from telebot import types
import threading
from flask import Flask
from datetime import datetime

# ================= [ FLASK WEB SERVER FOR RENDER (NO SLEEP) ] =================
# YG- ID များကို ထည့်ခွင့်ပြုထားသော User ID များ
# ဥပမာ - 7695807003 (Rhiso) ကို ထည့်ခွင့်ပေးချင်တယ်ဆိုရင်
SPECIAL_RESELLERS = {8760362205, 1278003270}
app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7 without sleeping!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ================= [ CONFIGURATION ] =================
BOT_TOKEN =  os.getenv("BT_TOKEN")
ADMIN_ID = 8701781484
DEFAULT_LIMIT = 5  # ကုဒ်ဟောင်းမှ ဒေတာများအတွက် အော်တိုသတ်မှတ်ပေးမည့် Limit ဟောင်း

GITHUB_TOKEN = os.getenv("GH_TOKEN") 
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
                    created_date = datetime.now().strftime("%Y-%m-%d")
                    if len(parts) == 6:
                        try: owner_id = int(parts[4])
                        except: owner_id = ADMIN_ID
                        created_date = parts[5]
                        cursor.execute("""
                            INSERT OR IGNORE INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at) 
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (parts[0], parts[1], parts[2], parts[3], owner_id, created_date))
                    elif len(parts) == 5:
                        try: owner_id = int(parts[4])
                        except: owner_id = ADMIN_ID
                        cursor.execute("""
                            INSERT OR IGNORE INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at) 
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (parts[0], parts[1], parts[2], parts[3], owner_id, created_date))
                    elif len(parts) == 4:
                        cursor.execute("""
                            INSERT OR IGNORE INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at) 
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (parts[0], parts[1], parts[2], parts[3], ADMIN_ID, created_date))
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
            
            cursor.execute("DELETE FROM users WHERE tg_id != ?", (ADMIN_ID,))
            
            lines = file_content_resellers.split("\n")
            for line in lines:
                line = line.strip()
                if not line: continue
                
                if "|" in line:
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) == 3:
                        clean_id = parts[0].replace(" ", "")
                        if clean_id.isdigit():
                            target_tg_id = int(clean_id)
                            user_role = 'admin' if target_tg_id == ADMIN_ID else 'reseller'
                            try: r_limit = int(parts[2])
                            except: r_limit = DEFAULT_LIMIT
                            cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, daily_limit) VALUES (?, ?, ?, ?)", (target_tg_id, parts[1], user_role, r_limit))
                    elif len(parts) == 2:
                        clean_id = parts[0].replace(" ", "")
                        if clean_id.isdigit():
                            target_tg_id = int(clean_id)
                            user_role = 'admin' if target_tg_id == ADMIN_ID else 'reseller'
                            cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, daily_limit) VALUES (?, ?, ?, ?)", (target_tg_id, parts[1], user_role, DEFAULT_LIMIT))
            
            cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, daily_limit) VALUES (?, ?, 'admin', 999999)", (ADMIN_ID, 'Main_Admin'))
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
        target_id TEXT UNIQUE,
        key_string TEXT, 
        unit_val TEXT, 
        duration_type TEXT, 
        added_by INTEGER,
        created_at TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        tg_id INTEGER PRIMARY KEY, 
        username TEXT, 
        role TEXT,
        daily_limit INTEGER DEFAULT 5
    )''')
    cursor.execute("INSERT OR IGNORE INTO users (tg_id, username, role, daily_limit) VALUES (?, ?, ?, ?)", (ADMIN_ID, 'Main_Admin', 'admin', 999999))
    
    try: cursor.execute("ALTER TABLE auth_keys ADD COLUMN created_at TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN daily_limit INTEGER DEFAULT 5")
    except: pass
        
    conn.commit()
    conn.close()

init_db()
pull_data_from_github()

# --- GitHub Auto Sync Functions ---
def sync_db_to_github():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, unit_val, duration_type, added_by, created_at FROM auth_keys")
        rows = cursor.fetchall()
        conn.close()
        
        content_lines = []
        for row in rows:
            tid = row[0] if row[0] else "NoID"
            kstr = row[1] if row[1] else "NoKey"
            uval = row[2] if row[2] else "0"
            dtype = row[3] if row[3] else "d"
            owner = row[4] if row[4] else str(ADMIN_ID)
            cdate = row[5] if row[5] else datetime.now().strftime("%Y-%m-%d")
            content_lines.append(f"{tid} | {kstr} | {uval} | {dtype} | {owner} | {cdate}")
            
        file_content = "\n".join(content_lines)
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        
        res = requests.get(url, headers=headers)
        sha = res.json().get('sha') if res.status_code == 200 else None
        payload = {
            "message": "Bot Auto Sync Keys with Date Limits",
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
        cursor.execute("SELECT tg_id, username, daily_limit FROM users")
        rows = cursor.fetchall()
        conn.close()
        
        content_lines = []
        for row in rows:
            content_lines.append(f"{row[0]} | {row[1]} | {row[2]}")
            
        file_content = "\n".join(content_lines)
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{RESELLER_FILE_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        
        res = requests.get(url, headers=headers)
        sha = res.json().get('sha') if res.status_code == 200 else None
        payload = {
            "message": "Bot Auto Sync Resellers List with custom limits",
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

def get_reseller_daily_limit(user_id):
    if user_id == ADMIN_ID: return 999999
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT daily_limit FROM users WHERE tg_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else DEFAULT_LIMIT

def get_today_added_count(user_id):
    today_str = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM auth_keys WHERE added_by = ? AND created_at = ?", (user_id, today_str))
    count = cursor.fetchone()[0]
    conn.close()
    return count

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
        reseller_temp_data[admin_id] = {'id': reseller_id}
        user_states[admin_id] = 'waiting_for_reseller_name'
        bot.reply_to(message, f"✍️ ID `{reseller_id}` အတွက် သတ်မှတ်မည့် **Reseller နာမည်** ကို ပို့ပေးပါ-", parse_mode="Markdown")
    except: 
        bot.reply_to(message, "❌ မှားယွင်းနေပါသည်။ Telegram ID (ဂဏန်းသီးသန့်) ကိုသာ ပို့ပေးပါ။")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'waiting_for_reseller_name' and msg.text not in MENU_BUTTONS)
def process_reseller_name(message):
    admin_id = message.from_user.id
    reseller_name = message.text.strip()
    
    if admin_id not in reseller_temp_data:
        bot.reply_to(message, "❌ အချိန်လွန်သွားပါပြီ။ အစမှ ပြန်ဆောက်ပေးပါ။")
        user_states[admin_id] = None
        return

    reseller_temp_data[admin_id]['name'] = reseller_name
    user_states[admin_id] = 'waiting_for_reseller_limit'
    bot.reply_to(message, f"📊 နာမည် `_{reseller_name}_` အတွက် တစ်ရက်လျှင် ထည့်သွင်းခွင့်ပြုမည့် **Key အရေအတွက် အကန့်အသတ် (Limit)** ကို ဂဏန်းသီးသန့် ပို့ပေးပါ-", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'waiting_for_reseller_limit' and msg.text not in MENU_BUTTONS)
def process_reseller_limit(message):
    admin_id = message.from_user.id
    
    if admin_id not in reseller_temp_data or 'id' not in reseller_temp_data[admin_id]:
        bot.reply_to(message, "❌ အချက်အလက် မှားယွင်းသွားပါပြီ။ လူသစ်ပြန်ဆောက်ပေးပါ။")
        user_states[admin_id] = None
        return
        
    try:
        r_limit = int(message.text.strip())
        reseller_id = reseller_temp_data[admin_id]['id']
        reseller_name = reseller_temp_data[admin_id]['name']
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, daily_limit) VALUES (?, ?, 'reseller', ?)", (reseller_id, reseller_name, r_limit))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ **အောင်မြင်ပါသည်!**\n👤 နာမည်: `{reseller_name}`\n🆔 ID: `{reseller_id}`\n📊 Daily Limit: `{r_limit} ခု` အား သတ်မှတ်ပြီးပါပြီ။ Cloud သို့ သိမ်းဆည်းနေပါသည်...", parse_mode="Markdown")
        sync_resellers_to_github()
        
    except:
        bot.reply_to(message, "❌ မှားယွင်းနေပါသည်။ Key အရေအတွက် ကန့်သတ်ချက်ကို ဂဏန်းသီးသန့်သာ ပို့ပေးပါ။")
        return
        
    user_states[admin_id] = None
    if admin_id in reseller_temp_data: del reseller_temp_data[admin_id]

# 2. Reseller List
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
        cursor.execute("SELECT tg_id, username, role, daily_limit FROM users")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows: 
            return bot.reply_to(message, "📭 Database ထဲတွင် အသုံးပြုသူစာရင်း လုံးဝမရှိသေးပါ။")
        
        res = f"👥 <b>အသုံးပြုသူ စာရင်းစုစုပေါင်း:</b> {len(rows)} ဦး\n\n"
        for r in rows:
            if r[2] == 'admin':
                role_tag = "👑 Admin"
                limit_str = "Unlimited"
            else:
                role_tag = "👤 Reseller"
                limit_str = f"{r[3]} ခု/ရက်"
                
            clean_name = str(r[1]).replace("<", "&lt;").replace(">", "&gt;")
            res += f"• <b>{clean_name}</b> (ID: {r[0]}) - [{role_tag}] (Limit: <code>{limit_str}</code>)\n"
            
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
        res += f"🆔 `{r[0]}` | 🔑 `{r[1]}` | {r[2]} | {r[3]} (By: *{owner_name}* - `{r[4]}`)\n"
    bot.reply_to(message, res, parse_mode="Markdown")

# 5. Add Key (🌟 Fix တာကွက် - bot.reply_to စာသားနေရာတွင် message ပိုဇစ်ရှင် ထည့်သွင်းပြင်ဆင်ပြီး)
@bot.message_handler(func=lambda msg: msg.text == "➕ Add Key" and is_reseller(msg.from_user.id))
def cmd_addkey(message):
    user_id = message.from_user.id
    pull_data_from_github()
    
    if not is_admin(user_id):
        user_limit = get_reseller_daily_limit(user_id)
        current_count = get_today_added_count(user_id)
        if current_count >= user_limit:
            bot.reply_to(message, f"❌ **တားဆီးထားပါသည်!**\n\nသင်သည် ယနေ့အတွက် သတ်မှတ်ထားသော သင့်ကိုယ်ပိုင် Key အကန့်အသတ် **{user_limit} ခု** ပြည့်သွားပါပြီ။ မနက်ဖြန်မှသာ ထပ်မံထည့်သွင်းနိုင်ပါမည်။", parse_mode="Markdown")
            return

    user_states[user_id] = 'waiting_for_key'
    msg_text = ("✍️ ကျေးဇူးပြု၍ Key အချက်အလက်ကို အောက်ပါပုံစံအတိုင်း တိကျစွာ ပို့ပေးပါ-\n\n`ID | Key | Unit | Duration`\n\n💡 **ပုံစံနမူနာ:**\n• `F4AFA83F4F1577DE | XYZ-KEY-999 | 3 | d`")
    bot.reply_to(message, msg_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'waiting_for_key' and msg.text not in MENU_BUTTONS)
def process_key_data(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        user_limit = get_reseller_daily_limit(user_id)
        if get_today_added_count(user_id) >= user_limit:
            user_states[user_id] = None
            return bot.reply_to(message, f"❌ သင်သည် ယနေ့အတွက် သတ်မှတ်ထားသော Key အကန့်အသတ် {user_limit} ခု ပြည့်သွားပါပြီ။")

    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 4: 
        return bot.reply_to(message, "❌ ပုံစံမမှန်ပါ။ `ID | Key | Unit | Duration` အတိုင်း ပြန်လည်ပေးပို့ပါ။")
    
    target_id = parts[0]
    # 🌟 Admin မဟုတ်သူများအတွက် YG- ID တားဆီးခြင်း
    if not is_admin(user_id) and user_id not in SPECIAL_RESELLERS and target_id.startswith("YG-"):
        user_states[user_id] = None
        return bot.reply_to(message, "❌ **Internet Bypass reseller ဝယ်ယူပါ ")
    today_date_str = datetime.now().strftime("%Y-%m-%d")
    
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        cursor = conn.cursor()
        
        cursor.execute("SELECT 1 FROM auth_keys WHERE target_id = ?", (target_id,))
        existing_id = cursor.fetchone()
        
        if existing_id:
            conn.close()
            user_states[user_id] = None
            return bot.reply_to(message, "❌ ဤ Device ID သည် Database ထဲတွင် ရှိနှင့်နေပြီးသား ဖြစ်သဖြင့် ထပ်ထည့်၍မရပါ။")
            
        cursor.execute(
            "INSERT INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at) VALUES (?, ?, ?, ?, ?, ?)", 
            (parts[0], parts[1], parts[2], parts[3], user_id, today_date_str)
        )
        conn.commit()
        conn.close()
        
        success_msg = "✅ Key အချက်အလက် သိမ်းဆည်းပြီးပါပြီ။ Cloud သို့ လှမ်းပို့နေပါသည်..."
        if not is_admin(user_id):
            user_limit = get_reseller_daily_limit(user_id)
            rem = user_limit - get_today_added_count(user_id)
            success_msg += f"\n\n📊 **ယနေ့အခြေအနေ:** ထည့်ပြီး {get_today_added_count(user_id)} ခု / ထပ်ထည့်နိုင်သေးသည် {rem} ခု (Limit: {user_limit} ခု)"
            
        # 🌟 ပြင်ဆင်ပြီးချက် - message ပိုဇစ်ရှင် argument ပြန်ထည့်ပေးလိုက်ပါပြီ
        bot.reply_to(message, success_msg)
        sync_db_to_github()
        
    except Exception as e:
        bot.reply_to(message, f"❌ စနစ်အတွင်း အမှားအယွင်း ဖြစ်ပွားခဲ့သည်- {str(e)}")
        
    finally:
        user_states[user_id] = None

# 6. View My Keys
@bot.message_handler(func=lambda msg: msg.text == "🔑 My Keys" and is_reseller(msg.from_user.id))
def cmd_mykeys(message):
    user_states[message.from_user.id] = None
    pull_data_from_github()
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, added_by, created_at FROM auth_keys WHERE added_by = ?", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows: 
        return bot.reply_to(message, "📭 သင်ထည့်သွင်းထားသော Key မရှိသေးပါ။")
        
    res = "🔑 **သင်ထည့်သွင်းထားသော Key များ:**\n"
    if not is_admin(message.from_user.id):
        user_limit = get_reseller_daily_limit(message.from_user.id)
        res += f"📊 *ယနေ့ထည့်သွင်းပြီးစီးမှု:* `{get_today_added_count(message.from_user.id)} / {user_limit}` ခု\n\n"
    else:
        res += "\n"
        
    for r in rows: 
        date_str = r[3] if r[3] else "-"
        res += f"• ID: `{r[0]}` -> Key: `{r[1]}` (ရက်စွဲ: `{date_str}`)\n"
    bot.reply_to(message, res, parse_mode="Markdown")

# 7. Edit Key
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
        user_states[user_id] = None
        return bot.reply_to(message, "❌ ပုံစံမမှန်ပါ။ `DeviceID | Keyသစ် | Unitသစ် | Durationသစ်` အတိုင်း ပြန်လည်စစ်ဆေးပါ။")
    
    target_device_id = parts[0]  
    new_key = parts[1]           
    new_unit = parts[2]          
    new_duration = parts[3]      
    
    pull_data_from_github()
    
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
