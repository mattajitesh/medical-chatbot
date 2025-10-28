# app.py
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from models import db, Doctor, Appointment
from appUtils import (
    validate_name, validate_email, validate_mobile, validate_date,
    send_email, get_greeting_message, HELP_TEXT, get_llm_response, is_health_query
)
from appointmentService import book_appointment, cancel_appointment, reschedule_appointment

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///healthbot.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# In-memory user sessions (Consider Redis or database for production)
user_sessions = {}

@app.before_request
def create_tables():
    db.create_all()
    if not Doctor.query.first():
        doctors = [
            Doctor(name="Dr. Jinni Joffer", speciality="General Physician", consultation_fee=500),
            Doctor(name="Dr. Nia Sharma", speciality="Cardiologist", consultation_fee=800),
            Doctor(name="Dr. Mrunal Sharma", speciality="Dermatologist", consultation_fee=650),
            Doctor(name="Dr. Rakesh Jaha", speciality="Dermatologist", consultation_fee=700),
            Doctor(name="Dr. Purva Deshmukh", speciality="Gastroenterologist", consultation_fee=700),
        ]
        db.session.add_all(doctors)
        db.session.commit()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_id = data.get("user_id", "default")
    user_message = data.get("message", "").strip()

    booking_stages = ["name", "email", "mobile", "symptoms", "choose_doctor", "date", "time", "slot_choice", "confirmation"]
    cancel_stages = ["awaiting_serial", "confirm_cancel"]
    reschedule_stages = ["awaiting_serial", "confirm_reschedule", "date", "time", "slot_choice", "confirmation"]

    # Log incoming message and session state
    app.logger.debug(f"[chat] User ID: {user_id}, Message: {user_message}, Session: {user_sessions.get(user_id)}")

    # Handle specific commands first
    if user_message.lower() in ["hi", "hello", "hey"]:
        user_sessions.pop(user_id, None)
        return jsonify({"response": get_greeting_message() + "\n\nHow can I assist you?"})
    elif user_message.lower() == "help":
        user_sessions.pop(user_id, None)
        return jsonify({"response": HELP_TEXT})
    elif user_message.lower() == "restart":
        user_sessions.pop(user_id, None)
        app.logger.debug(f"[chat] Session cleared for user {user_id} on restart")
        return jsonify({"response": get_greeting_message() + "\n\nHow can I assist you?"})
    elif user_message.lower() in ["cancel", "cancel appointment"]:
        user_sessions[user_id] = {"stage": "awaiting_serial", "flow": "cancel"}
        app.logger.debug(f"[chat] Initiating cancel flow for user {user_id}, Session: {user_sessions[user_id]}")
        return jsonify({"response": "Please provide the serial number of the appointment to cancel."})
    elif user_message.lower() in ["reschedule", "reschedule appointment"]:
        user_sessions[user_id] = {"stage": "awaiting_serial", "flow": "reschedule"}
        app.logger.debug(f"[chat] Initiating reschedule flow for user {user_id}, Session: {user_sessions[user_id]}")
        return jsonify({"response": "Please provide the serial number of the appointment to reschedule."})
    elif user_message.lower() == "emergency":
        user_sessions.pop(user_id, None)
        return jsonify({
            "response": "This seems like a medical emergency. "
                        "Please call your local emergency number 108/112 "
                        "or go to the nearest hospital immediately."
        })
    elif "appointment" in user_message.lower():
        user_sessions[user_id] = {"stage": "name", "flow": "book"}
        app.logger.debug(f"[chat] Initiating booking flow for user {user_id}, Session: {user_sessions[user_id]}")
        return jsonify({"response": "What is your name?"})
    elif is_health_query(user_message):
        app.logger.debug(f"[chat] Health query detected for user {user_id}: {user_message}")
        response = get_llm_response(user_message)
        return jsonify({"response": response})

    # Check for existing session
    session = user_sessions.get(user_id)
    if not session:
        app.logger.debug(f"[chat] No session found for user {user_id}, prompting restart")
        return jsonify({"response": "Hi, I'm your healthbot.\n I can help you with the following:\n - Type 'appointment' to book a new appointment\n - Type 'reschedule' to reschedule an existing appointment\n - Type 'cancel' to cancel an appointment\n - Type 'emergency' for urgent help\n - Type 'help' to see this message again\n - Type 'restart' to start over"})

    stage = session.get("stage")
    flow = session.get("flow", "unknown")
    app.logger.debug(f"[chat] Current stage for {user_id} = {stage}, flow = {flow}, Session: {session}")

    # Handle rescheduling flow
    if flow == "reschedule" and stage in reschedule_stages:
        app.logger.debug(f"[chat] Routing to reschedule_appointment for user {user_id}, stage: {stage}, Session: {session}")
        return reschedule_appointment(user_id, user_message, user_sessions)

    # Handle booking flow
    if flow == "book" and stage in booking_stages:
        app.logger.debug(f"[chat] Routing to book_appointment for user {user_id}, stage: {stage}, Session: {session}")
        return book_appointment(user_id, user_message, user_sessions)

    # Handle cancellation flow
    if flow == "cancel" and stage in cancel_stages:
        app.logger.debug(f"[chat] Routing to cancel_appointment for user {user_id}, stage: {stage}, Session: {session}")
        if stage == "awaiting_serial":
            serial = user_message.strip().lower()
            if not serial:
                return jsonify({"response": "Please send the serial number (e.g., a UUID like 123e4567-e89b-12d3-a456-426614174000)."})
            appointment = Appointment.query.filter_by(serial_number=serial).first()
            if not appointment:
                user_sessions.pop(user_id, None)
                app.logger.debug(f"[chat] No appointment found for serial {serial}, session cleared")
                return jsonify({"response": f"No appointment found with serial number '{serial}'. Start again with 'cancel' or 'reschedule'."})
            if appointment.status and appointment.status.lower() == "cancelled":
                user_sessions.pop(user_id, None)
                app.logger.debug(f"[chat] Appointment {serial} already cancelled, session cleared")
                return jsonify({"response": f"Appointment {serial} is already cancelled."})

            # Fetch doctor details for the appointment
            doctor = Doctor.query.get(appointment.doctor_id)
            if not doctor:
                user_sessions.pop(user_id, None)
                app.logger.debug(f"[chat] Doctor not found for ID {appointment.doctor_id}, session cleared")
                return jsonify({"response": "❌ Doctor not found for this appointment. Please type 'restart'."})

            details_msg = (
                f"Found appointment {serial}:\n\n"
                f"👤 Patient: {appointment.patient_name}\n"
                f"📧 Email: {appointment.patient_email}\n"
                f"📱 Mobile: {appointment.patient_mobile}\n"
                f"👨‍⚕️ Doctor: {doctor.name}\n"
                f"🏥 Speciality: {doctor.speciality}\n"
                f"📅 Date: {appointment.appointment_time.date()}\n"
                f"⏰ Time: {appointment.appointment_time.strftime('%I:%M %p')}\n\n"
            )

            details_msg += "Reply 'yes' to confirm cancellation or 'no' to abort."
            user_sessions[user_id] = {"stage": "confirm_cancel", "serial_number": serial, "flow": "cancel"}
            app.logger.debug(f"[chat] Moving to confirm_cancel stage for user {user_id}, serial: {serial}, Session: {user_sessions[user_id]}")
            return jsonify({"response": details_msg})

        if stage == "confirm_cancel":
            if user_message.lower() in ["yes", "y"]:
                app.logger.debug(f"[chat] Confirming cancellation for user {user_id}, Session: {session}")
                return cancel_appointment(user_id, "", user_sessions)
            if user_message.lower() in ["no", "n", "abort"]:
                user_sessions.pop(user_id, None)
                app.logger.debug(f"[chat] Cancellation aborted for user {user_id}, session cleared")
                return jsonify({"response": "Cancellation aborted. Anything else I can help with?"})
            return jsonify({"response": "Please reply 'yes' to confirm cancellation or 'no' to abort."})

    # Fallback for invalid session or flow
    app.logger.debug(f"[chat] Invalid session or flow for user {user_id}, stage: {stage}, flow: {flow}, Session: {session}")
    user_sessions.pop(user_id, None)
    return jsonify({"response": "Hi, I'm your healthbot. I can help you with the following:\n - Type 'appointment' to book a new appointment\n - Type 'reschedule' to reschedule an existing appointment\n - Type 'cancel' to cancel an appointment\n - Type 'emergency' for urgent help\n - Type 'help' to see this message again\n - Type 'restart' to start over"})

if __name__ == "__main__":
    app.run(port=8000, debug=True)