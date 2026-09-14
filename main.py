import os
import asyncio
import sqlite3
import threading
from flask import Flask
from telebot.async_telebot import AsyncTeleBot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton
)

# --- BOT TOKEN VA ADMIN ID ---
TOKEN = "8866529176:AAHywhFvrsn6XG1Ullu8VO1Ims1wmavfQT8"
ADMIN_ID = 8866529176  # Agar Telegram raqamli ID'ingiz boshqacha bo'lsa, shu raqamni almashtiring

bot = AsyncTeleBot(TOKEN)
app = Flask('')

@app.route('/')
def home():
    return "Salomatlik Bot Serveri Barqaror Ishlamoqda!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- MA'LUMOTLAR BAZASI ---
def get_db():
    conn = sqlite3.connect('database.db')
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            phone TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product TEXT,
            phone TEXT,
            location TEXT,
            status TEXT,
            courier_id INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            prize TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_prizes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            prize TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- INTERFEYS TUGMALARI (ADMIN UCHUN SARALANGAN) ---
def get_main_menu(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton("🛍 Buyurtma berish"),
        KeyboardButton("🔍 Kodni tekshirish"),
        KeyboardButton("🏆 Yutuqlarim")
    ]
    # Admin paneli FAQT ADMIN ga ko'rinadi
    if user_id == ADMIN_ID:
        buttons.append(KeyboardButton("👤 Admin Paneli"))
        
    markup.add(*buttons)
    return markup

def get_courier_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🚚 Yo'ldagi buyurtmalarim"),
        KeyboardButton("✅ Yetkazilganlar")
    )
    return markup

user_states = {}

# --- START VA ASOSIY MIJOZ MENYUSI ---
@bot.message_handler(commands=['start'])
async def send_welcome(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)", 
                   (message.from_user.id, message.from_user.full_name))
    conn.commit()
    conn.close()

    await bot.send_message(
        message.chat.id,
        f"Assalomu alaykum {message.from_user.first_name}! Salomatlik markazi rasmiy botiga xush kelibsiz.\n\nKerakli bo'limni tanlang:",
        reply_markup=get_main_menu(message.from_user.id)
    )

# --- BUYURTMA BERISH VA KATALOG ---
@bot.message_handler(func=lambda msg: msg.text == "🛍 Buyurtma berish")
async def start_order(message):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("💊 Maxsus -20% to'plam (Qora sedana + Omega 3)", callback_data="prod_maxsus"),
        InlineKeyboardButton("🌿 Qora sedana yog'i (Tabbah)", callback_data="prod_sedana"),
        InlineKeyboardButton("📞 Mutaxassis maslahati kerak", callback_data="prod_consult")
    )
    await bot.send_message(
        message.chat.id,
        "🛒 **Mahsulotlar katalogi:**\n\nKerakli mahsulotni tanlang yoki mutaxassis maslahatini oling:",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('prod_'))
async def process_prod_choice(call):
    products = {
        "prod_maxsus": "Maxsus -20% to'plam (Qora sedana + Omega 3)",
        "prod_sedana": "Qora sedana yog'i (Tabbah)",
        "prod_consult": "Mutaxassis maslahati"
    }
    prod_name = products.get(call.data, "Salomatlik mahsuloti")
    
    user_states[call.from_user.id] = {'product': prod_name, 'step': 'phone'}
    await bot.answer_callback_query(call.id)
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True))
    
    await bot.send_message(
        call.message.chat.id,
        f"Siz **{prod_name}** ni tanladingiz.\n\nMutaxassisimiz bog'lanishi uchun **'📱 Telefon raqamni yuborish'** tugmasini bosing yoki raqamingizni yozib yuboring:",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=['text', 'contact'], func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].get('step') == 'phone')
async def process_phone(message):
    if message.content_type == 'contact':
        phone = message.contact.phone_number
    else:
        phone = message.text

    user_states[message.from_user.id]['phone'] = phone
    user_states[message.from_user.id]['step'] = 'location'
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📍 Lokatsiyani yuborish", request_location=True))

    await bot.send_message(
        message.chat.id,
        "Rahmat! Endi mahsulot yetkazib berilishi kerak bo'lgan manzilingizni (Lokatsiya yuboring yoki matn ko'rinishida yozing):",
        reply_markup=kb
    )

@bot.message_handler(content_types=['text', 'location'], func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].get('step') == 'location')
async def process_location_and_save(message):
    user_data = user_states.pop(message.from_user.id, {})
    prod = user_data.get('product', 'Noma\'lum')
    phone = user_data.get('phone', 'Noma\'lum')
    
    if message.content_type == 'location':
        loc_text = f"https://maps.google.com/?q={message.location.latitude},{message.location.longitude}"
    else:
        loc_text = message.text

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (user_id, product, phone, location, status) VALUES (?, ?, ?, ?, 'Yangi')",
        (message.from_user.id, prod, phone, loc_text)
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await bot.send_message(
        message.chat.id,
        f"✅ **Buyurtmangiz muvaffaqiyatli qabul qilindi!**\n\n🆔 **Buyurtma ID:** #{order_id}\n🛍 **Mahsulot:** {prod}\n\nTez orada operatorlarimiz siz bilan bog'lanishadi.",
        parse_mode="Markdown",
        reply_markup=get_main_menu(message.from_user.id)
    )

    # Operator (Admin)ga xabarnoma yuborish
    op_kb = InlineKeyboardMarkup(row_width=2)
    op_kb.add(
        InlineKeyboardButton("⏳ Jarayonda", callback_data=f"op_process_{order_id}"),
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"op_confirm_{order_id}"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data=f"op_cancel_{order_id}")
    )

    try:
        await bot.send_message(
            ADMIN_ID,
            f"📥 **YANGI BUYURTMA!**\n\n"
            f"📌 **ID:** #{order_id}\n"
            f"👤 **Mijoz:** {message.from_user.full_name}\n"
            f"🛍 **Mahsulot:** {prod}\n"
            f"📞 **Tel:** {phone}\n"
            f"📍 **Manzil:** {loc_text}",
            reply_markup=op_kb,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Operatorga xabar yuborishda xatolik: {e}")

# --- KODNI TEKSHIRISH VA YUTUQLAR TIZIMI ---
@bot.message_handler(func=lambda msg: msg.text == "🔍 Kodni tekshirish")
async def start_check_code(message):
    user_states[message.from_user.id] = {'step': 'promo'}
    await bot.send_message(
        message.chat.id,
        "🏷 **Mahsulot qutisidagi promo-kodni kiriting:**\n(Masalan: WIN1002)",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].get('step') == 'promo')
async def process_promo_code(message):
    code_entered = message.text.strip().upper()
    user_states.pop(message.from_user.id, None)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT prize FROM promocodes WHERE code = ?", (code_entered,))
    row = cursor.fetchone()

    if row:
        prize = row[0]
        cursor.execute("DELETE FROM promocodes WHERE code = ?", (code_entered,))
        cursor.execute("INSERT INTO user_prizes (user_id, prize) VALUES (?, ?)", (message.from_user.id, prize))
        conn.commit()
        conn.close()
        await bot.send_message(
            message.chat.id,
            f"🎉 **TABRIKLAYMIZ!**\n\nSiz kiritgan promo-kod bo'yicha yutuq: **{prize}**!\nYutuq parolingiz '🏆 Yutuqlarim' bo'limiga qo'shildi.",
            parse_mode="Markdown"
        )
    else:
        conn.close()
        await bot.send_message(
            message.chat.id,
            "❌ **Xatolik!** Ushbu promo-kod mavjud emas yoki avval ishlatilgan.",
            parse_mode="Markdown"
        )

@bot.message_handler(func=lambda msg: msg.text == "🏆 Yutuqlarim")
async def show_my_prizes(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT prize FROM user_prizes WHERE user_id = ?", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await bot.send_message(message.chat.id, "🎁 Sizda hozircha yutuqlar mavjud emas.")
        return

    text = "🏆 **Sizning yutuqlaringiz:**\n\n"
    for idx, r in enumerate(rows, 1):
        text += f"{idx}. {r[0]}\n"
    await bot.send_message(message.chat.id, text, parse_mode="Markdown")

# --- ADMIN PANEL ---
@bot.message_handler(func=lambda msg: msg.text == "👤 Admin Paneli")
async def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        await bot.send_message(message.chat.id, "⛔ Sizda admin huquqi yo'q!")
        return
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    conn.close()

    await bot.send_message(
        message.chat.id,
        f"📊 **ADMIN KABINETI**\n\n👥 Jami foydalanuvchilar: **{total_users} ta**\n📦 Jami buyurtmalar: **{total_orders} ta**\n\n🔐 Kuryer rejimini faollashtirish uchun: `/kuryer kuryer123` deb yozing.",
        parse_mode="Markdown"
    )

# --- OPERATOR TUGMALARI UCHUN HANDLERLAR ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('op_'))
async def operator_action(call):
    data_parts = call.data.split('_')
    action = data_parts[1] 
    try:
        order_id = int(data_parts[2])
    except (IndexError, ValueError):
        await bot.answer_callback_query(call.id, "Xatolik yuz berdi!")
        return

    conn = get_db()
    cursor = conn.cursor()
    
    if action == 'confirm':
        cursor.execute("UPDATE orders SET status = 'Tasdiqlandi (Kuryerga yuborildi)' WHERE id = ?", (order_id,))
        conn.commit()
        cursor.execute("SELECT product, phone, location FROM orders WHERE id = ?", (order_id,))
        order_info = cursor.fetchone()
        conn.close()
        
        await bot.answer_callback_query(call.id, "Buyurtma tasdiqlandi va Kuryerga yuborildi!")
        await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        await bot.send_message(call.message.chat.id, f"✅ #{order_id}-sonli buyurtma tasdiqlandi va kuryerga yuborildi.")
        
        if order_info:
            prod, phone, loc = order_info
            courier_kb = InlineKeyboardMarkup()
            courier_kb.add(InlineKeyboardButton("📥 Qabul qilish", callback_data=f"accept_{order_id}"))
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"📦 **KURYER UCHUN YANGI BUYURTMA!**\n\n📌 **ID:** #{order_id}\n🛍 **Mahsulot:** {prod}\n📞 **Tel:** {phone}\n📍 **Manzil:** {loc}",
                    reply_markup=courier_kb,
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Kuryerga yuborishda xatolik: {e}")

    elif action == 'process':
        cursor.execute("UPDATE orders SET status = 'Jarayonda' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"op_confirm_{order_id}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"op_cancel_{order_id}")
        )
        await bot.answer_callback_query(call.id, "Mijoz bilan suhbatlashilmoqda...")
        await bot.edit_message_text(
            f"⏳ **ID #{order_id}** — Jarayonda (Mijoz bilan suhbatlashilmoqda)", 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=kb, 
            parse_mode="Markdown"
        )
        
    elif action == 'cancel':
        cursor.execute("UPDATE orders SET status = 'Bekor qilindi' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
        await bot.answer_callback_query(call.id, "Buyurtma bekor qilindi.")
        await bot.edit_message_text(f"❌ **ID #{order_id}** — Bekor qilindi", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# --- KURYER TIZIMI ---
@bot.message_handler(commands=['kuryer'])
async def courier_secret_login(message):
    args = message.text.split()
    SECRET_PASSWORD = "kuryer123"
    
    if len(args) > 1 and args[1] == SECRET_PASSWORD:
        await bot.send_message(
            message.chat.id,
            "✅ **Maxfiy parol tasdiqlandi!**\nKuryer paneli faollashtirildi.",
            parse_mode="Markdown",
            reply_markup=get_courier_menu()
        )
    else:
        await bot.send_message(
            message.chat.id,
            "🔐 Kuryer panelini ochish uchun parolni kiriting:\n\n**Namuna:** `/kuryer kuryer123`",
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_'))
async def courier_accept_order(call):
    try:
        order_id = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        await bot.answer_callback_query(call.id, "Xatolik yuz berdi!")
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = 'Qabul qilindi', courier_id = ? WHERE id = ?", (call.from_user.id, order_id))
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚚 Yo'ldaman", callback_data=f"ontheway_{order_id}"))

    await bot.answer_callback_query(call.id, "Buyurtma qabul qilindi!")
    await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=kb)
    await bot.send_message(call.message.chat.id, f"✅ **#{order_id}**-sonli buyurtma qabul qilindi. Yo'lga chiqish uchun 'Yo\\'ldaman' tugmasini bosing.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('ontheway_'))
async def courier_on_the_way(call):
    try:
        order_id = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        await bot.answer_callback_query(call.id, "Xatolik yuz berdi!")
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = 'Yo''lda' WHERE id = ?", (order_id,))
    cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Yetkazildi", callback_data=f"deliver_{order_id}"))

    await bot.answer_callback_query(call.id, "Holat: Yo'lda")
    await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=kb)
    await bot.send_message(call.message.chat.id, f"🚚 **#{order_id}** — Yo'ldasiz. Manzilga yetib borgach 'Yetkazildi' tugmasini bosing.", parse_mode="Markdown")

    if row:
        try:
            await bot.send_message(row[0], "🚚 Kuryerimiz buyurtmangizni olib yo'lga chiqdi!")
        except Exception as e:
            print(f"Mijozga xabar berishda xatolik: {e}")

@bot.message_handler(func=lambda msg: msg.text == "🚚 Yo'ldagi buyurtmalarim")
async def courier_on_the_way_orders(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, product, phone, location, status FROM orders WHERE courier_id = ? AND status IN ('Qabul qilindi', 'Yo''lda')", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await bot.send_message(message.chat.id, "📭 Sizda hozirda yo'ldagi buyurtmalar yo'q.")
        return

    for o_id, prod, phone, loc, status in rows:
        kb = InlineKeyboardMarkup()
        if status == 'Qabul qilindi':
            kb.add(InlineKeyboardButton("🚚 Yo'ldaman", callback_data=f"ontheway_{o_id}"))
        else:
            kb.add(InlineKeyboardButton("✅ Yetkazildi", callback_data=f"deliver_{o_id}"))
        
        text = f"📦 **Buyurtma #{o_id}**\nStatus: {status}\n🛍 Mahsulot: {prod}\n📞 Tel: {phone}\n📍 Manzil: {loc}"
        await bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "✅ Yetkazilganlar")
async def courier_delivered_orders(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, product, phone, location FROM orders WHERE courier_id = ? AND status = 'Yetkazildi' ORDER BY id DESC LIMIT 10", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await bot.send_message(message.chat.id, "📦 Hali yetkazilgan buyurtmalar yo'q.")
        return

    text = "✅ **Yetkazilgan oxirgi buyurtmalaringiz:**\n\n"
    for o_id, prod, phone, loc in rows:
        text += f"📌 **ID #{o_id}**\n🛍 {prod}\n📞 Tel: {phone}\n---\n"
    await bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('deliver_'))
async def courier_mark_delivered(call):
    try:
        order_id = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        await bot.answer_callback_query(call.id, "Xatolik yuz berdi!")
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = 'Yetkazildi' WHERE id = ?", (order_id,))
    cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()

    await bot.answer_callback_query(call.id, "Buyurtma yetkazildi!")
    await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    await bot.send_message(call.message.chat.id, f"🎉 **#{order_id}**-sonli buyurtma yetkazildi!", parse_mode="Markdown")

    if row:
        try:
            await bot.send_message(row[0], "🎉 Buyurtmangiz muvaffaqiyatli yetkazildi! Xaridingiz uchun rahmat!")
        except Exception as e:
            print(f"Mijozga xabar berishda xatolik: {e}")

# --- ISHGA TUSHIRISH ---
async def main():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    await bot.infinity_polling()

if __name__ == '__main__':
    asyncio.run(main())
