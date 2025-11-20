🤖 MedBot – Healthcare Assistant Chatbot

A conversational healthcare assistant built with Flask, SQLite, and a hybrid rule-based + LLM workflow.
MedBot helps users describe symptoms, book appointments, reschedule or cancel them, and get quick health advice.

<img width="2145" height="1183" alt="image" src="https://github.com/user-attachments/assets/b14bc16e-bff6-48b4-8b6e-3a07daf92ed1" />

🌟 Features
🩺 1. Symptom-Based Guidance

Users can describe symptoms such as:

"I have a headache and fever"


MedBot provides basic precautions and initial suggestions.

📅 2. Book an Appointment

Start by typing:

book appointment


MedBot collects details step-by-step:

1️⃣ Full Name
2️⃣ Email ID
3️⃣ Mobile Number
4️⃣ Symptoms
5️⃣ Doctor Recommendation (based on symptoms)
6️⃣ Appointment Date (YYYY-MM-DD)
7️⃣ Shift – Morning 🌅 / Evening 🌇
8️⃣ Time Slot ⏰

✔ Confirms the appointment
✔ Sends an email confirmation

🔁 3. Reschedule Appointment

Start with:

reschedule appointment


Reschedule using either:

Mobile Number

Serial Number

You can update:
✔ Date
✔ Shift
✔ Time Slot

❌ 4. Cancel Appointment

Start with:

cancel appointment


Cancel using:

Mobile Number

Serial Number

MedBot shows your appointment details before confirming cancellation.

💬 5. General Health Advice

Ask quick health FAQs such as:

“What should I do for cold and cough?”

“I feel weak and tired.”

MedBot gives short, helpful advice (non-medical).

⛑ Special Commands
help     → Shows user guide
restart  → Restarts session
emergency → Advises immediate hospital visit


⚠ Note: This bot is not a replacement for a medical professional.
For emergencies, visit your nearest hospital immediately.

🛠 Tech Stack

Python Flask

Flask-SQLAlchemy + SQLite

dotenv

Rule-based conversation engine

Optional LLM integration for health-query answers






