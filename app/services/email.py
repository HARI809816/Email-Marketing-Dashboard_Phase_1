import smtplib
from email.message import EmailMessage
from app.config import SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM

async def send_otp_email(to_email: str, otp: str):
    msg = EmailMessage()
    msg.set_content(f"Your verification code for Email Dashboard is: {otp}\n\nThis code will expire in 10 minutes.")
    msg['Subject'] = 'Verification Code - Email Dashboard'
    msg['From'] = EMAIL_FROM
    msg['To'] = to_email

    try:
        # Use SMTP_SSL for port 465, or starttls for 587
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
