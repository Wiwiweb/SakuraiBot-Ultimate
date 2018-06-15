import logging
import sys
from traceback import format_tb

from configparser import ConfigParser
from logging.handlers import TimedRotatingFileHandler
import boto3
from botocore.exceptions import NoCredentialsError

# Test mode
if len(sys.argv) > 1 and '--test' in sys.argv:
    print("=== TEST MODE ===")
    test_mode = True
else:
    test_mode = False

# Config
CONFIG_FILE = "../cfg/config.ini"
SECRETS_FILE_PRIVATE = "../cfg/secrets.ini"
config = ConfigParser()
config.read([CONFIG_FILE, SECRETS_FILE_PRIVATE])

# Logger
log = logging.getLogger('PrismataBot')
log.setLevel(logging.DEBUG)
log_format = '%(asctime)s: %(levelname)s - %(message)s'
handler = TimedRotatingFileHandler(config['Files']['logfile'], 'midnight', encoding='utf-8')
handler.setFormatter(logging.Formatter(log_format))
log.addHandler(handler)


# Exception logging
def log_uncaught_exceptions(ex_cls, ex, tb):
    log.critical(''.join(format_tb(tb)))
    log.critical('{0}: {1}'.format(ex_cls, ex))

sys.excepthook = log_uncaught_exceptions

# Config secrets
if 'Secrets' not in config:
    config.add_section('Secrets')
if not config['Secrets']['imgur_client_id']:
    try:
        ssm = boto3.client('ssm', region_name=config['AWS']['region'])
        secrets = ['imgur_client_id', 'imgur_access_token',
                   'reddit_client_id', 'reddit_client_secret', 'reddit_password']
        response = ssm.get_parameters(Names=secrets, WithDecryption=True)
        for parameter in response['Parameters']:
            config.set('Secrets', parameter['Name'], parameter['Value'])
        log.info("Secrets loaded from SSM")
    except NoCredentialsError:
        log.error("Couldn't load secrets!")
        raise SystemExit()
