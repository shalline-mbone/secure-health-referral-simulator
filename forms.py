from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email

class AddReferralForm(FlaskForm):
    name = StringField('Patient Full Name', validators=[DataRequired()])
    email = StringField('Patient Email', validators=[DataRequired(), Email()])
    status = SelectField('Referral Status', choices=[
        ('pending', 'Pending'), 
        ('successful', 'Successful')
    ])
    month = SelectField('Referral Month', choices=[
        ('January', 'January'), ('February', 'February'), ('March', 'March'),
        ('April', 'April'), ('May', 'May'), ('June', 'June'),
        ('July', 'July'), ('August', 'August'), ('September', 'September'),
        ('October', 'October'), ('November', 'November'), ('December', 'December')
    ])
    
    # Severity Field
    severity = SelectField('Patient Severity', choices=[
        ('mild', '🟢 Mild - Stable, routine care'),
        ('moderate', '🟡 Moderate - Needs attention within 24-48 hours'),
        ('severe', '🟠 Severe - Needs attention within 6-12 hours'),
        ('critical', '🔴 Critical - Immediate attention required (bypass to national)')
    ], validators=[DataRequired()])
    
    # Condition Type Field
    condition_type = SelectField('Medical Condition', choices=[
        ('general_illness', 'General Illness - County capable'),
        ('fracture_simple', 'Simple Fracture - County capable'),
        ('fracture_complex', 'Complex Fracture - May need specialist'),
        ('maternity_routine', 'Routine Maternity - County capable'),
        ('maternity_complicated', 'Complicated Maternity - Specialist needed'),
        ('stroke', 'Acute Ischemic Stroke - Bypass often needed'),
        ('heart_attack', 'Myocardial Infarction - Bypass required'),
        ('pediatric_emergency', 'Pediatric Emergency - Bypass recommended')
    ], validators=[DataRequired()])
    
    # Clinical Notes Field - THIS WAS MISSING
    clinical_notes = TextAreaField('Clinical Notes (Symptoms, vital signs, special requirements)')
    
    # Submit Button
    submit = SubmitField('Generate Secure Referral Token')