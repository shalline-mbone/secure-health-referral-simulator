from flask_login import current_user
from forms import AddReferralForm
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask.cli import FlaskGroup
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import csv, os
from functools import wraps
import json
import uuid
import datetime
from cryptography.fernet import Fernet
import base64
import hashlib

# ==================== INITIALIZE FLASK APP FIRST ====================
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# ==================== DATABASE SETUP ====================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, "instance", "referrals.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
cli = FlaskGroup(app)

# ==================== FLASK-LOGIN SETUP ====================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==================== PASSWORD HASHING ====================
bcrypt = Bcrypt(app)

# ==================== MAIL SETUP ====================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'lugusashalline1@gmail.com'
app.config['MAIL_PASSWORD'] = 'shjzspifqnjlgybc'
app.config['MAIL_DEFAULT_SENDER'] = ('Secure Referral System', 'lugusashalline1@gmail.com')
app.config['MAIL_SUPPRESS_SEND'] = False
app.config['MAIL_DEBUG'] = False

mail = Mail(app)

# ==================== TOKEN SERIALIZER ====================
s = URLSafeTimedSerializer(app.secret_key)

# ==================== TOKEN ENCRYPTION SETUP ====================
def get_encryption_key():
    key = hashlib.sha256(app.secret_key.encode()).digest()
    return base64.urlsafe_b64encode(key)

cipher = Fernet(get_encryption_key())

def encrypt_token(token):
    encrypted = cipher.encrypt(token.encode())
    return encrypted.decode()

def decrypt_token(encrypted_token):
    try:
        if not encrypted_token:
            return None
        if not encrypted_token.startswith('gAAAAA'):
            return encrypted_token
        decrypted = cipher.decrypt(encrypted_token.encode())
        return decrypted.decode()
    except Exception as e:
        print(f"Decryption error: {e}")
        return encrypted_token

# ==================== MODELS ====================

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    license_number = db.Column(db.String(50), unique=True, nullable=False)
    role = db.Column(db.String(50), nullable=False, default="user")
    hospital_name = db.Column(db.String(200), nullable=True)
    
    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

    def get_reset_token(self, expires_sec=1800):
        return s.dumps(self.username, salt='password-reset')

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        try:
            username = s.loads(token, salt='password-reset', max_age=expires_sec)
        except:
            return None
        return User.query.filter_by(username=username).first()


class Referral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    month = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    severity = db.Column(db.String(20), nullable=True)
    condition_type = db.Column(db.String(50), nullable=True)
    referral_token = db.Column(db.String(500), nullable=True, unique=True)
    recommended_hospital = db.Column(db.String(200), nullable=True)
    hospital_tier = db.Column(db.String(20), nullable=True)
    bypass_reason = db.Column(db.Text, nullable=True)
    required_capabilities = db.Column(db.String(200), nullable=True)
    token_status = db.Column(db.String(20), default='active')
    token_generated_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    clinical_notes = db.Column(db.Text, nullable=True)
    
    is_referral = db.Column(db.Boolean, default=False)
    original_referral_id = db.Column(db.Integer, nullable=True)
    re_referral_reason = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Referral {self.name} - {self.status}>'


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    referral_id = db.Column(db.Integer, db.ForeignKey('referral.id'), nullable=False)
    hospital_name = db.Column(db.String(200), nullable=False)
    token = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    referral = db.relationship('Referral', backref='notifications')
    
    def __repr__(self):
        return f'<Notification for {self.hospital_name}>'


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(150), nullable=False)
    action = db.Column(db.String(200), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(300), nullable=True)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    user = db.relationship('User', backref='audit_logs')
    
    def __repr__(self):
        return f'<AuditLog {self.username} - {self.action} - {self.timestamp}>'


# ==================== EMAIL NOTIFICATION FUNCTION ====================
def send_token_email(patient_email, patient_name, token, receiving_hospital, condition, severity):
    email_subject = "Your Secure Referral Token - IMP.SECURE Referral System"
    email_body = f"""
Dear {patient_name},

A referral has been created for you in the IMP.SECURE Referral System.

YOUR REFERRAL DETAILS:
========================================
Referral Token: {token}
Condition: {condition}
Severity: {severity.upper()}
Destination Hospital: {receiving_hospital}
========================================

IMPORTANT INSTRUCTIONS:
1. Present this token to the receiving hospital upon arrival
2. Do NOT share this token with anyone else
3. The receiving hospital will validate this token to access your medical information

Thank you,
IMP.SECURE Referral System
"""
    
    print("\n" + "="*70)
    print("📧 EMAIL SENT")
    print("="*70)
    print(f"TO: {patient_email}")
    print(f"TOKEN: {token}")
    print("="*70 + "\n")
    
    try:
        msg = Message(email_subject, recipients=[patient_email])
        msg.body = email_body
        mail.send(msg)
        print(f"✅ Email sent to {patient_email}")
        return True
    except Exception as e:
        print(f"⚠️ Email failed: {e}")
        return False


# ==================== AUDIT LOG HELPER ====================
def log_audit(user_id, username, action, details=None, request_obj=None):
    ip_address = None
    user_agent = None
    
    if request_obj:
        ip_address = request_obj.remote_addr or request_obj.headers.get('X-Forwarded-For', 'Unknown')
        user_agent = request_obj.headers.get('User-Agent', 'Unknown')[:300]
    
    log_entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.session.add(log_entry)
    db.session.commit()


# ==================== USER LOADER ====================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ==================== HOSPITAL DATA LOADER ====================
def load_hospitals():
    hospitals_path = os.path.join(os.path.dirname(__file__), 'hospitals.json')
    try:
        with open(hospitals_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "county_hospitals": [{"id": "county_default", "name": "County Referral Hospital", "capabilities": []}],
            "national_hospitals": [{"id": "national_default", "name": "National Referral Hospital", "capabilities": []}],
            "capability_mapping": {}
        }


HOSPITAL_DATA = load_hospitals()


# ==================== HELPER FUNCTIONS ====================
def generate_referral_token(condition_type, hospital_name):
    condition_map = {
        'stroke': 'STR', 'heart_attack': 'HRT', 'pediatric_emergency': 'PED',
        'maternity_routine': 'MAT', 'maternity_complicated': 'MATC',
        'fracture_simple': 'FRX', 'fracture_complex': 'FRXC',
        'general_illness': 'GEN'
    }
    
    prefix = condition_map.get(condition_type, 'REF')
    hospital_code = ''.join(word[0] for word in hospital_name.split()[:2]).upper()
    random_part = str(uuid.uuid4())[:8].upper()
    timestamp = datetime.datetime.now().strftime('%y%m%d')
    
    return f"{prefix}-{hospital_code}-{timestamp}-{random_part}"


def determine_referral_destination(severity, condition_type, referring_hospital, clinical_notes=""):
    hospitals = load_hospitals()
    
    if severity == 'critical':
        recommended = hospitals['national_hospitals'][0]
        tier = 'National Referral Hospital'
        bypass_reason = f"CRITICAL SEVERITY: Patient requires immediate specialist intervention at {recommended['name']}."
    elif any(cond in condition_type for cond in ['stroke', 'heart_attack', 'pediatric_emergency', 'maternity_complicated', 'fracture_complex']):
        recommended = hospitals['national_hospitals'][0]
        tier = 'National Referral Hospital'
        bypass_reason = f"CONDITION REQUIREMENT: {condition_type.replace('_', ' ').title()} requires specialized resources at national level."
    else:
        recommended = hospitals['county_hospitals'][0]
        tier = 'County Hospital'
        bypass_reason = f"STANDARD REFERRAL: {condition_type.replace('_', ' ').title()} can be managed at {recommended['name']}."
    
    if recommended['name'] == referring_hospital:
        if tier == 'National Referral Hospital':
            for alt in hospitals['national_hospitals']:
                if alt['name'] != referring_hospital:
                    recommended = alt
                    bypass_reason += f" (Redirected from same hospital to {recommended['name']})"
                    break
        else:
            for alt in hospitals['county_hospitals']:
                if alt['name'] != referring_hospital:
                    recommended = alt
                    bypass_reason += f" (Redirected from same hospital to {recommended['name']})"
                    break
    
    return recommended, tier, bypass_reason


# ==================== ROLE DECORATORS ====================
def role_required(role):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("You must be logged in.", "danger")
                return redirect(url_for("login"))
            if current_user.role != role:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != "admin":
            flash("Access denied: Admins only.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function


# ==================== LICENSE LOADER ====================
def load_valid_licenses():
    licenses = set()
    try:
        with open("licenses.csv", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                licenses.add(row["license_number"].strip())
    except FileNotFoundError:
        print("licenses.csv not found")
    return licenses


valid_licenses = load_valid_licenses()


# ==================== ROUTES ====================

@app.route('/')
def home():
    return render_template("base.html")


@app.route('/dashboard')
@login_required
def dashboard():
    total = Referral.query.count()
    successful = Referral.query.filter_by(status='successful').count()
    pending = Referral.query.filter_by(status='pending').count()
    re_referred = Referral.query.filter_by(status='re_referred').count()
    months = ['January','February','March','April','May','June',
              'July','August','September','October','November','December']

    successful_counts = [Referral.query.filter_by(status='successful', month=m).count() for m in months]
    pending_counts = [Referral.query.filter_by(status='pending', month=m).count() for m in months]
    monthly_counts = [Referral.query.filter_by(month=m).count() for m in months]
    
    if current_user.role == 'admin':
        referrals = Referral.query.all()
    else:
        referrals = Referral.query.filter(
            (Referral.recommended_hospital == current_user.hospital_name) |
            (Referral.user_id == current_user.id)
        ).all()
    
    for ref in referrals:
        try:
            if ref.referral_token:
                ref.decrypted_token = decrypt_token(ref.referral_token)
            else:
                ref.decrypted_token = None
        except:
            ref.decrypted_token = None
    
    incoming_referrals = []
    outgoing_referrals = []
    unread_notifications = []
    unread_count = 0
    
    if current_user.hospital_name:
        incoming_referrals = Referral.query.filter_by(
            recommended_hospital=current_user.hospital_name,
            token_status='active'
        ).all()
        
        for ref in incoming_referrals:
            try:
                if ref.referral_token:
                    ref.decrypted_token = decrypt_token(ref.referral_token)
                else:
                    ref.decrypted_token = None
            except:
                ref.decrypted_token = None
        
        outgoing_referrals = Referral.query.filter_by(
            user_id=current_user.id
        ).all()
        
        for ref in outgoing_referrals:
            try:
                if ref.referral_token:
                    ref.decrypted_token = decrypt_token(ref.referral_token)
                else:
                    ref.decrypted_token = None
            except:
                ref.decrypted_token = None
        
        unread_notifications = Notification.query.filter_by(
            hospital_name=current_user.hospital_name,
            is_read=False
        ).order_by(Notification.created_at.desc()).all()
        unread_count = len(unread_notifications)

    return render_template('dashboard.html',
                           total=total,
                           successful=successful,
                           pending=pending,
                           re_referred=re_referred,
                           months=months,
                           successful_counts=successful_counts,
                           pending_counts=pending_counts,
                           monthly_counts=monthly_counts,
                           referrals=referrals,
                           incoming_referrals=incoming_referrals,
                           outgoing_referrals=outgoing_referrals,
                           unread_notifications=unread_notifications,
                           unread_count=unread_count)


@app.route("/add_referral", methods=["GET", "POST"])
@login_required
def add_referral():
    form = AddReferralForm()
    
    if form.validate_on_submit():
        try:
            severity = form.severity.data
            condition_type = form.condition_type.data
            referring_hospital = current_user.hospital_name
            
            recommended_hospital, hospital_tier, bypass_reason = determine_referral_destination(
                severity, condition_type, referring_hospital, form.clinical_notes.data
            )
            
            if recommended_hospital['name'] == referring_hospital:
                flash('❌ Cannot refer a patient to your own hospital!', 'danger')
                return redirect(url_for('add_referral'))
            
            referral_token_plain = generate_referral_token(condition_type, recommended_hospital['name'])
            referral_token_encrypted = encrypt_token(referral_token_plain)
            
            referral = Referral(
                name=form.name.data,
                email=form.email.data,
                status=form.status.data,
                month=form.month.data,
                user_id=current_user.id,
                severity=severity,
                condition_type=condition_type,
                referral_token=referral_token_encrypted,
                recommended_hospital=recommended_hospital['name'],
                hospital_tier=hospital_tier,
                bypass_reason=bypass_reason,
                required_capabilities=', '.join(recommended_hospital.get('capabilities', ['Standard care'])[:3]),
                token_status='active',
                clinical_notes=form.clinical_notes.data
            )
            
            db.session.add(referral)
            db.session.commit()
            
            notification = Notification(
                referral_id=referral.id,
                hospital_name=recommended_hospital['name'],
                token=referral_token_encrypted,
                is_read=False
            )
            db.session.add(notification)
            db.session.commit()
            
            send_token_email(
                patient_email=form.email.data,
                patient_name=form.name.data,
                token=referral_token_plain,
                receiving_hospital=recommended_hospital['name'],
                condition=condition_type.replace('_', ' ').title(),
                severity=severity
            )
            
            log_audit(
                user_id=current_user.id,
                username=current_user.username,
                action='CREATE_REFERRAL',
                details=f'Created referral for patient {form.name.data} with token {referral_token_plain} to {recommended_hospital["name"]}',
                request_obj=request
            )
            
            flash(f'✅ Referral created! Token: {referral_token_plain}', 'success')
            return redirect(url_for('view_referral_token', referral_id=referral.id, token=referral_token_plain))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating referral: {str(e)}', 'danger')
            return redirect(url_for('add_referral'))
    
    return render_template("add_referral.html", form=form)


@app.route('/referral/token/<int:referral_id>')
@login_required
def view_referral_token(referral_id):
    referral = Referral.query.get_or_404(referral_id)
    
    if referral.user_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to view this token.', 'danger')
        return redirect(url_for('dashboard'))
    
    decrypted_token = decrypt_token(referral.referral_token)
    return render_template('referral_token.html', referral=referral, token=decrypted_token)


@app.route('/referral/validate', methods=['GET', 'POST'])
@login_required
def validate_referral_token():
    # GET request with no token - just show the form
    if request.method == 'GET' and not request.args.get('token'):
        return render_template('token_validation.html', valid=None)
    
    # GET request with token parameter (from notification link)
    if request.method == 'GET' and request.args.get('token'):
        token_input = request.args.get('token')
    else:
        # POST request (form submission)
        token_input = request.form.get('token', '').strip()
    
    if not token_input:
        flash('Please enter a token.', 'warning')
        return render_template('token_validation.html', valid=None)
    
    print(f"\n[DEBUG] Validating token: {token_input}")
    
    # Search for matching referral
    all_referrals = Referral.query.all()
    found_referral = None
    plain_token = None
    
    for referral in all_referrals:
        try:
            decrypted = decrypt_token(referral.referral_token)
            if decrypted == token_input:
                found_referral = referral
                plain_token = decrypted
                print(f"[DEBUG] Match found! ID: {referral.id}, Status: {referral.status}, Token Status: {referral.token_status}")
                break
        except Exception as e:
            print(f"[DEBUG] Error: {e}")
            continue
    
    if not found_referral:
        flash('Invalid referral token.', 'danger')
        return render_template('token_validation.html', valid=False)
    
    # Check if token is already used
    if found_referral.token_status != 'active':
        flash('This token has already been used or expired.', 'warning')
        return render_template('token_validation.html', valid=False)
    
    # Check hospital authorization
    if current_user.hospital_name != found_referral.recommended_hospital:
        log_audit(
            user_id=current_user.id,
            username=current_user.username,
            action='UNAUTHORIZED_VALIDATION_ATTEMPT',
            details=f'User from {current_user.hospital_name} attempted to validate token for {found_referral.recommended_hospital}',
            request_obj=request
        )
        flash('❌ Access Denied: This token was not issued to your hospital.', 'danger')
        return render_template('token_validation.html', valid=False, error_message='This token was not issued to your hospital.')
    
    # Log successful validation
    log_audit(
        user_id=current_user.id,
        username=current_user.username,
        action='TOKEN_VALIDATED',
        details=f'Validated token for patient {found_referral.name}',
        request_obj=request
    )
    
    return render_template('token_validation.html', valid=True, referral=found_referral, plain_token=plain_token)


@app.route('/referral/mark_used', methods=['POST'])
@login_required
def mark_token_used():
    token_input = request.form.get('token')
    
    print(f"\n[DEBUG] mark_token_used - Token: {token_input}")
    
    # Find the referral with this token
    found_referral = None
    all_referrals = Referral.query.all()
    
    for referral in all_referrals:
        try:
            # Decrypt the stored token
            decrypted = decrypt_token(referral.referral_token)
            print(f"[DEBUG] Comparing: {decrypted} with {token_input}")
            
            if decrypted == token_input:
                found_referral = referral
                break
        except Exception as e:
            print(f"[DEBUG] Error: {e}")
            continue
    
    if found_referral:
        # Update the referral
        found_referral.token_status = 'used'
        found_referral.status = 'successful'
        db.session.commit()
        
        print(f"[DEBUG] Referral {found_referral.id} updated to successful")
        
        log_audit(
            user_id=current_user.id,
            username=current_user.username,
            action='REFERRAL_CONFIRMED',
            details=f'Confirmed patient {found_referral.name} received at {found_referral.recommended_hospital}',
            request_obj=request
        )
        
        flash(f'✅ Patient {found_referral.name} confirmed received!', 'success')
    else:
        print(f"[DEBUG] No match found for token: {token_input}")
        flash('❌ Token not found.', 'danger')
    
    # Redirect to dashboard to see the updated status
    return redirect(url_for('dashboard'))


@app.route('/referral/re_refer/<int:referral_id>', methods=['POST'])
@login_required
def re_refer_patient(referral_id):
    original_referral = Referral.query.get_or_404(referral_id)
    
    re_referral_reason = request.form.get('re_referral_reason', '')
    additional_notes = request.form.get('additional_notes', '')
    
    original_referral.token_status = 'used'
    original_referral.status = 're_referred'
    original_referral.re_referral_reason = re_referral_reason
    db.session.commit()
    
    hospitals = load_hospitals()
    
    if original_referral.hospital_tier == 'National Referral Hospital':
        new_destination = None
        for alt in hospitals['national_hospitals']:
            if alt['name'] != original_referral.recommended_hospital:
                new_destination = alt
                break
        if not new_destination:
            new_destination = hospitals['national_hospitals'][0]
    else:
        if 'specialist' in re_referral_reason.lower() or 'equipment' in re_referral_reason.lower():
            new_destination = hospitals['national_hospitals'][0]
        else:
            new_destination = None
            for alt in hospitals['county_hospitals']:
                if alt['name'] != original_referral.recommended_hospital:
                    new_destination = alt
                    break
            if not new_destination:
                new_destination = hospitals['national_hospitals'][0]
    
    new_token_plain = generate_referral_token(original_referral.condition_type, new_destination['name'])
    new_token_encrypted = encrypt_token(new_token_plain)
    
    new_referral = Referral(
        name=original_referral.name,
        email=original_referral.email,
        status='pending',
        month=datetime.datetime.now().strftime('%B'),
        user_id=current_user.id,
        severity=original_referral.severity,
        condition_type=original_referral.condition_type,
        referral_token=new_token_encrypted,
        recommended_hospital=new_destination['name'],
        hospital_tier='National Referral Hospital' if new_destination in hospitals['national_hospitals'] else 'County Hospital',
        bypass_reason=f"RE-REFERRAL: {re_referral_reason}",
        required_capabilities=original_referral.required_capabilities,
        token_status='active',
        clinical_notes=f"RE-REFERRAL: {additional_notes}",
        is_referral=True,
        original_referral_id=original_referral.id,
        re_referral_reason=re_referral_reason
    )
    
    db.session.add(new_referral)
    db.session.commit()
    
    notification = Notification(
        referral_id=new_referral.id,
        hospital_name=new_destination['name'],
        token=new_token_encrypted,
        is_read=False
    )
    db.session.add(notification)
    db.session.commit()
    
    send_token_email(
        patient_email=new_referral.email,
        patient_name=new_referral.name,
        token=new_token_plain,
        receiving_hospital=new_destination['name'],
        condition=new_referral.condition_type.replace('_', ' ').title(),
        severity=new_referral.severity
    )
    
    log_audit(
        user_id=current_user.id,
        username=current_user.username,
        action='RE_REFERRAL_CREATED',
        details=f'Created re-referral for {new_referral.name} from {original_referral.recommended_hospital} to {new_destination["name"]}',
        request_obj=request
    )
    
    flash(f'✅ Patient re-referred to {new_destination["name"]}. New token: {new_token_plain}', 'success')
    return redirect(url_for('dashboard'))


@app.route('/notification/mark_read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.hospital_name == current_user.hospital_name:
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_referrals = Referral.query.count()
    successful_count = Referral.query.filter_by(status='successful').count()
    pending_count = Referral.query.filter_by(status='pending').count()
    re_referred_count = Referral.query.filter_by(status='re_referred').count()

    month_mapping = {
        'January': 'Jan', 'February': 'Feb', 'March': 'Mar', 'April': 'Apr',
        'May': 'May', 'June': 'Jun', 'July': 'Jul', 'August': 'Aug',
        'September': 'Sep', 'October': 'Oct', 'November': 'Nov', 'December': 'Dec'
    }
    
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    monthly_counts = []
    for month_full, month_short in month_mapping.items():
        count = Referral.query.filter_by(month=month_full).count()
        monthly_counts.append(count)

    admin_actions = [
        {"name": "Manage Users", "endpoint": "manage_users"},
        {"name": "View Referrals", "endpoint": "view_referrals"},
        {"name": "Audit Logs", "endpoint": "audit_logs"},
        {"name": "System Settings", "endpoint": "system_settings"}
    ]

    return render_template("admin_dashboard.html",
                           total_users=total_users,
                           total_referrals=total_referrals,
                           successful_count=successful_count,
                           pending_count=pending_count,
                           re_referred_count=re_referred_count,
                           months=months,
                           monthly_counts=monthly_counts,
                           admin_actions=admin_actions)


@app.route("/admin/audit_logs")
@admin_required
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    actions = list(set([l.action for l in AuditLog.query.all()]))
    return render_template('audit_logs.html', logs=logs, actions=actions)


@app.route("/admin/users")
@admin_required
def manage_users():
    users = User.query.all()
    return render_template("manage_users.html", users=users)


@app.route("/admin/users/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_user(id):
    user = User.query.get_or_404(id)
    if request.method == "POST":
        user.username = request.form["username"]
        user.email = request.form["email"]
        user.role = request.form["role"]
        user.hospital_name = request.form.get("hospital_name", "")
        db.session.commit()
        flash("User updated successfully!", "success")
        return redirect(url_for("manage_users"))
    return render_template("edit_user.html", user=user)


@app.route("/admin/users/delete/<int:id>", methods=["GET", "POST"])
@admin_required
def delete_user(id):
    user = User.query.get_or_404(id)
    if request.method == "POST":
        db.session.delete(user)
        db.session.commit()
        flash("User deleted successfully!", "danger")
        return redirect(url_for("manage_users"))
    return render_template("delete_user.html", user=user)


@app.route("/admin/referrals")
@admin_required
def view_referrals():
    referrals = Referral.query.all()
    for ref in referrals:
        ref.decrypted_token = decrypt_token(ref.referral_token)
    return render_template("view_referrals.html", referrals=referrals)


@app.route("/admin/settings")
@admin_required
def system_settings():
    return render_template("system_settings.html")


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required("admin")
def edit_referral(id):
    referral = Referral.query.get_or_404(id)
    if request.method == 'POST':
        referral.status = request.form['status']
        referral.month = request.form['month']
        db.session.commit()
        flash('Referral updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('edit_referral.html', referral=referral)


@app.route('/delete/<int:id>')
@login_required
@role_required("admin")
def delete_referral(id):
    referral = Referral.query.get_or_404(id)
    db.session.delete(referral)
    db.session.commit()
    flash('Referral deleted successfully!', 'danger')
    return redirect(url_for('dashboard'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        license_number = request.form['license_number']
        hospital_name = request.form.get('hospital_name', '')
        role = request.form.get('role', 'user')

        existing_user = User.query.filter(
            (User.username == username) | (User.license_number == license_number)
        ).first()
        if existing_user:
            flash('Username or license already registered.', 'danger')
            return redirect(url_for('register'))

        if license_number not in valid_licenses:
            flash('Invalid license number. Please contact admin.', 'danger')
            return redirect(url_for('register'))

        user = User(
            username=username, 
            license_number=license_number, 
            role=role,
            hospital_name=hospital_name
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        log_audit(user.id, username, 'USER_REGISTERED', f'New user registered', request)
        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            log_audit(user.id, user.username, 'LOGIN_SUCCESS', 'User logged in', request)
            flash('Login successful!', 'success')
            if user.role == "admin":
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            log_audit(0, username, 'LOGIN_FAILED', f'Failed login attempt', request)
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    log_audit(current_user.id, current_user.username, 'LOGOUT', 'User logged out', request)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/reset_request', methods=['GET', 'POST'])
def reset_request():
    return render_template('reset_request.html')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    return render_template('reset_password.html')


if __name__ == '__main__':
    app.run(debug=True)