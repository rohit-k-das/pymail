from mailApp import MicrosoftOutlookMail
from mailApp import Gmail
import logging
import datetime

logger = logging.getLogger(__name__)


def parser(pull_emails, move_mail_back, read_mail, sender, recipient, subject, start_date, end_date, hard_delete):
    # Generate access token to be used in the below functions of the app/script
    MicrosoftOutlookMail.oauth_access_token, MicrosoftOutlookMail.expiry_time = MicrosoftOutlookMail.generate_access_token()

    if not MicrosoftOutlookMail.oauth_access_token and MicrosoftOutlookMail.expiry_time > datetime.datetime.now():
        logger.critical('Unable to generate access token. Exiting..')
        return

    # Functions of the email script
    # Pull email
    if pull_emails:
        sender = sender.lower()
        recipient = recipient.lower()
        MicrosoftOutlookMail.email_pull(sender, recipient, subject, start_date, end_date, hard_delete)
        Gmail.remove_mails(sender, recipient, subject, start_date, end_date)
    # Revert mail
    if move_mail_back:
        MicrosoftOutlookMail.restore_mail(recipient, sender, subject, start_date, end_date)
        Gmail.recover_mails(sender, recipient, subject, start_date, end_date)

    # Read mail
    if read_mail:
        sender = sender.lower()
        recipient = recipient.lower()
        MicrosoftOutlookMail.read_emails(sender, recipient, subject, start_date, end_date)
        Gmail.read_emails(sender, recipient, subject, start_date, end_date)
