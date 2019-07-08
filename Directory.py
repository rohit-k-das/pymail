import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import concurrent.futures
import json
import logging
import time
import jwt
import ConfigParser
import os

MAX_THREADS = 14  # Get max number of threads for multi-threading

logger = logging.getLogger(__name__)

directory_api = 'https://www.googleapis.com/admin/directory/v1/{0}'

Config = ConfigParser.ConfigParser()
Config.read(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'settings.ini'))
google_service_account_secret = Config.get('Settings', 'Google_Service_Account_Secret')
google_service_account_id = Config.get('Settings', 'Google_Service_Account_ID')
company_domain = Config.get('Settings', 'Company_Domain')


# Generate session with max of 3 retries and interval of 1 second
def session_generator():
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=0.5)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


# Create OAuth token per requirement for each recipient
def generate_directory_api_access_token(recipient):
    access_token = None
    expiry = None
    jwt_header = {"alg": "RS256", "typ": "JWT"}
    iat = time.time()
    exp = iat + 3600
    jwt_claim_set = {
        'iss': google_service_account_id,
        'scope': 'https://www.googleapis.com/auth/admin.directory.group.readonly https://www.googleapis.com/auth/admin.directory.user.readonly',
        'sub': recipient,
        'aud': 'https://www.googleapis.com/oauth2/v4/token',
        'iat': iat,
        'exp': exp
    }

    secret = bytes(google_service_account_secret.replace('\\n', '\n'), 'utf-8')
    signed_jwt = jwt.encode(jwt_claim_set, secret, headers=jwt_header, algorithm='RS256')

    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion': signed_jwt.decode('utf-8').replace("'", '"')}
    url = 'https://www.googleapis.com/oauth2/v4/token'
    session = session_generator()
    resp = session.post(url, headers=headers, data=json.dumps(data))
    if resp.ok:
        response = resp.json()
        access_token = response['access_token']
        expiry = time.time() + response['expires_in']
    elif resp.status_code == 400 and "Invalid email" in resp.json()['error']['message']:
        logger.info("Recipient %s not found" % recipient)
    elif resp.status_code == 429:
        logger.error('Too many requests. Sleeping %s' % resp.json()['error']['message'])
        time.sleep(1)
        access_token, expiry = generate_directory_api_access_token(recipient)
    else:
        logger.error('Failed to generate access token')
        logger.error("%d:%s" % (resp.status_code, resp.text))
    return access_token, expiry


# Check if user/email exists
def user_check(recipient, access_token):
    user_email = ""  # Default value
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer %s' % access_token}
    session = session_generator()
    url = directory_api.format("users/{0}")
    resp = session.get(url.format(recipient), headers=headers)
    response = resp.json()
    if resp.ok:
        if 'user' in response['kind'] and response['isMailboxSetup']:
            user_email = response['primaryEmail']
    # Handle Rate Limiting
    elif resp.status_code == 429 or resp.status_code == 403:
        logger.error('Too many requests. Sleeping %s' % resp.json()['error_description'])
        time.sleep(1)
        user_email = user_check(recipient, access_token)
    # If user doesn't exist
    elif resp.status_code == 400 and response['error']['message'] == "Type not supported: userKey":
        logger.error("%s is not a user" % recipient)
    elif resp.status_code == 403 and response['error']['message'] == 'Not Authorized to access this resource/api':
        logger.error("%s is not a user" % recipient)
    elif resp.status_code == 404 and response['error']['message'] == 'Resource Not Found: userKey':
        logger.error("%s is not a user" % recipient)
    # Handle other http errors
    else:
        logger.error("Unable to check user %s" % recipient)
        logger.error("%d:%s" % (resp.status_code, response))

    return user_email


# Check if the dl exists
def group_check(recipient, access_token):
    dl_email = ""  # Default value of DL email
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer %s' % access_token}
    session = session_generator()
    url = directory_api.format('groups/{0}')
    resp = session.get(url.format(recipient), headers=headers)
    response = resp.json()
    if resp.ok:
        if 'group' in response['kind']:
            if int(response['directMembersCount']) > 0:
                dl_email = response['email']
    # Handle Rate Limiting
    elif resp.status_code == 429:
        logger.error('Too many requests. Sleeping %s' % resp.json()['error']['message'])
        time.sleep(1)
        dl_email = group_check(recipient, access_token)
    # If group doesn't exist
    elif resp.status_code == 404 and response['error']['message'] == "Resource Not Found: groupKey":
        logger.error("%s is not a group" % recipient)
    elif resp.status_code == 403 and response['error']['message'] == 'Not Authorized to access this resource/api':
        logger.error("%s is not a group" % recipient)
    # Handle other http errors
    else:
        logger.error("Unable to check group %s" % recipient)
        logger.error("%d:%s" % (resp.status_code, response))

    return dl_email


# Get all members in a DL
def get_group_members(recipient, access_token, pagination_url=""):
    recipients = []  # All individual mailboxes/users
    groups = []  # If the DL contains another DL

    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer %s' % access_token}
    session = session_generator()

    if pagination_url:
        resp = session.get(pagination_url, headers=headers)
    else:
        params = {'maxResults': 1000}
        url = directory_api.format("groups/{0}/members")
        resp = session.get(url.format(recipient), headers=headers, params=params)

    response = resp.json()
    if resp.ok:
        if response['members']:
            for member in response['members']:
                if member['status'] == 'ACTIVE':
                    # If the recipient is  group/DL
                    if 'group' in member['kind']:
                        groups.append(member['email'])
                    # If the recipient is a user
                    if 'member' in member['kind']:
                        recipients.append(member['email'])

        # Make recursive calls if a DL contains another DL
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            fs = [executor.submit(get_group_members, email, access_token) for email in groups]
            block_of_futures = []
            if len(fs) > 15:
                block_of_futures = [fs[i:i + 15] for i in range(0, len(fs), 15)]
            else:
                block_of_futures.append(fs)
            for futures in block_of_futures:
                if futures:
                    for future in concurrent.futures.as_completed(futures):
                        recipients.extend(future.result())

        # Pagination
        if 'nextPageToken' in response:
            pageToken = response['nextPageToken']
            if 'pageToken' in resp.url:
                pagination_url = '{0}&pageToken={1}'.format(resp.url.split('&pageToken')[0], pageToken)
            else:
                pagination_url = '{0}&pageToken={1}'.format(resp.url, pageToken)
        else:
            pagination_url = ''

        if pagination_url:
            recipients.extend(get_group_members(recipient, access_token, pagination_url))

    # Handle Rate Limiting
    elif resp.status_code == 429:
        logger.error('Too many requests. Sleeping %s' % resp.json()['error']['message'])
        time.sleep(1)
        recipients.extend(get_group_members(recipient, access_token, pagination_url))
    # Handle other http errors
    else:
        logger.error("Unable to get members of group %s" % recipient)
        logger.error("%d:%s" % (resp.status_code, response))

    return recipients


# Check if employee still works in the company
def recipient_exits_check(recipient, access_token):
    recipients = []  # A list of recipients that still work in the company

    # Get the username associated with the email address
    user_email = user_check(recipient, access_token)
    if user_email:
        recipients.append(user_email)

    else:
        # Might be a DL
        dl_email = group_check(recipient, access_token)
        if dl_email:
            recipients_from_dl = get_group_members(recipient, access_token)
            if not recipients_from_dl:
                # For DL containing 0 members
                logger.info("No recipients found for {0}".format(recipient))
            else:
                recipients.extend(recipients_from_dl)  # Add members of DL
        else:
            logger.info("{0} not a Email DL nor a user".format(recipient))

    return recipients


# Get all users that have a mailbox
def list_all_active_users(access_token, pagination_url=""):
    recipients = []
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer %s' % access_token}
    session = session_generator()
    if pagination_url:
        resp = session.get(pagination_url, headers=headers)
    else:
        params = {'maxResults': 500, 'orderBy': 'email', 'domain': company_domain, 'query': 'isMailboxSetup=True&isSuspended=False'}
        url = directory_api.format("users")
        resp = session.get(url, headers=headers, params=params)

    response = resp.json()
    if resp.ok:
        for user in response['users']:
            recipients.append(user['primaryEmail'])

        # Pagination
        if 'nextPageToken' in response:
            pageToken = response['nextPageToken']
            if 'pageToken' in resp.url:
                pagination_url = '{0}&pageToken={1}'.format(resp.url.split('&pageToken')[0], pageToken)
            else:
                pagination_url = '{0}&pageToken={1}'.format(resp.url, pageToken)
        else:
            pagination_url = ''

        if pagination_url:
            recipients.extend(list_all_active_users(access_token, pagination_url))

    # Handle Rate Limiting
    elif resp.status_code == 429:
        logger.error('Too many requests. Sleeping %s' % resp.json()['error']['message'])
        time.sleep(1)
        recipients.extend(list_all_active_users(access_token, pagination_url))

    # Handle other http errors
    else:
        logger.error("Unable to get all active users")
        logger.error("%d:%s" % (resp.status_code, response))

    return recipients
