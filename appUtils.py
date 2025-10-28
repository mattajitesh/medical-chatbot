
import re
import random
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from openai import OpenAI
import os

SENDGRID_KEY = os.getenv("SENDGRID_API_KEY")
# OPENROUTER_KEY=os.getenv("OPENROUTER_API_KEY")


def validate_name(name):
    return bool(re.fullmatch(r"[A-Za-z ]{2,50}", name.strip()))

def validate_email(email):
    return bool(re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email.strip()))

def validate_mobile(mobile):
    return bool(re.fullmatch(r"[6-9]\d{9}", mobile.strip()))

def validate_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

def send_email(to_email, subject, body):
    message = Mail(
        from_email="jiteshmatta2103@gmail.com",  # must be verified in SendGrid
        to_emails=to_email,
        subject=subject,
        plain_text_content=body
    )
    sg = SendGridAPIClient(SENDGRID_KEY)
    response = sg.send(message)
    print(f"✅ Email sent to {to_email}, Status: {response.status_code}")

def get_greeting_message():
    greetings = [
        "🌸 Welcome to HealthBot! 🌸\n“Good health is the greatest wealth.” 💙",
        "👋 Hello! This is your Medical Assistant.\n“An early checkup is better than a late cure.” 🩺",
        "🌟 Hi! I’m HealthBot.\n“Take care of your body, it’s the only place you have to live.” 💪",
        "💚 Welcome to your health companion!\n“Prevention is better than cure.” 🌿"
    ]
    return random.choice(greetings)

HELP_TEXT = """
👋 Welcome to the Healthcare Assistant Chatbot!
Here’s how I can help you today 💬

🩺 Describe Your Symptoms
Example: “I have a headache and fever.”
→ I’ll suggest basic precautions and helpful advice.

📅 Book an Appointment
Type “book appointment” to start the process.
I’ll guide you step by step to collect your:
1️⃣ Full Name
2️⃣ Email ID
3️⃣ Mobile Number
4️⃣ Symptoms
5️⃣ Doctor (based on symptoms)
6️⃣ Appointment Date (📆 YYYY-MM-DD)
7️⃣ Preferred Shift (🌅 Morning / 🌇 Evening)
8️⃣ Time Slot ⏰
✅ Once done, I’ll confirm your appointment and send an 📧 email confirmation.

🔁 Reschedule an Appointment
Type “reschedule appointment” to begin.
→ Provide your serial number, review details, and confirm updates.
→ You can modify the date, shift, and time slot easily.

❌ Cancel an Appointment
Type “cancel appointment” to proceed.
→ Provide your serial number, review details, and confirm cancellation.

💬 Get General Advice
Ask simple health queries like:
🩹 “What should I do for cold and cough?”
🥱 “I feel weak and tired.”
→ I’ll provide concise, helpful advice.

💡 Type “help” anytime to see this guide again.
🔄 Type “restart” to restart the current process.
⚠️ Note: I’m not a replacement for a real doctor. For emergencies, please visit your nearest 🏥 hospital immediately.
"""

def is_health_query(message):
    """Detect if the message is a health-related query."""
    health_keywords = ["fever", "cough", "pain", "headache", "sore", "throat", "cold", "flu", "sick", "ill"]
    return any(keyword in message.lower() for keyword in health_keywords)

def rule_based_health_response(message):
    """Fallback rule-based response for health queries."""
    message = message.lower()
    if "fever" in message:
        return "Take rest and stay hydrated. Monitor your temperature. If symptoms worsen, consult a healthcare provider. You can book an appointment anytime. Just type 'Book appointment'."
    elif "cough" in message or "cold" in message:
        return "Rest, drink warm fluids, and avoid cold exposure. You can book an appointment anytime. Just type 'Book appointment'."
    elif "pain" in message or "headache" in message:
        return "Rest and consider over-the-counter pain relief if needed. You can book an appointment anytime. Just type 'Book appointment'."
    else:
        return "Please rest and monitor your symptoms. You can book an appointment anytime. Just type 'Book appointment'."

def get_llm_response(message):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    try:
        completion = client.chat.completions.create(
            extra_body={},
            model="deepseek/deepseek-chat-v3.1:free",
            messages=[
                {
                    "role": "system",
                    "content": "You are a health assistant. Provide concise advice for health queries (max 50 words) must ends with  You can book an appointment anytime. Just type 'Book appointment'."
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            max_tokens=50,
            temperature=0.7
        )
        response = completion.choices[0].message.content
        # response+= " You can book an appointment anytime. Just type 'Book appointment'."
        return response
    except Exception as e:
        print(f"[get_llm_response] Error: {e}")
        return rule_based_health_response(message)