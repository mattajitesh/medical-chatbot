import re
from datetime import datetime
from flask import jsonify
from models import db, Doctor, Appointment
from appUtils import send_email, validate_name, validate_email, validate_mobile, validate_date

email_msg='''
Please arrive 10–15 minutes early to ensure a smooth check-in process.
If you need to make any changes, you can easily reschedule or cancel your appointment by replying to this email or through our chatbot.

💚 Your health and well-being are our top priority.We look forward to assisting you and ensuring you get the best care possible.

Wishing you good health and a speedy recovery! 🌼

Warm regards,
Healthcare Assistant Team'''

def book_appointment(user_id, user_message, user_sessions):
    if user_id not in user_sessions:
        user_sessions[user_id] = {"stage": "name"}
        return jsonify({"response": "What is your name?"})

    session = user_sessions[user_id]

    if session["stage"] == "name":
        if not validate_name(user_message):
            return jsonify({"response": "❌ Invalid name. Use only letters & spaces (min 2 chars)."})
        session["name"] = user_message.strip()
        session["stage"] = "email"
        return jsonify({"response": f"Thanks {session['name']}! Please provide your email ID."})

    elif session["stage"] == "email":
        if not validate_email(user_message):
            return jsonify({"response": "❌ Invalid email. Please provide a correct format (example@domain.com)."})
        session["email"] = user_message.strip()
        session["stage"] = "mobile"
        return jsonify({"response": "Please enter your mobile number."})

    elif session["stage"] == "mobile":
        if not validate_mobile(user_message):
            return jsonify({"response": "❌ Invalid mobile. Enter a 10-digit number starting with 6,7,8,9."})
        session["mobile"] = user_message.strip()
        session["stage"] = "symptoms"
        symptoms = [
            "1. Fever",
            "2. Cold",
            "3. Cough",
            "4. Headache",
            "5. Heart",
            "6. Stomach Pain",
            "7. Skin Problem"
        ]
        return jsonify({"response": "Please select your symptom by typing the number:\n\n" + "\n".join(symptoms)})

    elif session["stage"] == "symptoms":
        symptoms_map = {
            "1": "Fever",
            "2": "Cold",
            "3": "Cough",
            "4": "Headache",
            "5": "Heart",
            "6": "Stomach Pain",
            "7": "Skin Problem"
        }
        if user_message not in symptoms_map:
            return jsonify({"response": "❌ Invalid option. Choose 1-7."})
        session["symptoms"] = symptoms_map[user_message]

        if user_message in ["1", "2", "3", "4"]:
            doctors = Doctor.query.filter_by(speciality="General Physician").all()
        elif user_message == "5":
            doctors = Doctor.query.filter_by(speciality="Cardiologist").all()
        elif user_message == "6":
            doctors = Doctor.query.filter_by(speciality="Gastroenterologist").all()
        elif user_message == "7":
            doctors = Doctor.query.filter_by(speciality="Dermatologist").all()
        else:
            doctors = Doctor.query.all()

        if not doctors:
            return jsonify({"response": "❌ No doctors available for this symptom at the moment."})

        session["available_doctors"] = [
            {"id": d.id, "name": d.name, "speciality": d.speciality} for d in doctors
        ]
        session["stage"] = "choose_doctor"

        doctor_list = "\n".join([f"{i+1}. {d.name} ({d.speciality})" for i, d in enumerate(doctors)])
        return jsonify({
            "response": f"Please choose a doctor by entering the number:\n{doctor_list}",
            "doctors": [{"number": i+1, "name": d.name, "speciality": d.speciality} for i, d in enumerate(doctors)]
        })

    elif session["stage"] == "choose_doctor":
        available_doctors = session.get("available_doctors", [])
        if not available_doctors:
            return jsonify({"response": "❌ No doctors available. Please restart."})

        if not user_message.isdigit():
            return jsonify({"response": "❌ Please enter a valid number from the list."})

        choice = int(user_message) - 1
        if choice < 0 or choice >= len(available_doctors):
            return jsonify({"response": "❌ Invalid number. Please choose a number from the list."})

        selected_doctor = available_doctors[choice]
        session["doctor_id"] = selected_doctor["id"]
        session["stage"] = "date"
        return jsonify({"response": f"Great choice 👍 {selected_doctor['name']}.\nPlease provide appointment date (YYYY-MM-DD)."})

    elif session["stage"] == "date":
        date_obj = validate_date(user_message)
        if not date_obj:
            return jsonify({"response": "❌ Invalid date format. Use YYYY-MM-DD."})
        today = datetime.now().date()
        if date_obj < today:
            return jsonify({"response": "❌ Invalid date. Please enter a valid date in (YYYY-MM-DD) format."})
        session["date"] = date_obj
        session["stage"] = "time"
        return jsonify({"response": "Thanks. Please choose your preferred slot:\n\n"
                                "1. Morning (09:00 – 12:00)\n"
                                "2. Evening (16:00 – 19:00)\n\n"
                                "Type 1 for Morning or 2 for Evening."})

    elif session["stage"] == "time":
        if user_message not in ["1", "2"]:
            return jsonify({
                "response": "❌ Invalid option. Please type:\n"
                            "1️⃣ for Morning (09:00 – 12:00)\n"
                            "2️⃣ for Evening (16:00 – 19:00)"
            })

        morning_slots = ["09:00-10:00 AM", "10:00-11:00 AM", "11:00-12:00 PM"]
        evening_slots = ["04:00-05:00 PM", "05:00-06:00 PM", "06:00-07:00 PM"]

        if user_message == "1":
            session["shift"] = "Morning"
            slots = morning_slots
        else:
            session["shift"] = "Evening"
            slots = evening_slots

        session["available_slots"] = slots
        session["stage"] = "slot_choice"

        slot_text = "\n".join([f"{i+1}. {slot}" for i, slot in enumerate(slots)])
        return jsonify({
            "response": f"✅ You selected {session['shift']} shift.\n\n"
                        f"Please choose a time slot:\n{slot_text}\n\n"
                        "Reply with the slot number."
        })

    elif session["stage"] == "slot_choice":
        try:
            choice = int(user_message.strip())
            slots = session.get("available_slots", [])
            if 1 <= choice <= len(slots):
                chosen_slot = slots[choice - 1]
                session["time"] = chosen_slot

                time_match = re.match(r"(\d{2}:\d{2})-.* (AM|PM)", chosen_slot)
                if time_match:
                    time_str = time_match.group(1)
                    ampm = time_match.group(2)
                    dt = datetime.strptime(f"{time_str} {ampm}", "%I:%M %p")
                    start_time = dt.time()
                else:
                    start_time = datetime.strptime("09:00", "%H:%M").time()

                doctor = Doctor.query.get(session["doctor_id"])
                appointment_datetime = datetime.combine(session["date"], start_time)

                new_appointment = Appointment(
                    patient_name=session["name"],
                    patient_email=session["email"],
                    patient_mobile=session["mobile"],
                    symptoms=session["symptoms"],
                    doctor_id=doctor.id,
                    appointment_time=appointment_datetime,
                    fee=doctor.consultation_fee,
                    status="Pending"
                )
                db.session.add(new_appointment)
                db.session.commit()

                session["appointment_id"] = new_appointment.id
                session["stage"] = "confirmation"

                details_msg = (
                    f"⏰ Your appointment is tentatively booked for {session['date']} at {chosen_slot}.\n\n"
                    f"👤 Patient: {session['name']}\n"
                    f"👨‍⚕️ Doctor: {doctor.name}\n"
                    f"💰 Fee: ₹{doctor.consultation_fee}\n\n"
                    "Reply 'confirm' to finalize or 'no' to cancel."
                )
                return jsonify({"response": details_msg})
            else:
                return jsonify({"response": f"❌ Invalid slot number. Please choose 1–{len(slots)}."})
        except ValueError:
            return jsonify({"response": "❌ Please enter a valid number for the slot."})

    elif session["stage"] == "confirmation":
        if user_message.lower() in ["confirm", "yes", "y"]:
            appointment = Appointment.query.get(session["appointment_id"])
            if appointment:
                appointment.status = "Confirmed"
                db.session.commit()

                doctor = Doctor.query.get(appointment.doctor_id)
                confirmation_msg = (
                    f"✅ Appointment Confirmed!\n\n"
                    f" Serial Number: {appointment.serial_number}\n"
                    f"👤 Patient: {appointment.patient_name}\n"
                    f"👨‍⚕️ Doctor: {doctor.name}\n"
                    f"📅 Date: {appointment.appointment_time.date()}\n"
                    f"⏰ Time: {session['time']}\n"
                    f"💰 Fee: ₹{appointment.fee}\n\n"
                )

                email_status = "📧 A confirmation email will be sent shortly. Kindly check in spam folder too."
                
                try:
                    send_email(appointment.patient_email, "Appointment Confirmation - HealthBot", confirmation_msg + email_msg)
                except Exception as e:
                    print(f"❌ Email sending failed: {e}")
                    email_status = "❌ Failed to send confirmation email. Please check your email address or contact support."

                confirmation_msg += email_status

                if "appointment_id" in session:
                    del session["appointment_id"]
                session["stage"] = "done"
                return jsonify({"response": confirmation_msg})
            else:
                return jsonify({"response": "Error retrieving appointment. Please type 'restart'."})

        elif user_message.lower() in ["no", "n"]:
            if "appointment_id" in session:
                appointment = Appointment.query.get(session["appointment_id"])
                if appointment:
                    db.session.delete(appointment)
                    db.session.commit()
                del session["appointment_id"]
            session["stage"] = "greeting"
            return jsonify({"response": "❌ Appointment cancelled. You can type 'restart' to book again."})
        else:
            return jsonify({"response": "❌ Please reply with 'confirm' or 'no'. Type 'restart' if needed."})

    return jsonify({"response": "⚠️ Something went wrong. Please type 'restart' to start booking again."})

def cancel_appointment(user_id, user_message, user_sessions):
    serial_number = user_message.strip() or user_sessions.get(user_id, {}).get("serial_number")

    if not serial_number:
        user_sessions.pop(user_id, None)
        return jsonify({"response": "No serial number provided. Start again with 'cancel'."})

    appointment = Appointment.query.filter_by(serial_number=serial_number).first()

    if not appointment:
        user_sessions.pop(user_id, None)
        return jsonify({"response": f"No appointment found with serial number '{serial_number}'."})

    if appointment.status.lower() == "cancelled":
        user_sessions.pop(user_id, None)
        return jsonify({"response": f"Appointment {serial_number} is already cancelled."})

    appointment.status = "Cancelled"
    db.session.commit()

    user_sessions.pop(user_id, None)

    return jsonify({"response": f"Appointment {serial_number} has been successfully cancelled."})

def reschedule_appointment(user_id, user_message, user_sessions):
    session = user_sessions.get(user_id, {})
    stage = session.get("stage")
    print(f"[reschedule_appointment] User ID: {user_id}, Stage: {stage}, Message: {user_message}, Session: {session}")

    try:
        # Handle unexpected stages gracefully
        if not session or stage not in ["awaiting_serial", "confirm_reschedule", "date", "time", "slot_choice", "confirmation"]:
            print(f"[reschedule_appointment] Invalid or missing session/stage: {stage}, Session: {session}")
            user_sessions.pop(user_id, None)
            return jsonify({"response": "❌ Invalid session state. Please type 'restart' to start rescheduling again."})

        if stage == "awaiting_serial":
            serial = user_message.strip().lower()
            if not serial:
                return jsonify({"response": "Please send the serial number (e.g., a UUID like 123e4567-e89b-12d3-a456-426614174000)."})
            appointment = Appointment.query.filter_by(serial_number=serial).first()
            if not appointment:
                user_sessions.pop(user_id, None)
                print(f"[reschedule_appointment] No appointment found for serial {serial}, session cleared")
                return jsonify({"response": f"No appointment found with serial number '{serial}'. Start again with 'cancel' or 'reschedule'."})
            if appointment.status and appointment.status.lower() == "cancelled":
                user_sessions.pop(user_id, None)
                print(f"[reschedule_appointment] Appointment {serial} already cancelled, session cleared")
                return jsonify({"response": f"Appointment {serial} is already cancelled."})

            doctor = Doctor.query.get(appointment.doctor_id)
            if not doctor:
                user_sessions.pop(user_id, None)
                print(f"[reschedule_appointment] Doctor not found for ID {appointment.doctor_id}, session cleared")
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
                "Reply 'yes' to confirm rescheduling or 'no' to abort."
            )
            session["stage"] = "confirm_reschedule"
            session["serial_number"] = serial
            session["flow"] = "reschedule"
            print(f"[reschedule_appointment] Moving to confirm_reschedule stage for user {user_id}, serial: {serial}, Session: {session}")
            return jsonify({"response": details_msg})

        if stage == "confirm_reschedule":
            if user_message.lower() in ["yes", "y"]:
                session["stage"] = "date"
                session["flow"] = "reschedule"
                print(f"[reschedule_appointment] Moving to date stage for user {user_id}, Session: {session}")
                return jsonify({"response": "Please provide the new appointment date (YYYY-MM-DD)."})
            if user_message.lower() in ["no", "n", "abort"]:
                user_sessions.pop(user_id, None)
                print(f"[reschedule_appointment] Rescheduling aborted for user {user_id}, session cleared")
                return jsonify({"response": "Rescheduling aborted. Anything else I can help with?"})
            print(f"[reschedule_appointment] Invalid input for confirm_reschedule: {user_message}")
            return jsonify({"response": "Please reply 'yes' to confirm rescheduling or 'no' to abort."})

        elif stage == "date":
            date_obj = validate_date(user_message)
            if not date_obj:
                print(f"[reschedule_appointment] Invalid date format: {user_message}")
                return jsonify({"response": "❌ Invalid date format. Use YYYY-MM-DD."})
            today = datetime.now().date()
            if date_obj < today:
                print(f"[reschedule_appointment] Date in past: {user_message}")
                return jsonify({"response": "❌ Invalid date. Please enter a valid date in (YYYY-MM-DD) format."})
            session["date"] = date_obj
            session["stage"] = "time"
            print(f"[reschedule_appointment] Date accepted: {date_obj}, moving to time stage, Session: {session}")
            return jsonify({"response": "Thanks. Please choose your preferred slot:\n\n"
                                    "1. Morning (09:00 – 12:00)\n"
                                    "2. Evening (16:00 – 19:00)\n\n"
                                    "Type 1 for Morning or 2 for Evening."})

        elif stage == "time":
            if user_message not in ["1", "2"]:
                print(f"[reschedule_appointment] Invalid shift selection: {user_message}")
                return jsonify({
                    "response": "❌ Invalid option. Please type:\n"
                                "1️⃣ for Morning (09:00 – 12:00)\n"
                                "2️⃣ for Evening (16:00 – 19:00)"
                })

            morning_slots = ["09:00-10:00 AM", "10:00-11:00 AM", "11:00-12:00 PM"]
            evening_slots = ["04:00-05:00 PM", "05:00-06:00 PM", "06:00-07:00 PM"]

            if user_message == "1":
                session["shift"] = "Morning"
                slots = morning_slots
            else:
                session["shift"] = "Evening"
                slots = evening_slots

            session["available_slots"] = slots
            session["stage"] = "slot_choice"
            print(f"[reschedule_appointment] Shift selected: {session['shift']}, moving to slot_choice stage, Session: {session}")
            slot_text = "\n".join([f"{i+1}. {slot}" for i, slot in enumerate(slots)])
            return jsonify({
                "response": f"✅ You selected {session['shift']} shift.\n\n"
                            f"Please choose a time slot:\n{slot_text}\n\n"
                            "Reply with the slot number."
            })

        elif stage == "slot_choice":
            serial_number = session.get("serial_number")
            if not serial_number:
                print(f"[reschedule_appointment] Missing serial_number in session for user {user_id}, Session: {session}")
                user_sessions.pop(user_id, None)
                return jsonify({"response": "❌ Session error: Missing appointment details. Please type 'restart'."})

            slots = session.get("available_slots", [])
            if not slots:
                print(f"[reschedule_appointment] No available slots in session for user {user_id}, Session: {session}")
                user_sessions.pop(user_id, None)
                return jsonify({"response": "❌ No available slots. Please type 'restart' to start again."})

            try:
                choice = int(user_message.strip())
                if 1 <= choice <= len(slots):
                    chosen_slot = slots[choice - 1]
                    session["time"] = chosen_slot
                    print(f"[reschedule_appointment] Slot selected: {chosen_slot}, Session: {session}")

                    time_match = re.match(r"(\d{2}:\d{2})-.* (AM|PM)", chosen_slot)
                    if time_match:
                        time_str = time_match.group(1)
                        ampm = time_match.group(2)
                        dt = datetime.strptime(f"{time_str} {ampm}", "%I:%M %p")
                        start_time = dt.time()
                    else:
                        print(f"[reschedule_appointment] Invalid time format in slot: {chosen_slot}")
                        start_time = datetime.strptime("09:00", "%H:%M").time()

                    appointment = Appointment.query.filter_by(serial_number=serial_number).first()
                    if not appointment:
                        print(f"[reschedule_appointment] Appointment not found for serial: {serial_number}")
                        user_sessions.pop(user_id, None)
                        return jsonify({"response": f"Appointment {serial_number} not found."})

                    doctor = Doctor.query.get(appointment.doctor_id)
                    if not doctor:
                        print(f"[reschedule_appointment] Doctor not found for ID: {appointment.doctor_id}")
                        user_sessions.pop(user_id, None)
                        return jsonify({"response": "❌ Doctor not found. Please type 'restart'."})

                    appointment_datetime = datetime.combine(session["date"], start_time)

                    # Update existing appointment
                    appointment.appointment_time = appointment_datetime
                    appointment.status = "Pending"
                    try:
                        db.session.commit()
                        print(f"[reschedule_appointment] Appointment updated: {appointment.serial_number}, New time: {appointment_datetime}")
                    except Exception as e:
                        print(f"[reschedule_appointment] Database commit failed: {str(e)}")
                        db.session.rollback()
                        user_sessions.pop(user_id, None)
                        return jsonify({"response": f"❌ Database error: {str(e)}. Please type 'restart'."})

                    session["appointment_id"] = appointment.id
                    session["stage"] = "confirmation"
                    print(f"[reschedule_appointment] Moving to confirmation stage for user {user_id}, Session: {session}")

                    details_msg = (
                        f"⏰ Your appointment has been tentatively rescheduled for {session['date']} at {chosen_slot}.\n\n"
                        f"👤 Patient: {appointment.patient_name}\n"
                        f"👨‍⚕️ Doctor: {doctor.name}\n"
                        f"💰 Fee: ₹{doctor.consultation_fee}\n\n"
                        "Reply 'confirm' to finalize or 'no' to cancel."
                    )
                    return jsonify({"response": details_msg})
                else:
                    print(f"[reschedule_appointment] Invalid slot number: {user_message}")
                    return jsonify({"response": f"❌ Invalid slot number. Please choose 1–{len(slots)}."})
            except ValueError:
                print(f"[reschedule_appointment] Invalid slot input: {user_message}")
                return jsonify({"response": "❌ Please enter a valid number for the slot."})

        elif stage == "confirmation":
            appointment_id = session.get("appointment_id")
            serial_number = session.get("serial_number")
            if not appointment_id or not serial_number:
                print(f"[reschedule_appointment] Missing appointment_id or serial_number in session for user {user_id}, Session: {session}")
                user_sessions.pop(user_id, None)
                return jsonify({"response": "❌ Session error: Missing appointment details. Please type 'restart'."})

            appointment = Appointment.query.get(appointment_id)
            if not appointment:
                print(f"[reschedule_appointment] Appointment not found for ID: {appointment_id}, Serial: {serial_number}")
                user_sessions.pop(user_id, None)
                return jsonify({"response": "Error retrieving appointment. Please type 'restart'."})

            if user_message.lower() in ["confirm", "yes", "y"]:
                appointment.status = "Confirmed"
                try:
                    db.session.commit()
                    print(f"[reschedule_appointment] Appointment confirmed: {appointment.serial_number}")
                except Exception as e:
                    print(f"[reschedule_appointment] Database commit failed in confirmation: {str(e)}")
                    db.session.rollback()
                    user_sessions.pop(user_id, None)
                    return jsonify({"response": f"❌ Database error: {str(e)}. Please type 'restart'."})

                doctor = Doctor.query.get(appointment.doctor_id)
                if not doctor:
                    print(f"[reschedule_appointment] Doctor not found for ID: {appointment.doctor_id}")
                    user_sessions.pop(user_id, None)
                    return jsonify({"response": "❌ Doctor not found. Please type 'restart'."})

                confirmation_msg = (
                    f"✅ Appointment Rescheduled!\n\n"
                    f" Serial Number: {appointment.serial_number}\n"
                    f"👤 Patient: {appointment.patient_name}\n"
                    f"👨‍⚕️ Doctor: {doctor.name}\n"
                    f"📅 Date: {appointment.appointment_time.date()}\n"
                    f"⏰ Time: {session['time']}\n"
                    f"💰 Fee: ₹{appointment.fee}\n\n"
                )

                email_status = "📧 A confirmation email will be sent shortly. Kindly check in spam folder too."
                try:
                    send_email(appointment.patient_email, "Appointment Reschedule Confirmation - HealthBot", confirmation_msg + email_msg)
                    print(f"[reschedule_appointment] Email sent to {appointment.patient_email}")
                except Exception as e:
                    print(f"[reschedule_appointment] Email sending failed: {e}")
                    email_status = "❌ Failed to send confirmation email. Please check your email address or contact support."

                confirmation_msg += email_status

                user_sessions.pop(user_id, None)
                print(f"[reschedule_appointment] Session cleared for user {user_id}")
                return jsonify({"response": confirmation_msg})

            elif user_message.lower() in ["no", "n"]:
                appointment.status = "Confirmed"  # Revert to original status
                try:
                    db.session.commit()
                    print(f"[reschedule_appointment] Reverted appointment status to Confirmed: {appointment.serial_number}")
                except Exception as e:
                    print(f"[reschedule_appointment] Database commit failed in revert: {str(e)}")
                    db.session.rollback()
                    user_sessions.pop(user_id, None)
                    return jsonify({"response": f"❌ Database error: {str(e)}. Please type 'restart'."})

                user_sessions.pop(user_id, None)
                print(f"[reschedule_appointment] Rescheduling cancelled, session cleared for user {user_id}")
                return jsonify({"response": "Rescheduling cancelled. The original appointment remains unchanged."})
            else:
                print(f"[reschedule_appointment] Invalid confirmation input: {user_message}")
                return jsonify({"response": "❌ Please reply with 'confirm' or 'no'. Type 'restart' if needed."})

    except Exception as e:
        print(f"[reschedule_appointment] Unexpected error in reschedule_appointment: {str(e)}, Session: {session}")
        user_sessions.pop(user_id, None)
        return jsonify({"response": f"❌ An unexpected error occurred: {str(e)}. Please type 'restart' to try again."})