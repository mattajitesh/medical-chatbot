import re
from datetime import datetime
from flask import jsonify
from models import db, Doctor, Appointment
from appUtils import send_email, validate_name, validate_email, validate_mobile, validate_date

# basic email msg just for better experience 
email_msg='''
Please arrive 10–15 minutes early to ensure a smooth check-in process.
If you need to make any changes, you can easily reschedule or cancel your appointment by replying to this email or through our chatbot.

💚 Your health and well-being are our top priority.We look forward to assisting you and ensuring you get the best care possible.

Wishing you good health and a speedy recovery! 🌼

Warm regards,
Healthcare Assistant Team'''

def parse_slot_to_time(slot_str):
    """
    Converts strings like:
    "09:00-10:00 AM" → datetime.time(9, 0)
    "11:00-12:00 PM" → datetime.time(11, 0)
    """
    # Extract the start time part: "09:00" from "09:00-10:00 AM"
    match = re.search(r"(\d{2}:\d{2}).*?(AM|PM)", slot_str, re.IGNORECASE)
    if not match:
        raise ValueError("Invalid slot format")

    time_24 = match.group(1)   # "09:00", "11:00", etc.
    am_pm   = match.group(2).upper()

    # Convert 24-hour "HH:MM" + AM/PM → proper time
    dt = datetime.strptime(f"{time_24} {am_pm}", "%H:%M %p")
    return dt.time()

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
        session["stage"] = "speciality"
        speciality = [
            "1. General Physician",
            "2. Cardiologist",
            "3. Gastroenterologist",
            "4. Dermatologist"
        ]
        return jsonify({"response": "Please select your speciality by typing the number:\n\n" + "\n".join(speciality)})

    elif session["stage"] == "speciality":
        speciality_map = {
            "1": "General Physician",
            "2": "Cardiologist",
            "3": "Gastroenterologist",
            "4": "Dermatologist"
        }
        if user_message not in speciality_map:
            return jsonify({"response": "Invalid selection!\n\n"
                            "Please type only:\n"
                            "1 → General Physician\n"
                            "2 → Cardiologist\n"
                            "3 → Gastroenterologist\n"
                            "4 → Dermatologist"})
        session["speciality"] = speciality_map[user_message]

        if user_message in ["1"]:
            doctors = Doctor.query.filter_by(speciality="General Physician").all()
        elif user_message == "2":
            doctors = Doctor.query.filter_by(speciality="Cardiologist").all()
        elif user_message == "3":
            doctors = Doctor.query.filter_by(speciality="Gastroenterologist").all()
        elif user_message == "4":
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
            "response": f"Please choose a doctor by entering the number:\n{doctor_list}"
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

        morning_slots = ["09:00-10:00 AM", "10:00-11:00 AM", "11:00 AM-12:00 PM"]
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
                    speciality=session["speciality"],
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
                
                #Send mail feature for booking new appointment
                # email_status = "📧 A confirmation email will be sent shortly. Kindly check in spam folder too."
                # try:
                #     send_email(appointment.patient_email, "Appointment Confirmation - HealthBot", confirmation_msg + email_msg)
                # except Exception as e:
                #     print(f"❌ Email sending failed: {e}")
                #     email_status = "❌ Failed to send confirmation email. Please check your email address or contact support."
                # confirmation_msg += email_status

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
    session = user_sessions.get(user_id, {})
    stage = session.get("stage")
    print(f"[cancel_appointment] User ID: {user_id}, Stage: {stage}, Message: '{user_message}', Session: {session}")

    try:
        # First time entering cancel flow
        if not session or "flow" not in session or session.get("flow") != "cancel":
            user_sessions[user_id] = {
                "flow": "cancel",
                "stage": "choose_method"
            }
            return jsonify({
                "response": (
                    "To cancel your appointment, please choose:\n\n"
                    "1 → To Enter Mobile Number\n"
                    "2 → To Enter Serial Number\n\n"
                    "Reply with 1 or 2"
                )
            })

        # ================== STAGE: Choose Method ==================
        if stage == "choose_method":
            if user_message.strip() not in ["1", "2"]:
                return jsonify({"response": "❌ Invalid Option. Please select within 1 or 2 only."})

            if user_message == "1":
                session["stage"] = "awaiting_mobile"
                user_sessions[user_id] = session
                return jsonify({"response": "Please enter your registered mobile number (10 digits):"})

            else:  # Option 2
                session["stage"] = "awaiting_serial"
                user_sessions[user_id] = session
                return jsonify({"response": "Please enter the exact appointment serial number:"})

        # ================== STAGE: Mobile Number Input ==================
        if stage == "awaiting_mobile":
            mobile = user_message.strip()
            if not (mobile.isdigit() and len(mobile) == 10):
                return jsonify({"response": "Please enter a valid 10-digit mobile number."})

            # Find active appointments
            appointments = Appointment.query.filter(
                Appointment.patient_mobile == mobile,
                (Appointment.status.is_(None) | (Appointment.status != "Cancelled"))
            ).order_by(Appointment.appointment_time.desc()).all()

            if not appointments:
                user_sessions.pop(user_id, None)
                return jsonify({"response": "No active appointments found for this mobile number."})

            session["mobile"] = mobile
            session["appointments_list"] = [
                {
                    "id": a.id,
                    "serial": a.serial_number,
                    "name": a.patient_name,
                    "doctor_id": a.doctor_id,
                    "time": a.appointment_time.strftime("%d %b %Y %I:%M %p")
                }
                for a in appointments
            ]

            if len(appointments) == 1:
                apt = appointments[0]
                doctor = Doctor.query.get(apt.doctor_id)
                session["appointment_id"] = apt.id
                session["stage"] = "confirm_cancel"
                user_sessions[user_id] = session

                return jsonify({
                    "response": (
                        f"Found your appointment:\n\n"
                        f"Serial: {apt.serial_number}\n\n"
                        f"👤 Patient: {apt.patient_name}\n"
                        f"👨‍⚕️ Doctor: {doctor.name} ({doctor.speciality})\n"
                        f"📅 Date & Time: {apt.appointment_time.strftime('%d %b %Y %I:%M %p')}\n"
                        f"Cancel this appointment?\nReply: yes or no"
                    )
                })
            else:
                session["stage"] = "choose_appointment"
                user_sessions[user_id] = session
                resp = "Multiple active appointments found:\n\n"
                for i, apt in enumerate(session["appointments_list"], 1):
                    doc = Doctor.query.get(apt["doctor_id"])
                    resp += f"{i}. {apt['name']} → {doc.name}\n   {apt['time']}\n   Serial: {apt['serial']}\n\n"
                resp += "Reply with the number to cancel:"
                return jsonify({"response": resp})

        # ================== STAGE: Serial Number Input ==================
        if stage == "awaiting_serial":
            serial = user_message.strip()
            appointment = Appointment.query.filter_by(serial_number=serial).first()

            if not appointment:
                user_sessions.pop(user_id, None)
                return jsonify({"response": f"No appointment found with serial: {serial}"})

            if appointment.status and appointment.status.lower() == "cancelled":
                user_sessions.pop(user_id, None)
                return jsonify({"response": f"Appointment {serial} is already cancelled."})

            doctor = Doctor.query.get(appointment.doctor_id)
            session["appointment_id"] = appointment.id
            session["stage"] = "confirm_cancel"
            user_sessions[user_id] = session

            return jsonify({
                "response": (
                    f"Found appointment:\n\n"
                    f"Serial: {appointment.serial_number}\n\n"
                    f"👤Patient: {appointment.patient_name}\n"
                    f"👨‍⚕️Doctor: {doctor.name} ({doctor.speciality})\n"
                    f"📅Date & Time: {appointment.appointment_time.strftime('%d %b %Y • %I:%M %p')}\n"
                    f"Cancel this appointment?\nReply: 'yes' to confirm or 'no' to abort cancellation"
                )
            })

        # ================== STAGE: Choose from List (Mobile flow) ==================
        if stage == "choose_appointment":
            try:
                idx = int(user_message.strip()) - 1
                selected = session["appointments_list"][idx]
                session["appointment_id"] = selected["id"]
                session["stage"] = "confirm_cancel"
                user_sessions[user_id] = session

                return jsonify({
                    "response": (
                        f"You selected:\n"
                        f"Serial Number: {selected['serial']}\n👤Patient: {selected['name']}\n📅Date & Time: {selected['time']}\n\n"
                        f"Confirm cancellation?\nReply: 'yes' to confirm or 'no' to abort cancellation"
                    )
                })
            except:
                return jsonify({"response": "❌ Invalid number. Please choose from the list."})

        # ================== STAGE: Final Confirmation ==================
        if stage == "confirm_cancel":
            if user_message.lower() in ["yes", "y", "haan", "confirm"]:
                apt = Appointment.query.get(session["appointment_id"])
                if not apt:
                    user_sessions.pop(user_id, None)
                    return jsonify({"response": "Appointment no longer exists."})

                serial = apt.serial_number
                apt.status = "Cancelled"
                db.session.commit()

                try:
                    send_email(
                        to=apt.patient_email,
                        subject="Appointment Cancelled - HealthBot",
                        body=f"Dear {apt.patient_name},\n\n"
                             f"Your appointment on {apt.appointment_time.strftime('%d %b %Y at %I:%M %p')}\n"
                             f"with Dr. {Doctor.query.get(apt.doctor_id).name} has been cancelled.\n\n"
                             f"Serial: {serial}\n\nThank you."
                    )
                except Exception as e:
                    print(f"[cancel_appointment] Email failed: {e}")

                user_sessions.pop(user_id, None)
                return jsonify({
                    "response": f"Appointment {serial} has been successfully cancelled!\n\n"
                                "Need help with anything else? Write 'help' to see more options"
                })

            elif user_message.lower() in ["no", "n", "abort"]:
                user_sessions.pop(user_id, None)
                return jsonify({"response": "Cancellation cancelled. Your appointment remains active."})

            else:
                return jsonify({"response": "Please reply 'yes' to cancel or 'no' to keep it."})

    except Exception as e:
        print(f"[cancel_appointment] Unexpected error: {str(e)}")
        user_sessions.pop(user_id, None)
        return jsonify({"response": "An error occurred. Please type 'cancel' to try again."})

def reschedule_appointment(user_id, user_message, user_sessions):
    session = user_sessions.get(user_id, {})
    stage = session.get("stage")
    print(f"[reschedule_appointment] User ID: {user_id}, Stage: {stage}, Message: '{user_message}', Session: {session}")

    try:
        # First time entering reschedule flow
        if not session or "flow" not in session or session.get("flow") != "reschedule":
            user_sessions[user_id] = {
                "flow": "reschedule",
                "stage": "choose_method"
            }
            return jsonify({
                "response": (
                    "To reschedule your appointment, please choose:\n\n"
                    "1 → To Enter Mobile Number\n"
                    "2 → To Enter Serial Number\n\n"
                    "Reply with 1 or 2"
                )
            })

        if stage == "choose_method":
            if user_message.strip() not in ["1", "2"]:
                return jsonify({"response": "❌ Invalid Option. Please select within 1 or 2 only."})

            if user_message == "1":
                session["stage"] = "awaiting_mobile"
                user_sessions[user_id] = session
                return jsonify({"response": "Please enter your registered mobile number (10 digits wihtout country code):"})

            else:  # Option 2
                session["stage"] = "awaiting_serial"
                user_sessions[user_id] = session
                return jsonify({"response": "Please enter the exact appointment serial number:"})

        elif stage == "awaiting_mobile":
            mobile = re.sub(r"\D", "", user_message.strip())
            if len(mobile) < 10:
                return jsonify({"response": "Please send a valid 10-digit mobile number."})

            mobile = mobile[-10:]  # Take last 10 digits

            # Find active (non-cancelled/non-completed) appointments only
            appointments = Appointment.query.filter(
                Appointment.patient_mobile.ilike(f"%{mobile}"),
                Appointment.status.notin_(["Cancelled", "Completed"])
            ).order_by(Appointment.appointment_time.desc()).limit(10).all()

            if not appointments:
                user_sessions.pop(user_id, None)
                return jsonify({"response": "No active appointments found for this mobile number."})

            # Enrich appointment data with formatted date/time and doctor name
            appointment_list = []
            for apt in appointments:
                doctor = Doctor.query.get(apt.doctor_id)
                appointment_list.append({
                    "id": apt.id,
                    "serial": apt.serial_number,
                    "name": apt.patient_name,
                    "doctor_name": doctor.name if doctor else "Unknown Doctor",
                    "date": apt.appointment_time.strftime("%d %b %Y"),
                    "time": apt.appointment_time.strftime("%I:%M %p"),
                    "datetime": apt.appointment_time.strftime("%d %b %Y %I:%M %p"),
                    "apt_object": apt
                })

            session["found_appointments"] = appointment_list

            if len(appointments) == 1:
                apt = appointments[0]
                doctor = Doctor.query.get(apt.doctor_id)
                doctor_name = doctor.name if doctor else "Unknown Doctor"

                session["serial_number"] = apt.serial_number
                session["stage"] = "confirm_reschedule"

                msg = (
                    f"Found your appointment:\n\n"
                    f"Serial Number: {apt.serial_number}\n"
                    f"👤 Patient: {apt.patient_name}\n"
                    f"👨‍⚕️ Doctor: {doctor_name}\n"
                    f"📅 Date: {apt.appointment_time.strftime('%d %b %Y')}\n"
                    f"⏰ Time: {apt.appointment_time.strftime('%I:%M %p')}\n\n"
                    f"Reply *yes* to reschedule or *no* to cancel this appointment."
                )
            else:
                session["stage"] = "choose_appointment"
                options = "\n\n".join(
                    f"{i+1}. Serial: *{apt['serial']}*\n"
                    f"   👤 {apt['name']}\n"
                    f"   👨‍⚕️ {apt['doctor_name']}\n"
                    f"   📅 {apt['date']} at {apt['time']}"
                    for i, apt in enumerate(appointment_list)
                )
                msg = (
                    f"Found {len(appointments)} active appointment(s):\n\n"
                    f"{options}\n\n"
                    f"Please reply with the number (1-{len(appointments)}) to select the appointment you want to reschedule/cancel."
                )
            user_sessions[user_id] = session
            return jsonify({"response": msg})

        elif stage == "choose_appointment":
            try:
                idx = int(user_message.strip()) - 1
                apts = session.get("found_appointments", [])
                if 0 <= idx < len(apts):
                    selected = apts[idx]
                    appointment = Appointment.query.filter_by(serial_number=selected["serial"]).first()
                    if not appointment:
                        return jsonify({"response": "Appointment no longer exists."})

                    session["serial_number"] = selected["serial"]
                    session["stage"] = "confirm_reschedule"
                    user_sessions[user_id] = session

                    doctor = Doctor.query.get(appointment.doctor_id)
                    msg = (
                        f"Selected:\n\n"
                        f"Serial Number: {appointment.serial_number}\n"
                        f"👤 Patient: {appointment.patient_name}\n"
                        f"👨‍⚕️ Doctor: {doctor.name}\n"
                        f"📅 Date: {appointment.appointment_time.date()}\n"
                        f"⏰ Time: {appointment.appointment_time.strftime('%I:%M %p')}\n\n"
                        "Reply 'yes' to reschedule or 'no' to abort."
                    )
                    return jsonify({"response": msg})
                else:
                    return jsonify({"response": f"Please choose a number from 1 to {len(apts)}."})
            except:
                return jsonify({"response": "Invalid input. Please reply with a number."})

        elif stage == "awaiting_serial":
            serial = user_message.strip()
            if not serial:
                return jsonify({"response": "Please send a valid serial number."})

            appointment = Appointment.query.filter_by(serial_number=serial).first()
            if not appointment:
                user_sessions.pop(user_id, None)
                return jsonify({"response": f"No appointment found with serial '{serial}'."})

            if appointment.status and appointment.status.lower() in ["cancelled", "completed"]:
                user_sessions.pop(user_id, None)
                return jsonify({"response": f"This appointment is already {appointment.status}."})

            doctor = Doctor.query.get(appointment.doctor_id)
            if not doctor:
                user_sessions.pop(user_id, None)
                return jsonify({"response": "Doctor not found. Please try again."})

            session["serial_number"] = serial
            session["stage"] = "confirm_reschedule"
            user_sessions[user_id] = session

            details_msg = (
                f"Found appointment:\n\n"
                f"Serial Number: {appointment.serial_number}\n"
                f"👤 Patient: {appointment.patient_name}\n"
                f"👨‍⚕️ Doctor: {doctor.name}\n"
                f"Speciality: {doctor.speciality}\n"
                f"📅 Date: {appointment.appointment_time.date()}\n"
                f"⏰Time: {appointment.appointment_time.strftime('%I:%M %p')}\n\n"
                "Reply 'yes' to reschedule or 'no' to abort."
            )
            return jsonify({"response": details_msg})
 
        elif stage == "confirm_reschedule":
            if user_message.lower() in ["yes", "y", "confirm"]:
                session["stage"] = "date"
                user_sessions[user_id] = session
                return jsonify({"response": "Please provide the new date (YYYY-MM-DD format)"})

            elif user_message.lower() in ["no", "n", "abort", "cancel"]:
                user_sessions.pop(user_id, None)
                return jsonify({"response": "Rescheduling cancelled. Your original appointment remains unchanged."})

            return jsonify({"response": "Please reply 'yes' to confirm or 'no' to abort."})

        elif stage == "date":
            date_obj = validate_date(user_message)
            if not date_obj:
                return jsonify({"response": "Invalid date format. Use YYYY-MM-DD."})
            if date_obj < datetime.now().date():
                return jsonify({"response": "Cannot select past date."})
            session["date"] = date_obj
            session["stage"] = "time"
            user_sessions[user_id] = session
            return jsonify({"response": "Please choose preferred slot:\n\n1. Morning (09:00 – 12:00)\n2. Evening (16:00 – 19:00)\n\nType 1 or 2"})

        elif stage == "time":
            if user_message not in ["1", "2"]:
                return jsonify({"response": "Please type 1 for Morning or 2 for Evening."})
            slots = ["09:00-10:00 AM", "10:00-11:00 AM", "11:00 AM-12:00 PM"] if user_message == "1" else ["04:00-05:00 PM", "05:00-06:00 PM", "06:00-07:00 PM"]
            session["shift"] = "Morning" if user_message == "1" else "Evening"
            session["available_slots"] = slots
            session["stage"] = "slot_choice"
            user_sessions[user_id] = session
            slot_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(slots))
            return jsonify({"response": f"{session['shift']} slots:\n\n{slot_text}\n\nReply with the number."})

        elif stage == "slot_choice":
            serial_number = session.get("serial_number")
            if not serial_number:
                user_sessions.pop(user_id, None)
                return jsonify({"response": "Session error. Type 'restart'."})

            slots = session.get("available_slots", [])
            try:
                choice = int(user_message.strip())
                if not (1 <= choice <= len(slots)):
                    raise ValueError()

                chosen_slot = slots[choice - 1]
                session["time"] = chosen_slot

                start_time = parse_slot_to_time(chosen_slot)
                appointment = Appointment.query.filter_by(serial_number=serial_number).first()
                if not appointment:
                    user_sessions.pop(user_id, None)
                    return jsonify({"response": "Appointment not found."})

                doctor = Doctor.query.get(appointment.doctor_id)
                if not doctor:
                    user_sessions.pop(user_id, None)
                    return jsonify({"response": "Doctor not found."})
                appointment_datetime = datetime.combine(session["date"], start_time)
                appointment.appointment_time = appointment_datetime
                appointment.status = "Pending"
                db.session.commit()

                session["appointment_id"] = appointment.id
                session["stage"] = "confirmation"
                user_sessions[user_id] = session

                details_msg = (
                    f"Appointment tentatively rescheduled:\n\n"
                    f"👨‍⚕️ Doctor: {doctor.name}\n"
                    f"📅 Date: {appointment.appointment_time.date()}\n"
                    f"⏰ Time: {session['time']}\n\n\n"
                    "Reply 'confirm' to finalize or 'no' to abort."
                )
                return jsonify({"response": details_msg})
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

                # mail sending for rescheduling appointment
                # email_status = "📧 A confirmation email will be sent shortly. Kindly check in spam folder too."
                # try:
                #     send_email(appointment.patient_email, "Appointment Reschedule Confirmation - HealthBot", confirmation_msg + email_msg)
                #     print(f"[reschedule_appointment] Email sent to {appointment.patient_email}")
                # except Exception as e:
                #     print(f"[reschedule_appointment] Email sending failed: {e}")
                #     email_status = "❌ Failed to send confirmation email. Please check your email address or contact support."

                # confirmation_msg += email_status

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
        
        else:
            user_sessions.pop(user_id, None)
            return jsonify({"response": "Session expired or invalid state. Type 'reschedule' to start again."})

    except Exception as e:
        print(f"[reschedule_appointment] ERROR: {str(e)}")
        user_sessions.pop(user_id, None)
        return jsonify({"response": "Sorry, something went wrong. Type 'reschedule' to try again."})