import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import markdown
from backend.app.logger import get_logger

logger = get_logger(__name__)

async def send_sunday_report(report_markdown: str, subject: str = "Kafin — Wöchentlicher Report") -> bool:
    """
    Sendet den generierten Report als formatierte HTML-Email.
    """
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)
    smtp_to = os.getenv("SMTP_TO")

    if not all([smtp_server, smtp_port, smtp_user, smtp_pass, smtp_to]):
        logger.warning("SMTP credentials incomplete in .env. Skipping email report.")
        return False

    try:
        # Konvertiere Markdown zu HTML
        html_content = markdown.markdown(report_markdown)
        
        # HTML mit etwas Styling umhüllen
        html_body = f"""
        <html>
          <head>
            <style>
              body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
              h1, h2, h3 {{ color: #111827; }}
              hr {{ border: 0; border-top: 1px solid #e5e7eb; margin: 20px 0; }}
              pre {{ background: #f3f4f6; padding: 10px; border-radius: 5px; overflow-x: auto; }}
              code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
            </style>
          </head>
          <body>
            {html_content}
          </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_from
        msg["To"] = smtp_to

        # Attach text and HTML versions
        part1 = MIMEText(report_markdown, "plain")
        part2 = MIMEText(html_body, "html")
        msg.attach(part1)
        msg.attach(part2)

        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_from, smtp_to, msg.as_string())
        server.quit()
        
        logger.info(f"Sunday Report email sent successfully to {smtp_to}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send Sunday Report email: {str(e)}")
        return False
