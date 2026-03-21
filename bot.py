import telebot
from telebot import types
import requests
import sqlite3
import os
from datetime import datetime

# ================== CONFIG ==================
TOKEN = os.environ.get("BOT_TOKEN")
API_KEY = os.environ.get("OPENWEATHER_KEY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))   # Put your own Telegram user ID here

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ================== DATABASE ==================
conn = sqlite3.connect("subscribers.db", check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS subscribers 
             (user_id INTEGER PRIMARY KEY, language TEXT DEFAULT 'en')""")
conn.commit()

# ================== FLOOD ZONES (Latest 2025-2026) ==================
FLOOD_ZONES = [
    "Garia", "Jadavpur", "Tollygunge", "Behala", "Ballygunge",
    "Bansdroni", "Gariahat", "Salt Lake", "Rajarhat", "New Town",
    "EM Bypass", "Park Street", "Camac Street", "Amherst Street",
    "Howrah", "Alipore", "Kalighat", "Sonarpur"
]

# ================== KEYBOARD ==================
def get_keyboard(lang="en"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if lang == "hi":
        markup.add("🌧️ मौसम", "⚠️ अलर्ट", "🌊 बाढ़ क्षेत्र", "💡 टिप्स")
        markup.add("📲 सब्सक्राइब", "❌ अनसब्सक्राइब", "❓ मदद")
    else:
        markup.add("🌧️ Weather", "⚠️ Alert", "🌊 Flood Zones", "💡 Tips")
        markup.add("📲 Subscribe", "❌ Unsubscribe", "❓ Help")
    return markup

# ================== HELPER FUNCTIONS ==================
def get_user_lang(user_id):
    c.execute("SELECT language FROM subscribers WHERE user_id=?", (user_id,))
    row = c.fetchone()
    return row[0] if row else "en"

def save_user(user_id, lang="en"):
    c.execute("INSERT OR REPLACE INTO subscribers (user_id, language) VALUES (?, ?)", (user_id, lang))
    conn.commit()

def is_subscribed(user_id):
    c.execute("SELECT user_id FROM subscribers WHERE user_id=?", (user_id,))
    return c.fetchone() is not None

# ================== WEATHER FETCH ==================
def get_weather(city="Kolkata,IN", lang="en"):
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric&lang={'hi' if lang=='hi' else 'en'}"
    try:
        data = requests.get(url, timeout=10).json()
        if data["cod"] != "200":
            return "Sorry, weather service is down right now."

        current = data["list"][0]
        temp = current["main"]["temp"]
        desc = current["weather"][0]["description"]
        rain_prob = round(current.get("pop", 0) * 100)
        wind = current["wind"]["speed"]
        rain_mm = current.get("rain", {}).get("3h", 0)

        # Next 3-6 hours
        next_hours = data["list"][1:3]
        forecast = "\n".join([f"• {int(item['dt']-data['list'][0]['dt'])/3600:.0f}h: {item['weather'][0]['description']} ({round(item.get('pop',0)*100)}% rain)" for item in next_hours])

        risk = "🟠 ORANGE ALERT" if rain_prob > 70 or "thunderstorm" in desc.lower() else "🟡 YELLOW ALERT" if rain_prob > 40 else "✅ Low risk"

        return f"""🌧️ <b>Kolkata Weather</b>

🌡️ {temp}°C | 💨 {wind} m/s
☁️ {desc.capitalize()}
🌧️ Rain chance: {rain_prob}% | Rain: {rain_mm} mm

{risk}

Next 6 hours:
{forecast}"""
    except Exception as e:
        return "Error fetching weather. Try again later."

# ================== HANDLERS ==================
@bot.message_handler(commands=["start"])
def start(message):
    lang = get_user_lang(message.chat.id)
    save_user(message.chat.id, lang)
    text = "🌧️ <b>Welcome to Kolkata Rain & Flood Alert Bot!</b>\n\nGet instant weather, flood alerts & safety tips for Kolkata.\nUse the buttons below 👇" if lang == "en" else "🌧️ <b>कोलकाता रेन एंड फ्लड अलर्ट बॉट में स्वागत है!</b>\n\nकोलकाता के मौसम, बाढ़ अलर्ट और टिप्स पाएं। नीचे बटन इस्तेमाल करें 👇"
    bot.send_message(message.chat.id, text, reply_markup=get_keyboard(lang))

@bot.message_handler(commands=["weather", "मौसम"])
def weather_cmd(message):
    lang = get_user_lang(message.chat.id)
    bot.send_message(message.chat.id, get_weather(lang=lang))

@bot.message_handler(commands=["alert", "अलर्ट"])
def alert_cmd(message):
    lang = get_user_lang(message.chat.id)
    # Using same weather logic for alert
    weather_text = get_weather(lang=lang)
    if "ORANGE ALERT" in weather_text or "🟠" in weather_text:
        extra = "⚠️ Heavy rain & thunderstorm possible today. Avoid low-lying areas!" if lang=="en" else "⚠️ आज भारी बारिश और गरज-चमक संभव। निचले इलाकों से बचें!"
    elif "YELLOW ALERT" in weather_text or "🟡" in weather_text:
        extra = "🟡 Moderate rain expected. Carry umbrella & check roads." if lang=="en" else "🟡 मध्यम बारिश की संभावना। छाता लेकर निकलें और सड़कों की जाँच करें।"
    else:
        extra = "✅ No major rain risk today."
    bot.send_message(message.chat.id, f"<b>Rain Alert for Kolkata</b>\n\n{extra}")

@bot.message_handler(commands=["floodzones", "बाढ़ क्षेत्र"])
def flood_cmd(message):
    lang = get_user_lang(message.chat.id)
    zones = "\n• ".join(FLOOD_ZONES)
    text = f"<b>🚨 Flood-Prone Areas in Kolkata (Latest 2025-26)</b>\n\n• {zones}\n\n⚠️ Avoid these during heavy rain. Water clears slower here." if lang=="en" else f"<b>🚨 कोलकाता के बाढ़ प्रभावित क्षेत्र (2025-26)</b>\n\n• {zones}\n\n⚠️ भारी बारिश में इन इलाकों से बचें।"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["tips", "टिप्स"])
def tips_cmd(message):
    lang = get_user_lang(message.chat.id)
    text = """💡 <b>Safety Tips During Rain</b>

• Charge your phone fully
• Avoid low-lying areas & underpasses
• Carry umbrella + raincoat
• Don't touch electric poles in water
• Keep emergency contacts ready
• Use metro/uber if roads are bad""" if lang=="en" else """💡 <b>बारिश के दौरान सुरक्षा टिप्स</b>

• फोन पूरी चार्ज रखें
• निचले इलाकों और अंडरपास से बचें
• छाता + रेनकोट साथ रखें
• पानी में बिजली के खंभों को न छुएं
• इमरजेंसी कॉन्टैक्ट तैयार रखें
• सड़कें खराब हों तो मेट्रो/उबर यूज करें"""
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["subscribe", "सब्सक्राइब"])
def subscribe(message):
    lang = get_user_lang(message.chat.id)
    save_user(message.chat.id, lang)
    text = "✅ You are now subscribed for priority alerts!" if lang=="en" else "✅ आप अब प्राथमिकता अलर्ट के लिए सब्सक्राइब हो गए!"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["unsubscribe", "अनसब्सक्राइब"])
def unsubscribe(message):
    c.execute("DELETE FROM subscribers WHERE user_id=?", (message.chat.id,))
    conn.commit()
    text = "❌ You have been unsubscribed." if get_user_lang(message.chat.id)=="en" else "❌ आप अनसब्सक्राइब हो गए।"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["help", "मदद"])
def help_cmd(message):
    lang = get_user_lang(message.chat.id)
    text = "Just click the buttons or type commands. Bot updates every 3 hours.\n\nFor daily morning alert → stay subscribed!" if lang=="en" else "बस बटन दबाएं या कमांड टाइप करें। बॉट हर 3 घंटे अपडेट होता है।"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["hindi"])
def set_hindi(message):
    save_user(message.chat.id, "hi")
    bot.send_message(message.chat.id, "✅ भाषा हिंदी में सेट हो गई। अब सभी मैसेज हिंदी में आएंगे!", reply_markup=get_keyboard("hi"))

@bot.message_handler(commands=["english"])
def set_english(message):
    save_user(message.chat.id, "en")
    bot.send_message(message.chat.id, "✅ Language set to English.", reply_markup=get_keyboard("en"))

@bot.message_handler(commands=["broadcast"])
def broadcast(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "Admin only!")
        return
    try:
        text = message.text.split(maxsplit=1)[1]
        c.execute("SELECT user_id FROM subscribers")
        for row in c.fetchall():
            try:
                bot.send_message(row[0], f"📢 <b>Broadcast:</b>\n\n{text}")
            except:
                pass
        bot.reply_to(message, "Broadcast sent to all subscribers!")
    except:
        bot.reply_to(message, "Use: /broadcast Your message here")

# ================== TEXT HANDLER (for keyboard clicks) ==================
@bot.message_handler(content_types=["text"])
def handle_text(message):
    lang = get_user_lang(message.chat.id)
    txt = message.text.lower()
    
    if "weather" in txt or "मौसम" in txt:
        weather_cmd(message)
    elif "alert" in txt or "अलर्ट" in txt:
        alert_cmd(message)
    elif "flood" in txt or "बाढ़" in txt:
        flood_cmd(message)
    elif "tips" in txt or "टिप्स" in txt:
        tips_cmd(message)
    elif "subscribe" in txt or "सब्सक्राइब" in txt:
        subscribe(message)
    elif "unsubscribe" in txt or "अनसब्सक्राइब" in txt:
        unsubscribe(message)
    elif "help" in txt or "मदद" in txt:
        help_cmd(message)

# ================== START BOT ==================
print("Kolkata Rain Bot is running...")
bot.infinity_polling()
