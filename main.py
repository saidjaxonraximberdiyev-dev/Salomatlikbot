import os
from threading import Thread
from flask import Flask

import asyncio
import sqlite3
from telebot.async_telebot import AsyncTeleBot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

app = Flask('')

@app.route('/')
def home():
    return "Bot ishlayapti!"

def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web).start()

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

init_db()

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
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (user_id, product, phone, location, status, courier_id, operator_id) VALUES (?, ?, ?, ?, 'Kutilmoqda', NULL, NULL)",
                   (user_id, user_data.get("product"), user_data.get("phone"), location_data))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await bot.send_message(message.chat.id, "✅ Buyurtmangiz tasdiqlandi va qabul qilindi! Kuryerimiz tez orada yo'lga chiqadi.", reply_markup=get_user_menu(user_id))

    courier_kb = InlineKeyboardMarkup()
    courier_kb.add(InlineKeyboardButton("📥 Qabul qilish", callback_data=f"accept_{order_id}"))

    # Kuryer botga yuborish qismi (to'liq tugatildi)
    try:
        await courier_bot.send_message(
            ADMIN_ID,
            f"📦 **YANGI BUYURTMA!**\n\n"
            f"📌 **ID:** #{order_id}\n"
            f"🛍 **Mahsulot:** {user_data.get('product')}\n"
            f"📞 **Tel:** {user_data.get('phone')}\n"
            f"📍 **Manzil:** {location_data}",
            reply_markup=courier_kb,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Kuryerga yuborishda xatolik: {e}")

    user_states.pop(user_id, None)

# Botlarni birgalikda ishga tushirish uchun asosiy sikl
async def main():
    await asyncio.gather(
        bot.infinity_polling(),
        courier_bot.infinity_polling()
    )
# Kuryer bot uchun /start buyrug'i
@courier_bot.message_handler(commands=["start"])
async def courier_start(message):
    await courier_bot.send_message(
        message.chat.id,
        "🚚 **Kuryer botga xush kelibsiz!**\n\n"
        "Yangi buyurtmalar shu yerga keladi va ularni qabul qilishingiz mumkin.",
        parse_mode="Markdown",
        reply_markup=get_courier_menu()
    )

# Kuryer buyurtmani qabul qilishi
@courier_bot.callback_query_handler(func=lambda call: call.data.startswith('accept_'))
async def courier_accept_order(call):
    try:
        order_id = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        await courier_bot.answer_callback_query(call.id, "Xatolik yuz berdi!")
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = 'Yo''lda', courier_id = ? WHERE id = ?", (call.from_user.id, order_id))
    conn.commit()
    
    cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()

    await courier_bot.answer_callback_query(call.id, "Buyurtma qabul qilindi! Yo'lga chiqing.")
    await courier_bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    await courier_bot.send_message(call.message.chat.id, f"✅ **#{order_id}**-sonli buyurtma muvaffaqiyatli qabul qilindi.", parse_mode="Markdown")

    if row:
        try:
            await bot.send_message(row[0], "🚚 Kuryerimiz buyurtmangizni qabul qildi va yo'lga chiqdi!")
        except Exception as e:
            print(f"Mijozga xabar berishda xatolik: {e}")
# --- OPERATOR TUGMALARI UCHUN HANDLERLAR ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('op_'))
async def operator_action(call):
    data_parts = call.data.split('_')
    action = data_parts[1] # confirm, process, cancel
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
        
        # Kuryer botga yuborish
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
        await bot.answer_callback_query(call.id, "Holat o'zgartirildi.")
        await bot.edit_message_text(f"⏳ **ID #{order_id}** — Jarayonda", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        
    elif action == 'cancel':
        cursor.execute("UPDATE orders SET status = 'Bekor qilindi' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
        await bot.answer_callback_query(call.id, "Buyurtma bekor qilindi.")
        await bot.edit_message_text(f"❌ **ID #{order_id}** — Bekor qilindi", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# --- KURYER BOT MENYULARI VA TUGMALARI ---
@courier_bot.message_handler(func=lambda msg: msg.text == "🚚 Yo'ldagi buyurtmalarim")
async def courier_on_the_way_orders(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, product, phone, location FROM orders WHERE courier_id = ? AND status = 'Yo''lda'", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await courier_bot.send_message(message.chat.id, "𭭜 Sizda hozirda yo'ldagi buyurtmalar yo'q.")
        return
# --- OPERATOR TUGMALARI UCHUN HANDLERLAR ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('op_'))
async def operator_action(call):
    data_parts = call.data.split('_')
    action = data_parts[1] # confirm, process, cancel
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
        
        # Kuryer botga yuborish
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
        
        # Jarayonda bo'lganda ham operator yana Tasdiqlashi yoki Bekor qilishi uchun tugmalarni qoldiramiz
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"op_confirm_{order_id}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"op_cancel_{order_id}")
        )
        
        await bot.answer_callback_query(call.id, "Holat: Jarayonda (Mijoz bilan gaplashilmoqda)")
        await bot.edit_message_text(
            f"⏳ **ID #{order_id}** — Jarayonda (Mijoz bilan muloqot qilinmoqda)", 
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

# --- KURYER BOT SIRLI /kuryer BUYRUG'I VA MENYULARI ---
@courier_bot.message_handler(commands=['kuryer'])
async def courier_secret_login(message):
    args = message.text.split()
    # Maxfiy parol (buni o'zingiz xohlagan so'zga o'zgartirishingiz mumkin)
    SECRET_PASSWORD = "kuryer123"
    
    if len(args) > 1 and args[1] == SECRET_PASSWORD:
        await courier_bot.send_message(
            message.chat.id,
            "✅ **Maxfiy parol tasdiqlandi!**\nKuryer paneli va barcha imkoniyatlar ochildi.",
            parse_mode="Markdown",
            reply_markup=get_courier_menu()
        )
    else:
        await courier_bot.send_message(
            message.chat.id,
            "🔐 Kuryer panelini ochish uchun maxfiy parolni kiriting.\n\n"
            "**Namuna:** `/kuryer kuryer123`",
            parse_mode="Markdown"
        )

@courier_bot.message_handler(func=lambda msg: msg.text == "🚚 Yo'ldagi buyurtmalarim")
async def courier_on_the_way_orders(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, product, phone, location FROM orders WHERE courier_id = ? AND status = 'Yo''lda'", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await courier_bot.send_message(message.chat.id, "𭭜 Sizda hozirda yo'ldagi buyurtmalar yo'q.")
        return

    for o_id, prod, phone, loc in rows:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Yetkazildi deb belgilash", callback_data=f"deliver_{o_id}"))
        text = f"🚚 **Buyurtma #{o_id}**\n🛍 Mahsulot: {prod}\n📞 Tel: {phone}\n📍 Manzil: {loc}"
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
killall -9 python python3 2>/dev/null; pkill -9 -f python

cat << 'EOF' > main.py
import asyncio
import sqlite3
from telebot.async_telebot import AsyncTeleBot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

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
    # Bazadan operatorlar ishtirok etgan buyurtmalarni yoki umumiy operatorlarni topamiz
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
    # Operator ma'lumotlari
    cursor.execute("SELECT full_name, username FROM users WHERE user_id = ?", (op_id,))
    op_info = cursor.fetchone()
    op_name = op_info[0] if op_info else "Noma'lum"
    op_uname = f"@{op_info[1]}" if op_info and op_info[1] else "Niksiz"

    # Operator sotgan buyurtmalar
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
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (user_id, product, phone, location, status, courier_id, operator_id) VALUES (?, ?, ?, ?, 'Kutilmoqda', NULL, NULL)",
                   (user_id, user_data.get("product"), user_data.get("phone"), location_data))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await bot.send_message(message.chat.id, "✅ Buyurtmangiz tasdiqlandi va qabul qilindi! Kuryerimiz tez orada yo'lga chiqadi.", reply_markup=get_user_menu(user_id))

    courier_kb = InlineKeyboardMarkup()
    courier_kb.add(InlineKeyboardButton("📥 Qabul qilish", callback_data=f"accept_{order_id}"))
    
    try:
        await courier_bot.send_message(
            ADMIN_ID,
            f"🚨 **YANGI BUYURTMA #{order_id}!**\n\n📦 Mahsulot: {user_data.get('product')}\n📞 Tel: {user_data.get('phone')}\n📍 Manzil: {location_data}",
            reply_markup=courier_kb,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Kuryer bot xatolik: {e}")
        
    user_states.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith('op_'))
async def handle_operator_action(call):
    data = call.data.split("_")
    action = data[1]
    order_id = int(data[2])
    operator_user_id = call.from_user.id

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, product, phone, location FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()

    if not row:
        await bot.answer_callback_query(call.id, "Buyurtma topilmadi!")
        conn.close()
        return

    u_id, prod, phone, loc = row

    if action == "confirm":
        cursor.execute("UPDATE orders SET status = 'Tasdiqlandi', courier_id = NULL, operator_id = ? WHERE id = ?", (operator_user_id, order_id))
        conn.commit()
        conn.close()

        new_text = (
            f"✅ **BUYURTMA TASDIQLANDI VA KURYERGA YUBORILDI!**\n\n"
            f"📌 **ID:** #{order_id}\n"
            f"🛍 **Mahsulot:** {prod}\n"
            f"📞 **Tel:** {phone}\n"
            f"📍 **Manzil:** {loc}\n"
            f"📊 **Holat:** Tasdiqlandi (Kuryer kutilmoqda)"
        )
        await bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

        try:
            await bot.send_message(u_id, f"🎉 Mutaxassis maslahatidan so'ng #{order_id} raqamli buyurtmangiz tasdiqlandi va kuryerga yetkazildi!")
        except Exception as e:
            print(f"Mijozga yuborish xatosi: {e}")

        courier_kb = InlineKeyboardMarkup()
        courier_kb.add(InlineKeyboardButton("📥 Qabul qilish", callback_data=f"accept_{order_id}"))
        try:
            await courier_bot.send_message(
                ADMIN_ID,
                f"🚨 **YANGI BUYURTMA #{order_id}!** (Mutaxassis tasdiqladi)\n\n📦 Mahsulot: {prod}\n📞 Tel: {phone}\n📍 Manzil: {loc}",
                reply_markup=courier_kb,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Kuryer bot xatosi: {e}")

        await bot.answer_callback_query(call.id, "Buyurtma kuryerga yuborildi!")

    elif action == "process":
        cursor.execute("UPDATE orders SET status = 'Jarayonda' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()

        op_kb = InlineKeyboardMarkup(row_width=1)
        op_kb.add(
            InlineKeyboardButton("✅ Tasdiqlash (Kuryerga yuborish)", callback_data=f"op_confirm_{order_id}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"op_cancel_{order_id}")
        )

        new_text = (
            f"⏳ **MASLAHAT JARAYONDA...**\n\n"
            f"📌 **ID:** #{order_id}\n"
            f"🛍 **Mahsulot:** {prod}\n"
            f"📞 **Tel:** {phone}\n"
            f"📍 **Manzil:** {loc}\n"
            f"📊 **Holat:** Jarayonda"
        )
        await bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id, reply_markup=op_kb, parse_mode="Markdown")
        await bot.answer_callback_query(call.id, "Holat: Jarayonda qilib belgilandi.")

    elif action == "cancel":
        cursor.execute("UPDATE orders SET status = 'Bekor qilindi' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()

        new_text = (
            f"❌ **BUYURTMA BEKOR QILINDI**\n\n"
            f"📌 **ID:** #{order_id}\n"
            f"🛍 **Mahsulot:** {prod}\n"
            f"📞 **Tel:** {phone}\n"
            f"📍 **Manzil:** {loc}\n"
            f"📊 **Holat:** Bekor qilindi"
        )
        await bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

        try:
            await bot.send_message(u_id, f"❌ Sizning #{order_id} raqamli buyurtmangiz bekor qilindi.")
        except Exception as e:
            print(f"Mijozga yuborish xatosi: {e}")

        await bot.answer_callback_query(call.id, "Buyurtma bekor qilindi!")

# --- KURYER BOT HANDLERLARI ---

@courier_bot.message_handler(commands=["start"])
async def courier_start_handler(message):
    await courier_bot.send_message(message.chat.id, "🚚 **Kuryer Botiga xush kelibsiz!**\nYangi buyurtmalar kelganda shu yerda ko'rinasiz.", parse_mode="Markdown")

@courier_bot.callback_query_handler(func=lambda call: call.data.startswith('accept_'))
async def accept_order(call):
    try:
        order_id = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        await courier_bot.answer_callback_query(call.id, "❌ Xatolik!")
        return

    courier_id = call.from_user.id

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, product, phone, location, status, courier_id FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()

    if not row:
        await courier_bot.answer_callback_query(call.id, "❌ Buyurtma topilmadi!", show_alert=True)
        conn.close()
        return

    u_id, prod, phone, loc, status, courier_assigned = row

    if courier_assigned is not None or status in ['Yo\'lda', 'Yetkazildi', 'Bekor qilindi']:
        await courier_bot.answer_callback_query(call.id, f"⚠️ Buyurtma #{order_id} allaqachon olingan!", show_alert=True)
        conn.close()
        return

    cursor.execute("UPDATE orders SET status = 'Yo''lda', courier_id = ? WHERE id = ?", (courier_id, order_id))
    conn.commit()
    conn.close()

    delivered_kb = InlineKeyboardMarkup()
    delivered_kb.add(InlineKeyboardButton("✅ Yetkazib berildi", callback_data=f"delivered_{order_id}"))

    text = (
        f"🚚 **BUYURTMA YO'LDA (QABUL QILINDI)!**\n\n"
        f"📌 **ID:** #{order_id}\n"
        f"📦 **Mahsulot:** {prod}\n"
        f"📞 **Tel:** {phone}\n"
        f"📍 **Manzil:** {loc}\n"
        f"📊 **Holat:** Yo'lda"
    )
    await courier_bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=delivered_kb, parse_mode="Markdown")
    await courier_bot.answer_callback_query(call.id, "✅ Buyurtma qabul qilindi. Yo'lga chiqing!")

    try:
        await bot.send_message(u_id, f"🚚 #{order_id} raqamli buyurtmangiz kuryer tomonidan ombordan olindi va yo'lga chiqdi!")
    except Exception as e:
        print(f"Mijozga yuborishda xatolik: {e}")

@courier_bot.callback_query_handler(func=lambda call: call.data.startswith('delivered_'))
async def delivered_order(call):
    try:
        order_id = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        await courier_bot.answer_callback_query(call.id, "❌ Xatolik!")
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, product, phone, location FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()

    if not row:
        await courier_bot.answer_callback_query(call.id, "❌ Buyurtma topilmadi!", show_alert=True)
        conn.close()
        return

    u_id, prod, phone, loc = row

    cursor.execute("UPDATE orders SET status = 'Yetkazildi' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

    text = (
        f"✅ **BUYURTMA YETKAZIB BERILDI!**\n\n"
        f"📌 **ID:** #{order_id}\n"
        f"📦 **Mahsulot:** {prod}\n"
        f"📞 **Tel:** {phone}\n"
        f"📍 **Manzil:** {loc}\n"
        f"📊 **Holat:** Muvaffaqiyatli yetkazildi"
    )
    await courier_bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    await courier_bot.answer_callback_query(call.id, "🎉 Buyurtma yetkazildi!")

    try:
        await bot.send_message(u_id, f"🎉 #{order_id} raqamli buyurtmangiz muvaffaqiyatli yetkazib berildi. Xaridingiz uchun rahmat!")
    except Exception as e:
        print(f"Mijozga yuborishda xatolik: {e}")

async def main():
    init_db()
    print("🚀 Botlar birgalikda muvaffaqiyatli ishga tushdi...")
    await asyncio.gather(
        bot.polling(non_stop=True, skip_pending=True),
        courier_bot.polling(non_stop=True, skip_pending=True)
    )

if __name__ == "__main__":
    asyncio.run(main())
EOF

if __name__ == "__main__":
    asyncio.run(main())
