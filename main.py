import click
import logging
import mailApp


@click.command()
@click.option("--pull-emails", is_flag=True, help="Pull all emails that match the search criteria into user's Trash")
@click.option("--hard-delete", is_flag=True, help="Permanently delete the email from user mailbox. Email will not be recoverable")
@click.option("--restore-emails", is_flag=True, help="Move mails from Trash to Inbox of original recipient")
@click.option("--read-emails", is_flag=True, help="Read  email")
@click.option('--sender', default='', help='Sender of the mail (Leave blank if not known)')
@click.option('--recipient', default='', help='Recipient of the mail (Leave blank if not known)')
@click.option('--start-date', default='', help='Start Date YYYY-MM-DD (Leave blank if not known)')
@click.option('--end-date', default='', help='End Date YYYY-MM-DD (Leave blank if not known)')
@click.option('--subject', default='', help='Subject of the mail (Leave blank if not known')
def main(pull_emails, restore_emails, read_emails, sender, recipient, subject, start_date, end_date, hard_delete):
    click.echo('Running Email Script')
    if not pull_emails and not restore_emails and not read_emails:
        raise click.UsageError('Please use one of "--pull-emails", "--restore-emails" or "--read-emails" options. Use --help to display the options')

    if not sender and not recipient and not subject:
        raise click.UsageError('At the least subject or recipient or sender needs to be specified.')

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)-15s [%(levelname)-8s]: %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p')
    mailApp.mailApp.parser(pull_emails, restore_emails, read_emails, sender, recipient, subject, start_date, end_date, hard_delete)


if __name__ == '__main__':
    main()