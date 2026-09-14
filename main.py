import os
import asyncio
import sqlite3
import threading
from flask import Flask
import telebot
from telebot.async_telebot import AsyncTeleBot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton
)

# Render va environment parametrlarini sozlash
TOKEN = os.environ.get("BOT_TOKEN", "8866529176:AAHywhFvrsn6XG1Ullu8VO1Ims1wmavfQT8")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789"))  # Telegram ID raqamingizni yozing

bot = AsyncTeleBot(TOKEN)
courier_bot = AsyncTeleBot(TOKEN)

app = Flask('')

@app.route('/')
def home():
    return "Salomatlik Bot Serveri Ishlamoqda!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- MA'LUMOTLAR BAZASI (SQLite WAL mode) ---
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
            discount INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- MENYULAR ---
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🛍 Buyurtma berish"),
        KeyboardButton("👤 Admin Paneli"),
        KeyboardButton("🔍 Kodni tekshirish"),
        KeyboardButton("🏆 Yutuqlarim")
    )
    return markup

def get_courier_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🚚 Yo'ldagi buyurtmalarim"),
        KeyboardButton("✅ Yetkazilganlar")
    )
    return markup

user_states = {}

# --- MIJOZ VA ASOSIY BOT HANDLERLARI ---
@bot.message_handler(commands=['start'])
async def send_welcome(message):
    await bot.send_message(
        message.chat.id,
        "Assalomu alaykum! Salomatlik markazi rasmiy botiga xush kelibsiz.",
        reply_markup=get_main_menu()
    )

@bot.message_handler(func=lambda msg: msg.text == "🛍 Buyurtma berish")
async def start_order(message):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("💊 Maxsus -20% to'plam (Qora sedana + Omega 3)", callback_data="prod_maxsus"),
        InlineKeyboardButton("📞 Mutaxassis maslahati kerak", callback_data="prod_consult")
    )
    await bot.send_message(
        message.chat.id,
        "Sizga mutaxassis maslahati kerakmi yoki mahsulot bilan to'liq tanishmisiz?",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('prod_'))
async def process_prod_choice(call):
    prod_type = call.data
    prod_name = "Maxsus -20% to'plam" if prod_type == "prod_maxsus" else "Mutaxassis maslahati"
    
    user_states[call.from_user.id] = {'product': prod_name}
    await bot.answer_callback_query(call.id)
    await bot.send_message(
        call.message.chat.id,
        "Mutaxassisimiz sizga qo'ng'iroq qilishi uchun telefon raqamingizni yuboring (masalan: +998901234567):"
    )

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states and 'phone' not in user_states[msg.from_user.id])
async def process_phone(message):
    user_states[message.from_user.id]['phone'] = message.text
    await bot.send_message(
        message.chat.id,
        "Manzilingizni (Lokatsiya yoki matn ko'rinishida) yuboring:"
    )

@bot.message_handler(content_types=['text', 'location'], func=lambda msg: msg.from_user.id in user_states and 'phone' in user_states[msg.from_user.id])
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
        f"✅ So'rovingiz qabul qilindi! Mutaxassisimiz tez orada siz bilan bog'lanib bepul maslahat beradi.\n\n🆔 **Buyurtma ID:** #{order_id}",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

    # Operatorga yuborish
    op_kb = InlineKeyboardMarkup(row_width=2)
    op_kb.add(
        InlineKeyboardButton("⏳ Jarayonda", callback_data=f"op_process_{order_id}"),
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"op_confirm_{order_id}"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data=f"op_cancel_{order_id}")
    )

    try:
        await bot.send_message(
            ADMIN_ID,
            f"📥 **YANGI BUYURTMA/MASLAHAT SO'ROVI!**\n\n"
            f"📌 **ID:** #{order_id}\n"
            f"🛍 **Mahsulot:** {prod}\n"
            f"📞 **Tel:** {phone}\n"
            f"📍 **Manzil:** {loc_text}",
            reply_markup=op_kb,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Operatorga yuborishda xatolik: {e}")

@bot.message_handler(func=lambda msg: msg.text == "👤 Admin Paneli")
async def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        await bot.send_message(message.chat.id, "Siz admin emassiz!")
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
        f"📊 **Admin Paneli**\n\n👥 Jami foydalanuvchilar: {total_users}\n📦 Jami buyurtmalar: {total_orders}",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "🔍 Kodni tekshirish")
async def check_code(message):
    await bot.send_message(message.chat.id, "Mahsulot qutisidagi promo-kodni kiriting:")

@bot.message_handler(func=lambda msg: msg.text == "🏆 Yutuqlarim")
async def my_prizes(message):
    await bot.send_message(message.chat.id, "🎁 Sizda hozircha yutuqlar mavjud emas.")

# --- OPERATOR TUGMALARI LOGIKASI ---
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
        
        await bot.answer_callback_query(call.id, "Buyurtma tasdiqlandi!")
        await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        await bot.send_message(call.message.chat.id, f"✅ #{order_id}-sonli buyurtma tasdiqlandi va kuryerga yuborildi.")
        
        if order_info:
            prod, phone, loc = order_info
            courier_kb = InlineKeyboardMarkup()
            courier_kb.add(InlineKeyboardButton("📥 Qabul qilish", callback_data=f"accept_{order_id}"))
            try:
                await courier_bot.send_message(
                    ADMIN_ID,
                    f"📦 **YANGI BUYURTMA (Maslahatdan so'ng)!**\n\n"
                    f"📌 **ID:** #{order_id}\n"
                    f"🛍 **Mahsulot:** {prod}\n"
                    f"📞 **Tel:** {phone}\n"
                    f"📍 **Manzil:** {loc}",
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
            f"⏳ **ID #{order_id}** — Jarayonda (Mijoz bilan suhbatlashilmoqda)\n"
            f"Sotib olsa 'Tasdiqlash', olmasa 'Bekor qilish' tugmasini bosing.", 
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

# --- KURYER BOT QISMI VA SIRLI /kuryer LOGINI ---
@courier_bot.message_handler(commands=['kuryer'])
async def courier_secret_login(message):
    args = message.text.split()
    SECRET_PASSWORD = "kuryer123"
    
    if len(args) > 1 and args[1] == SECRET_PASSWORD:
        await courier_bot.send_message(
            message.chat.id,
            "✅ **Maxfiy parol tasdiqlandi!**\nKuryer paneli ochildi.",
            parse_mode="Markdown",
            reply_markup=get_courier_menu()
        )
    else:
        await courier_bot.send_message(
            message.chat.id,
            "🔐 Kuryer panelini ochish uchun parolni kiriting:\n\n**Namuna:** `/kuryer kuryer123`",
            parse_mode="Markdown"
        )

@courier_bot.callback_query_handler(func=lambda call: call.data.startswith('accept_'))
async def courier_accept_order(call):
    try:
        order_id = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        await courier_bot.answer_callback_query(call.id, "Xatolik yuz berdi!")
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = 'Qabul qilindi', courier_id = ? WHERE id = ?", (call.from_user.id, order_id))
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚚 Yo'ldaman", callback_data=f"ontheway_{order_id}"))

    await courier_bot.answer_callback_query(call.id, "Buyurtma qabul qilindi!")
    await courier_bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=kb)
    await courier_bot.send_message(call.message.chat.id, f"✅ **#{order_id}**-sonli buyurtma qabul qilindi. Yo'lga chiqish uchun 'Yo\\'ldaman' tugmasini bosing.", parse_mode="Markdown")

@courier_bot.callback_query_handler(func=lambda call: call.data.startswith('ontheway_'))
async def courier_on_the_way(call):
    try:
        order_id = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        await courier_bot.answer_callback_query(call.id, "Xatolik yuz berdi!")
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

    await courier_bot.answer_callback_query(call.id, "Holat: Yo'lda")
    await courier_bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=kb)
    await courier_bot.send_message(call.message.chat.id, f"🚚 **#{order_id}** — Yo'ldasiz. Manzilga yetib borgach 'Yetkazildi' tugmasini bosing.", parse_mode="Markdown")

    if row:
        try:
            await bot.send_message(row[0], "🚚 Kuryerimiz buyurtmangizni olib yo'lga chiqdi!")
        except Exception as e:
            print(f"Mijozga xabar berishda xatolik: {e}")

@courier_bot.message_handler(func=lambda msg: msg.text == "🚚 Yo'ldagi buyurtmalarim")
async def courier_on_the_way_orders(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, product, phone, location, status FROM orders WHERE courier_id = ? AND status IN ('Qabul qilindi', 'Yo''lda')", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await courier_bot.send_message(message.chat.id, "𭭜 Sizda hozirda yo'ldagi buyurtmalar yo'q.")
        return

    for o_id, prod, phone, loc, status in rows:
        kb = InlineKeyboardMarkup()
        if status == 'Qabul qilindi':
            kb.add(InlineKeyboardButton("🚚 Yo'ldaman", callback_data=f"ontheway_{o_id}"))
        else:
            kb.add(InlineKeyboardButton("✅ Yetkazildi", callback_data=f"deliver_{o_id}"))
        
        text = f"📦 **Buyurtma #{o_id}**\nStatus: {status}\n🛍 Mahsulot: {prod}\n📞 Tel: {phone}\n📍 Manzil: {loc}"
        await courier_bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")

@courier_bot.message_handler(func=lambda msg: msg.text == "✅ Yetkazilganlar")
async def courier_delivered_orders(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, product, phone, location FROM orders WHERE courier_id = ? AND status = 'Yetkazildi' ORDER BY id DESC LIMIT 10", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await courier_bot.send_message(message.chat.id, "📦 Hali yetkazilgan buyurtmalar yo'q.")
        return

    text = "✅ **Yetkazilgan oxirgi buyurtmalaringiz:**\n\n"
    for o_id, prod, phone, loc in rows:
        text += f"📌 **ID #{o_id}**\n🛍 {prod}\n📞 Tel: {phone}\n---\n"
    await courier_bot.send_message(message.chat.id, text, parse_mode="Markdown")

@courier_bot.callback_query_handler(func=lambda call: call.data.startswith('deliver_'))
async def courier_mark_delivered(call):
    try:
        order_id = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        await courier_bot.answer_callback_query(call.id, "Xatolik yuz berdi!")
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = 'Yetkazildi' WHERE id = ?", (order_id,))
    cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()

    await courier_bot.answer_callback_query(call.id, "Buyurtma yetkazildi!")
    await courier_bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    await courier_bot.send_message(call.message.chat.id, f"🎉 **#{order_id}**-sonli buyurtma yetkazildi va Yetkazilganlar bo'limiga qo'shildi!", parse_mode="Markdown")

    if row:
        try:
            await bot.send_message(row[0], "🎉 Buyurtmangiz muvaffaqiyatli yetkazildi! Xaridingiz uchun rahmat!")
        except Exception as e:
            print(f"Mijozga xabar berishda xatolik: {e}")

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    await asyncio.gather(
        bot.infinity_polling(),
        courier_bot.infinity_polling()
    )

if __name__ == '__main__':
    asyncio.run(main())
