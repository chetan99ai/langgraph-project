import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
import os
load_dotenv()

def send_email(recepient_email, Subject, body):
    # 1. Setup email data
    SENDER_EMAIL = "chetan99ai@gmail.com"
    RECEIVER_EMAIL = recepient_email
    # Note: For Gmail/Yahoo, use an "App Password", not your normal login password.
    APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

    # 2. Construct the message using EmailMessage
    msg = EmailMessage()
    msg["Subject"] = Subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.set_content(body)

    # 3. Establish a secure connection and send
    # Example uses Gmail's SMTP server configuration
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Upgrade the connection to secure TLS encryption
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)  # Automatically handles headers and recipients
        return "Email sent successfully!"
    except Exception as e:
        return f"Failed to send email: {e}"
