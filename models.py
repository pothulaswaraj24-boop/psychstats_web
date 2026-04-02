from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # Device restriction
    ip_address = db.Column(db.String(100))
    user_agent = db.Column(db.String(300))
    

    full_name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True)
    
    # 🔥 NEW FIELDS
    is_admin = db.Column(db.Boolean, default=False)
    is_subscribed = db.Column(db.Boolean, default=False)
    subscription_expiry = db.Column(db.DateTime)
    is_requested = db.Column(db.Boolean, default=False)
    
    
    
class AppSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_name = db.Column(db.String(100))
    admin_email = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    upi_id = db.Column(db.String(100))