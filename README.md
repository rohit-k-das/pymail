
Google/Microsoft Email Python Script
------------------------------------

The script uses Google and Microsoft API's to read, delete or restore emails from the user's mailbox. You can use whichever your company uses and modify mailApp.

At the time of writing this, Microsoft does not have a good way to mass pull emails and is kind of a pain to delete or fetch mail for a particular user for security investigations and i didn't want to use powershell.

For Google Suite API, use https://developers.google.com/identity/protocols/OAuth2ServiceAccount to setup the service accounts necessary for Gmail & Directory API.

For Microsoft Outlook API, use https://docs.microsoft.com/en-us/graph/auth-v2-service?context=graph%2Fapi%2F1.0&view=graph-rest-1.0 to register an app and get domain wide delegated permissions i.e. access mailbox without the user.

Install requirements: `pip install -r requirements.lock`

Example Command: 
`python3 -B main.py --pull-emails --hard-delete --subject "Testing 124" --recipient "admin@company.com" --start-date "2018-02-09"`

The script goes through the mailbox of the recipient as specified in the option. If the recipient option is not specified, then the script searches through all the users of the company.
Sometimes Microsoft Outlook API is not able to parse the subject in the options, use the other options to get the same results

Use the -h option to get a list of options: `python -B main.py --help`

Note: If you are using Microsoft and you wanted to copy/move mails from one mailbox to a shared mailbox, you would need to:
 1. Ensure the user has access to both these mailboxes. 
 2. Create a custom function that utilizes the function `copy_email` or `move_email_to_folder`. 
 3. Ignore the error from point 2 and verify that the mail has been moved.
