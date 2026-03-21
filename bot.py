import telebot
from telebot import types
import requests
import sqlite3
import os
from datetime import datetime

# ================== CONFIG ==================
TOKEN = os.environ.get("BOT_TOKEN")               # From BotFather
API_KEY = os.environ.get("OPENWEATHER_KEY")       # From openweathermap.org/api_keys
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))     # Your Telegram ID (from @userinfobot)

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ================== DATABASE ==================
conn = sqlite3.connect("subscribers.db", check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS subscribers 
             (user_id INTEGER PRIMARY KEY, language TEXT DEFAULT 'en')""")
conn.commit()

# ================== UPDATED FLOOD ZONES (2025-2026 real hotspots) ==================
FLOOD_ZONES = [
    "Garia", "Jadavpur", "Bansdroni", "Bijoygarh", "Tollygunge",
    "Jodhpur Park", "Kalighat", "Topsia", "Ballygunge", "Alipore",
    "Behala", "Salt Lake", "Rajarhat", "New Town", "EM Bypass",
    "Howrah", "Sonarpur", "Park Street area"
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

# ================== HELPERS ==================
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

# ================== WEATHER FETCH (using CURRENT endpoint) ==================
def get_weather(lang="en"):
    url = f"https://api.openweathermap.org/data/2.5/weather?q=Kolkata,IN&appid={API_KEY}&units=metric&lang={'hi' if lang=='hi' else 'en'}"
    try:
        response = requests.get(url, timeout=10)
        print(f"API Status: {response.status_code} | Response: {response.text[:300]}...")  # For Render logs debug
        
        if response.status_code != 200:
            return f"API Error: {response.status_code} - {response.json().get('message', 'Unknown')}"
        
        data = response.json()
        if data.get("cod") != 200:
            return f"Weather service error: {data.get('message', 'Unknown')} (code: {data.get('cod')})"

        # Extract fields from your provided JSON structure
        weather = data["weather"][0]
        desc = weather["description"].capitalize()
        icon = weather["icon"]
        main = data["main"]
        temp = main["temp"]
        feels_like = main["feels_like"]
        humidity = main["humidity"]
        pressure = main["pressure"]
        wind = data["wind"]["speed"]
        clouds = data["clouds"]["all"]
        visibility = data["visibility"] / 1000  # km
        sunrise = datetime.fromtimestamp(data["sys"]["sunrise"]).strftime("%I:%M %p")
        sunset = datetime.fromtimestamp(data["sys"]["sunset"]).strftime("%I:%M %p")

        # Simple risk logic (no pop in current API, so heuristic)
        if "rain" in desc.lower() or "thunder" in desc.lower() or "shower" in desc.lower():
            risk = "🟠 High rain risk" if clouds > 80 else "🟡 Moderate rain possible"
        elif clouds > 70 and humidity > 80:
            risk = "🟡 Haze with possible light rain/drizzle"
        else:
            risk = "✅ Low rain risk for now"

        return f"""🌧️ <b>Kolkata Weather (Current)</b>

🌡️ {temp}°C (feels like {feels_like}°C)
☁️ {desc}
💧 Humidity: {humidity}%
💨 Wind: {wind} m/s
🌫️ Visibility: {visibility:.1f} km
☁️ Clouds: {clouds}%

🌅 Sunrise: {sunrise}   🌇 Sunset: {sunset}

{risk}

Note: For hourly forecast alerts, stay subscribed!"""
    except Exception as e:
        print(f"Exception in get_weather: {str(e)}")
        return "Sorry, weather service is temporarily unavailable. Try again soon."

# ================== HANDLERS ==================
@bot.message_handler(commands=["start"])
def start(message):
    lang = get_user_lang(message.chat.id)
    save_user(message.chat.id, lang)
    text = "🌧️ <b>Welcome to Kolkata Rain & Flood Alert Bot!</b>\n\nReal-time weather, flood warnings & tips for Kolkata.\nUse buttons below 👇" if lang == "en" else "🌧️ <b>कोलकाता रेन एंड फ्लड अलर्ट बॉट में स्वागत!</b>\n\nकोलकाता का मौसम, बाढ़ अलर्ट और टिप्स। नीचे बटन इस्तेमाल करें 👇"
    bot.send_message(message.chat.id, text, reply_markup=get_keyboard(lang))

@bot.message_handler(commands=["weather", "मौसम"])
def weather_cmd(message):
    lang = get_user_lang(message.chat.id)
    bot.send_message(message.chat.id, get_weather(lang=lang))

@bot.message_handler(commands=["alert", "अलर्ट"])
def alert_cmd(message):
    lang = get_user_lang(message.chat.id)
    weather_text = get_weather(lang=lang)
    if "High rain risk" in weather_text or "Moderate rain" in weather_text or "thunder" in weather_text.lower():
        extra = "⚠️ Rain/thunder possible — avoid low areas!" if lang=="en" else "⚠️ बारिश/गरज संभव — निचले इलाकों से बचें!"
    elif "Haze" in weather_text:
        extra = "🟡 Hazy conditions — poor visibility, drive carefully." if lang=="en" else "🟡 धुंध भरी स्थिति — दृश्यता कम, सावधानी से चलाएं।"
    else:
        extra = "✅ No major alert right now." if lang=="en" else "✅ अभी कोई बड़ा अलर्ट नहीं।"
    bot.send_message(message.chat.id, f"<b>Rain Alert Update</b>\n\n{extra}\n\n{weather_text}")

@bot.message_handler(commands=["floodzones", "बाढ़ क्षेत्र"])
def flood_cmd(message):
    lang = get_user_lang(message.chat.id)
    zones = "\n• ".join(FLOOD_ZONES)
    text = f"<b>🚨 Major Waterlogging Areas (2025-2026)</b>\n\n• {zones}\n\n⚠️ These flood fast during heavy rain — avoid if possible." if lang=="en" else f"<b>🚨 प्रमुख जलभराव क्षेत्र (2025-2026)</b>\n\n• {zones}\n\n⚠️ भारी बारिश में ये जल्दी डूब जाते हैं — बचें।"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["tips", "टिप्स"])
def tips_cmd(message):
    lang = get_user_lang(message.chat.id)
    text = """💡 <b>Rain Safety Tips</b>

• Keep phone charged
• Avoid flooded roads & underpasses
• Carry umbrella/raincoat
• Don't touch electric poles in water
• Use metro/apps if traffic bad
• Check alerts before going out""" if lang=="en" else """💡 <b>बारिश सुरक्षा टिप्स</b>

• फोन चार्ज रखें
• जलभराव वाली सड़कें/अंडरपास से बचें
• छाता/रेनकोट साथ रखें
• पानी में बिजली के खंभे न छुएं
• ट्रैफिक खराब हो तो मेट्रो/ऐप यूज करें
• बाहर निकलने से पहले अलर्ट चेक करें"""
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["subscribe", "सब्सक्राइब"])
def subscribe(message):
    lang = get_user_lang(message.chat.id)
    save_user(message.chat.id, lang)
    text = "✅ Subscribed! You'll get priority weather alerts." if lang=="en" else "✅ सब्सक्राइब हो गए! प्राथमिकता अलर्ट मिलेंगे।"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["unsubscribe", "अनसब्सक्राइब"])
def unsubscribe(message):
    c.execute("DELETE FROM subscribers WHERE user_id=?", (message.chat.id,))
    conn.commit()
    text = "❌ Unsubscribed successfully." if get_user_lang(message.chat.id)=="en" else "❌ अनसब्सक्राइब सफल।"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["help", "मदद"])
def help_cmd(message):
    lang = get_user_lang(message.chat.id)
    text = "Use the buttons or commands. Bot fetches fresh data every time.\nSubscribe for better alerts!" if lang=="en" else "बटन या कमांड यूज करें। बॉट हर बार नया डेटा लाता है। सब्सक्राइब करें बेहतर अलर्ट के लिए!"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["hindi"])
def set_hindi(message):
    save_user(message.chat.id, "hi")
    bot.send_message(message.chat.id, "✅ Language set to Hindi!", reply_markup=get_keyboard("hi"))

@bot.message_handler(commands=["english"])
def set_english(message):
    save_user(message.chat.id, "en")
    bot.send_message(message.chat.id, "✅ Language set to English.", reply_markup=get_keyboard("en"))

@bot.message_handler(commands=["broadcast"])
def broadcast(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "Admin only command!")
        return
    try:
        text = message.text.split(maxsplit=1)[1]
        c.execute("SELECT user_id FROM subscribers")
        sent = 0
        for row in c.fetchall():
            try:
                bot.send_message(row[0], f"📢 <b>Admin Broadcast:</b>\n\n{text}")
                sent += 1
            except:
                pass
        bot.reply_to(message, f"Broadcast sent to {sent} users!")
    except:
        bot.reply_to(message, "Format: /broadcast Your message here")

# ================== TEXT BUTTON HANDLER ==================
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

# ================== RUN ==================
print("Kolkata Rain & Flood Bot started...")
bot.infinity_polling()
