import praw

from globals import config

USER_AGENT = "SakuraiBotUltimate by /u/Wiwiweb for /r/smashbros"

reddit = praw.Reddit(client_id=config['Secrets']['reddit_client_id'],
                     client_secret=config['Secrets']['reddit_client_secret'],
                     username=config['Reddit']['username'],
                     password=config['Secrets']['reddit_password'],
                     user_agent=USER_AGENT)

submission = praw.models.Submission(reddit, id='939xks')
for flair in submission.flair.choices():
    print(flair)
