import os
import asyncio
import sqlite3
from threading import Thread
from flask import Flask
from telebot.async_telebot import AsyncTeleBot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- FLASK VEB-SERVER (PORT UCHUN) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot ishlayapti!"

def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# Veb-serverni alohida oqimda ishga tushiramiz
Thread(target=run_web, daemon=True).start()

# --- BOT SOZLAMALARI ---
BOT_TOKEN = "8866529176:AAHywhFvrsn6XG1Ullu8VO1Ims1wmavfQT8"
COURIER_BOT_TOKEN = "8925703420:AAFQrXlAE0wD760H_TBr-A5SJWhA5NXuXT0"
ADMIN_ID = 786394206

DB_NAME = "bot_database.db"

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            full_name TEXT, 
            username TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY, 
            prize TEXT, 
            file_id TEXT, 
            file_type TEXT, 
            is_used INTEGER DEFAULT 0, 
            used_by INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            product TEXT, 
            phone TEXT, 
            location TEXT, 
            status TEXT DEFAULT 'Kutilmoqda', 
            courier_id INTEGER DEFAULT NULL,
            operator_id INTEGER DEFAULT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY, 
            value TEXT
        )
    """)
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN operator_id INTEGER DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def set_operator_id(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('operator_id', ?)", (str(user_id),))
    conn.commit()
    conn.close()

def get_operator_id():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM config WHERE key = 'operator_id'")
    row = cursor.fetchone()
    conn.close()
    return int(row[0]) if row else ADMIN_ID

def get_user_menu(user_id: int):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("🔍 Kodni tekshirish"), KeyboardButton("🏆 Yutuqlarim"), KeyboardButton("🛒 Buyurtma berish"))
    if user_id == ADMIN_ID:
        markup.add(KeyboardButton("🔑 Admin Paneli"))
    return markup

def get_admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🎁 Sovg'a qo'shish"), 
        KeyboardButton("📦 Buyurtmalar"), 
        KeyboardButton("📊 Sotuvlar (Operatorlar)"),
        KeyboardButton("⬅️ Asosiy menyu")
    )
    return markup

def get_courier_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🚚 Yo'ldagi buyurtmalarim"),
        KeyboardButton("✅ Yetkazilganlar")
    )
    return markup

def get_products_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(KeyboardButton("🌿 Dorivor toʻplam (Qora sedana + Omega-3)"), KeyboardButton("🌟 Maxsus -20% to'plam"), KeyboardButton("❌ Bekor qilish"))
    return markup

def get_buying_option_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        KeyboardButton("👨‍⚕️ Mutaxassis maslahati kerak"),
        KeyboardButton("✅ Mahsulot bilan tanishman, xarid qilaman"),
        KeyboardButton("❌ Bekor qilish")
    )
    return markup

def get_phone_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True), KeyboardButton("❌ Bekor qilish"))
    return markup

def get_location_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(KeyboardButton("📍 Lokatsiyani yuborish", request_location=True), KeyboardButton("❌ Bekor qilish"))
    return markup

bot = AsyncTeleBot(BOT_TOKEN)
courier_bot = AsyncTeleBot(COURIER_BOT_TOKEN)
user_states = {}

@bot.message_handler(commands=["operator"])
async def set_operator_command(message):
    user_id = message.from_user.id
    set_operator_id(user_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, full_name, username) VALUES (?, ?, ?)", 
                   (user_id, message.from_user.first_name, message.from_user.username or ""))
    conn.commit()
    conn.close()

    await bot.send_message(
        message.chat.id,
        f"👨‍⚕️ **Tabriklaymiz!** Siz tizimda **OPERATOR** sifatida ro'yxatga olindingiz.\n\n"
        f"Endi mijozlar maslahat so'rashganda ularning so'rovlari sizga keladi.",
        parse_mode="Markdown",
        reply_markup=get_user_menu(user_id)
    )

@bot.message_handler(commands=["start"])
async def start_handler(message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    is_new_user = cursor.fetchone() is None

    if is_new_user:
        cursor.execute("INSERT INTO users VALUES (?, ?, ?)", (user_id, message.from_user.first_name, message.from_user.username or ""))
        welcome_code = f"START{user_id}"
        cursor.execute("INSERT OR IGNORE INTO promo_codes VALUES (?, ?, ?, ?, 0, NULL)", 
                       (welcome_code, "🌿 Qora Sedana + Omega-3 to'plamiga -20% chegirma!", None, "none"))
        conn.commit()
        conn.close()
        
        msg_text = (
            f"Salom, {message.from_user.first_name}!\n\n"
            f"🎉 **Xush kelibsiz bonusi!** Sizga birinchi buyurtmangiz uchun maxsus promo-kod taqdim etildi:\n\n"
            f"🔑 Promokod: `{welcome_code}`\n\n"
            f"Kodni nusxalab oling va pastdagi **🔍 Kodni tekshirish** tugmasi orqali faollashtiring!"
        )
        await bot.send_message(message.chat.id, msg_text, parse_mode="Markdown", reply_markup=get_user_menu(user_id))
    else:
        conn.close()
        await bot.send_message(message.chat.id, f"Salom, {message.from_user.first_name}! Yana ko'rishganimizdan xursandmiz.", reply_markup=get_user_menu(user_id))

@bot.message_handler(func=lambda msg: msg.text in ["❌ Bekor qilish", "⬅️ Asosiy menyu"])
async def cancel_action(message):
    user_states.pop(message.from_user.id, None)
    await bot.send_message(message.chat.id, "Asosiy menyuga qaytildi.", reply_markup=get_user_menu(message.from_user.id))

@bot.message_handler(func=lambda msg: msg.text == "🔑 Admin Paneli" and msg.from_user.id == ADMIN_ID)
async def open_admin_panel(message):
    await bot.send_message(message.chat.id, "🔑 Admin paneli:", reply_markup=get_admin_menu())

@bot.message_handler(func=lambda msg: msg.text == "📦 Buyurtmalar" and msg.from_user.id == ADMIN_ID)
async def admin_orders(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, product, phone, location, status FROM orders ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await bot.send_message(message.chat.id, "Hali buyurtmalar mavjud emas.")
        return

    text = "📦 **Oxirgi buyurtmalar:**\n\n"
    for o_id, u_id, prod, phone, loc, st in rows:
        text += f"📌 **ID #{o_id}**\n🛍 Mahsulot: {prod}\n📞 Tel: {phone}\n📍 Manzil: {loc}\n📊 Holat: {st}\n---\n"
    await bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📊 Sotuvlar (Operatorlar)" and msg.from_user.id == ADMIN_ID)
async def admin_operators_stats(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT o.operator_id, u.full_name, u.username 
        FROM orders o 
        JOIN users u ON o.operator_id = u.user_id 
        WHERE o.operator_id IS NOT NULL
    """)
    operators = cursor.fetchall()
    conn.close()

    if not operators:
        await bot.send_message(message.chat.id, "📊 Hozircha operatorlar tomonidan tasdiqlangan sotuvlar mavjud emas.")
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for op_id, full_name, username in operators:
        uname = f"(@{username})" if username else ""
        markup.add(InlineKeyboardButton(f"👤 {full_name} {uname}", callback_data=f"stats_op_{op_id}"))

    await bot.send_message(message.chat.id, "📊 **Operatorlar bo'yicha sotuvlar statistikasi:**\n\nQuyidagi operatorlardan birini tanlang:", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('stats_op_'))
async def show_operator_sales(call):
    try:
        op_id = int(call.data.split("_")[2])
    except (IndexError, ValueError):
        await bot.answer_callback_query(call.id, "Xatolik yuz berdi!")
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, username FROM users WHERE user_id = ?", (op_id,))
    op_info = cursor.fetchone()
    op_name = op_info[0] if op_info else "Noma'lum"
    op_uname = f"@{op_info[1]}" if op_info and op_info[1] else "Niksiz"

    cursor.execute("SELECT id, product, phone, status FROM orders WHERE operator_id = ? ORDER BY id DESC", (op_id,))
    orders = cursor.fetchall()
    conn.close()

    total_sales = len(orders)
    text = f"👨‍⚕️ **Operator:** {op_name} ({op_uname})\n" \
           f"📈 **Jami sotuvlar soni:** {total_sales} ta\n\n" \
           f"📋 **Tasdiqlangan buyurtmalar ro'yxati:**\n"

    if not orders:
        text += "Hali buyurtmalar yo'q."
    else:
        for o_id, prod, phone, status in orders:
            text += f"▪️ **ID #{o_id}** | {prod} | Tel: {phone} | 📊 [{status}]\n"

    await bot.answer_callback_query(call.id)
    await bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🏆 Yutuqlarim")
async def show_my_prizes(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT code, prize FROM promo_codes WHERE used_by = ?", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await bot.send_message(message.chat.id, "Sizda hali faollashtirilgan yutuqlar yo'q.")
        return
    
    text = "🏆 **Sizning faol chegirma va sovg'alaringiz:**\n\n"
    for code, prize in rows:
        text += f"🔑 Kod: `{code}`\n🎁 {prize}\n---\n"
    await bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🎁 Sovg'a qo'shish" and msg.from_user.id == ADMIN_ID)
async def start_add_gift(message):
    user_states[message.from_user.id] = {"state": "step_1_code"}
    await bot.send_message(message.chat.id, "1️⃣ Promo-kodni kiriting (masalan: OMEGA2026):")

@bot.message_handler(func=lambda msg: msg.text == "🛒 Buyurtma berish")
async def start_order(message):
    user_states[message.from_user.id] = {"state": "select_product"}
    await bot.send_message(message.chat.id, "Kerakli mahsulotni tanlang:", reply_markup=get_products_menu())

@bot.message_handler(func=lambda msg: msg.text == "🔍 Kodni tekshirish")
async def start_code_check(message):
    user_states[message.from_user.id] = {"state": "waiting_for_code"}
    await bot.send_message(message.chat.id, "Promo-kodni kiriting:")

@bot.message_handler(content_types=['contact'])
async def handle_contact(message):
    user_id = message.from_user.id
    st = user_states.get(user_id, {}).get("state")
    phone = message.contact.phone_number

    if st == "waiting_phone_for_advice":
        user_states[user_id]["phone"] = phone
        user_states[user_id]["state"] = "waiting_location_for_advice"
        await bot.send_message(message.chat.id, "Maslahatdan so'ng buyurtma tasdiqlansa kuryer borishi uchun manzilingizni (Lokatsiya) yuboring:", reply_markup=get_location_menu())

    elif st == "waiting_for_phone":
        user_states[user_id]["phone"] = phone
        user_states[user_id]["state"] = "waiting_for_location"
        await bot.send_message(message.chat.id, "Manzilingizni (Lokatsiya) yuboring:", reply_markup=get_location_menu())

@bot.message_handler(content_types=['location'])
async def handle_location(message):
    user_id = message.from_user.id
    st = user_states.get(user_id, {}).get("state")
    loc = f"https://maps.google.com/?q={message.location.latitude},{message.location.longitude}"

    if st == "waiting_for_location":
        await complete_order(message, user_id, loc)
    elif st == "waiting_location_for_advice":
        await complete_advice_order(message, user_id, loc)

@bot.message_handler(content_types=['photo', 'video', 'text'])
async def handle_all_inputs(message):
    user_id = message.from_user.id
    user_data = user_states.get(user_id, {})
    state = user_data.get("state")

    if state == "step_1_code" and user_id == ADMIN_ID and message.text:
        user_states[user_id] = {"state": "step_2_media", "code": message.text.strip().upper()}
        await bot.send_message(message.chat.id, "2️⃣ Sovg'a rasmi yoki videosini yuboring (yoki matn yozing):")
        return

    elif state == "step_2_media" and user_id == ADMIN_ID:
        file_id = message.photo[-1].file_id if message.photo else (message.video.file_id if message.video else None)
        file_type = "photo" if message.photo else ("video" if message.video else "none")
        user_states[user_id].update({"state": "step_3_name", "file_id": file_id, "file_type": file_type})
        await bot.send_message(message.chat.id, "3️⃣ Sovg'aning nomini yozing:")
        return

    elif state == "step_3_name" and user_id == ADMIN_ID and message.text:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO promo_codes VALUES (?, ?, ?, ?, 0, NULL)", 
                       (user_data["code"], message.text.strip(), user_data["file_id"], user_data["file_type"]))
        conn.commit()
        conn.close()
        await bot.send_message(message.chat.id, "✅ Sovg'a saqlandi!", reply_markup=get_admin_menu())
        user_states.pop(user_id, None)
        return

    if message.text:
        if state == "select_product":
            user_states[user_id] = {"state": "confirm_buying_option", "product": message.text}
            await bot.send_message(
                message.chat.id, 
                "Sizga mutaxassis maslahati kerakmi yoki mahsulot bilan to'liq tanishmisiz?", 
                reply_markup=get_buying_option_menu()
            )

        elif state == "confirm_buying_option":
            if message.text == "👨‍⚕️ Mutaxassis maslahati kerak":
                user_states[user_id]["state"] = "waiting_phone_for_advice"
                await bot.send_message(
                    message.chat.id, 
                    "Mutaxassisimiz sizga qo'ng'iroq qilishi uchun telefon raqamingizni yuboring:", 
                    reply_markup=get_phone_menu()
                )
            elif message.text == "✅ Mahsulot bilan tanishman, xarid qilaman":
                user_states[user_id]["state"] = "waiting_for_phone"
                await bot.send_message(
                    message.chat.id, 
                    "Buyurtmani rasmiylashtirish uchun telefon raqamingizni yuboring:", 
                    reply_markup=get_phone_menu()
                )

        elif state == "waiting_phone_for_advice":
            user_states[user_id]["phone"] = message.text
            user_states[user_id]["state"] = "waiting_location_for_advice"
            await bot.send_message(message.chat.id, "Manzilingizni (Lokatsiya) yuboring:", reply_markup=get_location_menu())

        elif state == "waiting_location_for_advice":
            await complete_advice_order(message, user_id, message.text)

        elif state == "waiting_for_phone":
            user_states[user_id]["phone"] = message.text
            user_states[user_id]["state"] = "waiting_for_location"
            await bot.send_message(message.chat.id, "Manzilingizni kiriting:", reply_markup=get_location_menu())

        elif state == "waiting_for_location":
            await complete_order(message, user_id, message.text)

        elif state == "waiting_for_code":
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT prize, file_id, file_type, is_used FROM promo_codes WHERE code = ?", (message.text.strip().upper(),))
            row = cursor.fetchone()
            if not row:
                await bot.send_message(message.chat.id, "❌ Noto'g'ri kod.")
            elif row[3] == 1:
                await bot.send_message(message.chat.id, "⚠️ Bu kod allaqachon ishlatilgan!")
            else:
                cursor.execute("UPDATE promo_codes SET is_used = 1, used_by = ? WHERE code = ?", (user_id, message.text.strip().upper()))
                conn.commit()
                text = f"🎉 **Tabriklaymiz!**\n\nYutug'ingiz faollashtirildi: {row[0]}"
                if row[2] == "photo": await bot.send_photo(message.chat.id, row[1], caption=text)
                elif row[2] == "video": await bot.send_video(message.chat.id, row[1], caption=text)
                else: await bot.send_message(message.chat.id, text, parse_mode="Markdown")
                user_states.pop(user_id, None)
            conn.close()

async def complete_advice_order(message, user_id, location_data):
    user_data = user_states.get(user_id, {})
    prod = user_data.get("product", "Noma'lum")
    phone = user_data.get("phone", "Noma'lum")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (user_id, product, phone, location, status, courier_id, operator_id) VALUES (?, ?, ?, ?, 'Maslahat kutilmoqda', NULL, NULL)",
                   (user_id, prod, phone, location_data))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await bot.send_message(message.chat.id, "✅ So'rovingiz qabul qilindi. Mutaxassisimiz tez orada siz bilan bog'lanib bepul maslahat beradi!", reply_markup=get_user_menu(user_id))

    op_kb = InlineKeyboardMarkup(row_width=1)
    op_kb.add(
        InlineKeyboardButton("✅ Tasdiqlash (Kuryerga yuborish)", callback_data=f"op_confirm_{order_id}"),
        InlineKeyboardButton("⏳ Jarayonda", callback_data=f"op_process_{order_id}"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data=f"op_cancel_{order_id}")
    )

    op_id = get_operator_id()
    try:
        await bot.send_message(
            op_id,
            f"📞 **MUTAXASSIS MASLAHATI SO'ROVI!**\n\n"
            f"📌 **ID:** #{order_id}\n"
            f"🛍 **Mahsulot:** {prod}\n"
            f"👤 **Mijoz:** {message.from_user.first_name}\n"
            f"📞 **Tel:** {phone}\n"
            f"📍 **Manzil:** {location_data}\n"
            f"📊 **Holat:** Maslahat kutilmoqda",
            reply_markup=op_kb,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Operatorga yuborishda xatolik: {e}")

    user_states.pop(user_id, None)

async def complete_order(message, user_id, location_data):
    user_data = user_states.get(user_id, {})
    prod = user_data.get("product", "Noma'lum")
    phone = user_data.get("phone", "Noma'lum")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (user_id, product, phone, location, status, courier_id, operator_id) VALUES (?, ?, ?, ?, 'Kutilmoqda', NULL, NULL)",
                   (user_id, prod, phone, location_data))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await bot.send_message(message.chat.id, "✅ Buyurtmangiz tasdiqlandi va qabul qilindi! Kuryerimiz tez orada yo'lga chiqadi.", reply_markup=get_user_menu(user_id))

    courier_kb = InlineKeyboardMarkup()
    courier_kb.add(InlineKeyboardButton("📥 Qabul qilish", callback_data=f"accept_{order_id}"))
    
    try:
        await courier_bot.send_message(
            ADMIN_ID,
            f"📦 **YANGI BUYURTMA!**\n\n📌 **ID:** #{order_id}\n🛍 **Mahsulot:** {prod}\n📞 **Tel:** {phone}\n📍 **Manzil:** {location_data}",
            reply_markup=courier_kb,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Kuryer botiga yuborishda xatolik: {e}")

    user_states.pop(user_id, None)

# --- BOTLARNI ISHGA TUSHIRISH ---
async def main():
    init_db()
    await asyncio.gather(
        bot.infinity_polling(),
        courier_bot.infinity_polling()
    )

if __name__ == "__main__":
    asyncio.run(main())
