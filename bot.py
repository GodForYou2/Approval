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

# Database ကို စဆောက်ပြီးတာနဲ့ GitHub က ဒေတာတွေကို လှမ်းဆွဲခိုင်းမည်
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
    pull_data_from_github() # GitHub က ဒေတာကို ဆွဲယူမည်
    if sync_to_github():   # ပြန်ပြီး ညှိသိမ်းမည်
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
    
    # List မပြခင် GitHub က နောက်ဆုံးဒေတာကို အမြဲ အော်တိုဆွဲဖတ်ခိုင်းမည်
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

if __name__ == "__main__":
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()
    
    print(f"[+] Render Auto-Restore Bot is running...")
    bot.infinity_polling()    cursor.execute('''CREATE TABLE IF NOT EXISTS auth_keys (
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

# --- GitHub Auto Sync Function ---
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
            "message": "Bot Auto Sync Keys (Format: ID | Key | Unit | Duration)",
            "content": base64.b64encode(file_content.encode('utf-8')).decode('utf-8')
        }
        if sha: payload["sha"] = sha

        put_res = requests.put(url, headers=headers, json=payload)
        return put_res.status_code in [200, 201]
    except Exception as e:
        print(f"[-] Sync Error: {str(e)}")
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
        cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role) VALUES (?, ?, ?)", (reseller_id, reseller_name, 'reseller'))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ **အောင်မြင်ပါသည်!**\n👤 နာမည်: `{reseller_name}`\n🆔 ID: `{reseller_id}` အား Reseller ခန့်အပ်ပြီးပါပြီ။", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ သိမ်းဆည်းရာတွင် အမှားအယွင်းရှိခဲ့သည်- {str(e)}")
    
    user_states[admin_id] = None
    if admin_id in reseller_temp_data: del reseller_temp_data[admin_id]

# 2. Reseller List
@bot.message_handler(func=lambda msg: msg.text == "📊 Reseller List" and is_admin(msg.from_user.id))
def admin_view_resellers(message):
    user_states[message.from_user.id] = None
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT tg_id, username FROM users WHERE role = 'reseller'")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 Reseller စာရင်း မရှိသေးပါ။")
    res = f"👥 **စုစုပေါင်း Reseller အရေအတွက်:** {len(rows)} ဦး\n\n"
    for r in rows: res += f"• **{r[1]}** (ID: `{r[0]}`)\n"
    bot.reply_to(message, res, parse_mode="Markdown")

# 3. Delete Reseller
@bot.message_handler(func=lambda msg: msg.text == "🗑 Delete Reseller" and is_admin(msg.from_user.id))
def admin_delete_reseller_menu(message):
    user_states[message.from_user.id] = None
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
        bot.answer_callback_query(call.id, f"✅ {r_name} အား ဖြုတ်ချပြီးပါပြီ။")
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                              text=f"🗑 **အောင်မြင်ပါသည်!**\n👤 Reseller: `_{r_name}_` (ID: `{reseller_id}`) အား စနစ်အတွင်းမှ ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="Markdown")
    except Exception as e: bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

# 4. View All Keys
@bot.message_handler(func=lambda msg: msg.text == "🌐 View All Keys" and is_admin(msg.from_user.id))
def admin_view_all_keys(message):
    user_states[message.from_user.id] = None
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
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string FROM auth_keys WHERE added_by = ?", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 သင်ထည့်သွင်းထားသော Key မရှိသေးပါ။")
    res = "🔑 **သင်ထည့်သွင်းထားသော Key များ:**\n\n"
    for r in rows: res += f"• ID: `{r[0]}` -> Key: `{r[1]}`\n"
    bot.reply_to(message, res, parse_mode="Markdown")

# 7. Edit Key
@bot.message_handler(func=lambda msg: msg.text == "✏️ Edit Key" and is_reseller(msg.from_user.id))
def cmd_editkey(message):
    user_states[message.from_user.id] = 'waiting_for_edit_data'
    msg_text = ("✏️ ပြင်ဆင်လိုသော Key ပုံစံကို ပို့ပေးပါ-\n\n`ပြင်မည့်Key | IDသစ် | Unitသစ် | Durationသစ်`")
    bot.reply_to(message, msg_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'waiting_for_edit_data' and msg.text not in MENU_BUTTONS)
def process_edit_key(message):
    user_id = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 4: return bot.reply_to(message, "❌ ပုံစံမမှန်ပါ။ ပြန်လည်စစ်ဆေးပါ။")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT added_by FROM auth_keys WHERE key_string = ?", (parts[0],))
    result = cursor.fetchone()
    conn.close()
    owner_id = result[0] if result else None
    if owner_id is None: return bot.reply_to(message, "❌ ဤ Key ကို ရှာမတွေ့ပါ။")
    if owner_id != user_id and not is_admin(user_id): return bot.reply_to(message, "🚫 ပြင်ဆင်ခွင့်မရှိပါ။")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE auth_keys SET target_id=?, unit_val=?, duration_type=? WHERE key_string=?", (parts[1], parts[2], parts[3], parts[0]))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✏️ Key ကို ပြင်ဆင်ပြီးပါပြီ။ Cloud သို့ Update လုပ်နေသည်...")
        sync_db_to_github()
        user_states[user_id] = None
    except: bot.reply_to(message, "❌ ပြင်ဆင်မှု မှားယွင်းနေသည်။")

# 8. Delete Key (ID ဖြင့် စစ်ဆေးဖျက်ဆီးခြင်း)
@bot.message_handler(func=lambda msg: msg.text == "🗑 Delete Key" and is_reseller(msg.from_user.id))
def cmd_delete_key_trigger(message):
    user_states[message.from_user.id] = 'waiting_for_del_id'
    bot.reply_to(message, "🗑 ဖျက်လိုသော **Device ID** (ဥပမာ - `F4AFA83F4F1577DE`) ကို ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'waiting_for_del_id' and msg.text not in MENU_BUTTONS)
def process_delete_key_by_id(message):
    user_id = message.from_user.id
    id_to_del = message.text.strip()
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
    # Flask ဝဘ်ဆာဗာကို Thread တစ်ခုနှင့် သီးသန့် နောက်ကွယ်တွင် ပွင့်ထားခိုင်းမည်
    threading.Thread(target=run_web_server, daemon=True).start()
    print("[+] Flask Web Server + Telegram Bot Running 24/7 on Render...")
    bot.infinity_polling()
