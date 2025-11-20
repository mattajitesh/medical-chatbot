#DONOT RUN THIS FILE ONLY FOR DEVELOPERS 
from app import app, db
from sqlalchemy import text
# THIS FILE DELETE YOUR DATABASE ENTIRELY ONLY DO YOUR OWN RISK
with app.app_context():
    db.session.execute(text("DROP TABLE IF EXISTS appointment;"))
    db.session.commit()
    print("appointment table DROPPED!")