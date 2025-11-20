# models.py
from flask_sqlalchemy import SQLAlchemy
import uuid

db = SQLAlchemy()

# database model for DOCTOR table
class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    speciality = db.Column(db.String(120), nullable=False)
    consultation_fee = db.Column(db.Float, nullable=False)

# database model for APPOINTMENT table
class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    patient_name = db.Column(db.String(120), nullable=False)
    patient_email = db.Column(db.String(120), nullable=False)
    patient_mobile = db.Column(db.String(20), nullable=False)
    speciality = db.Column(db.String(200), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_time = db.Column(db.DateTime, nullable=False)
    fee = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="Scheduled")