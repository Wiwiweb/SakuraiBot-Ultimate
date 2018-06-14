from collections import namedtuple
from datetime import datetime
from time import sleep

import praw
import requests
from bs4 import BeautifulSoup

from globals import config, log, test_mode

SMASH_BLOG_JSON = 'https://www.smashbros.com/data/bs/en_US/json/en_US.json'
IMGUR_UPLOAD_API = 'https://api.imgur.com/3/image'
IMGUR_CREATE_ALBUM_API = 'https://api.imgur.com/3/album'
REDDIT_TITLE_LIMIT = 300

USER_AGENT = "SakuraiBotUltimate by /u/Wiwiweb for /r/smashbros"

Post = namedtuple('Post', 'title date text images link')

processed_posts = None


def bot_loop():
    all_posts = get_all_blog_posts()
    new_posts = find_new_posts(all_posts)

    for post in new_posts:
        log.info(post)
        url = post.link
        if url is None and len(post.images) > 0:
            url = upload_to_imgur(post)
        post_to_reddit(post, url)
        add_to_processed_posts(post)

    sleep(config['Sleep']['new_post_check'])


def get_all_blog_posts():
    req = requests.get(SMASH_BLOG_JSON)
    posts_json = req.json()
    posts = {}
    for post_json in posts_json:
        title = post_json['title']['rendered']
        date = post_json['date_gmt']
        text = post_json['acf']['editor']\

        # Strip HTML
        soup = BeautifulSoup(text, 'html5lib')
        text = soup.get_text()

        images = []
        for i in range(1, 5):
            image_url = post_json['acf']['image{}'.format(i)]['url']
            if image_url is not None:
                image_url = 'https://www.smashbros.com/{}'.format(image_url[7:])
                images.append(image_url)
        link = post_json['acf']['link_url']
        if link is '':
            link = None
        posts[title] = Post(title=title, date=date, text=text, images=images, link=link)
    return posts


def find_new_posts(all_posts):
    global processed_posts
    if processed_posts is None:
        processed_posts = read_processed_posts_file()

    all_posts_titles = set(all_posts.keys())
    new_post_titles = all_posts_titles - processed_posts
    new_posts = [all_posts[new_post_title] for new_post_title in new_post_titles]
    return new_posts


def read_processed_posts_file():
    postf = open(config['Files']['processed_posts'], 'r')
    lines = postf.read().splitlines()
    postf.close()
    return set(lines)


def upload_to_imgur(post):
    single_picture = len(post.images) == 1
    image_delete_hashes = []
    single_picture_url = None
    if test_mode:
        # Upload anonymously
        headers = {'Authorization': 'Client-ID ' + config['Secrets']['imgur_client_id']}
    else:
        headers = {'Authorization': 'Bearer ' + config['Secrets']['imgur_access_token']}

    # Upload image(s)
    for image_url in post.images:
        parameters = {'image': image_url,
                      'type': 'URL'}
        if single_picture:
            parameters['description'] = post.text
        req = requests.post(IMGUR_UPLOAD_API, data=parameters, headers=headers)
        json = req.json()
        log.debug(json)
        image_delete_hashes.append(json['data']['deletehash'])
        single_picture_url = json['data']['link']

    if single_picture:
        log.info("Uploaded picture {}".format(single_picture_url))
        return single_picture_url
    else:
        # Create album and return album URL
        parameters = {'deletehashes[]': image_delete_hashes,
                      'description': post.text}
        req = requests.post(IMGUR_CREATE_ALBUM_API, data=parameters, headers=headers)
        json = req.json()
        log.debug(json)
        url = 'https://imgur.com/a/{}'.format(json['data']['id'])
        log.info("Uploaded album {}".format(url))
        return url


def post_to_reddit(post, url):
    reddit_config = 'Reddit_test' if test_mode else 'Reddit'
    reddit = praw.Reddit(client_id=config['Secrets']['reddit_client_id'],
                         client_secret=config['Secrets']['reddit_client_secret'],
                         username=config[reddit_config]['username'],
                         password=config['Secrets']['reddit_password'],
                         user_agent=USER_AGENT)

    subreddit = reddit.subreddit(config[reddit_config]['subreddit'])

    text = post.text
    date = datetime.strptime(post.date, '%Y/%m/%d %H:%M:%S')
    date_string = date.strftime('%m/%d')
    title_format = "New Smash Blog Post! ({}) {}"
    title = title_format.format(date_string, text)
    text_too_long = False
    if len(title) > REDDIT_TITLE_LIMIT:
        too_long = ' [...]" (Text too long! See comment)'
        # allowed_text_length =
        # length of text - the number of chars we must remove
        # - the length of the text we add at the end
        allowed_text_length = \
            len(text) \
            - (len(title) - REDDIT_TITLE_LIMIT) \
            - len(too_long)
        while len(text) > allowed_text_length:
            text = text.rsplit(' ', 1)[0] # Remove last word
        text += too_long
        title = title_format.format(date_string, text)
        text_too_long = True

    selftext = '' if url is None else None
    submission = subreddit.submit(title=title, url=url, selftext=selftext)
    log.info("Created reddit post: {}".format(submission.shortlink))
    log.info("Flair choices: {}".format(submission.flair.choices()))  # TODO: look and remove

    # Add full text comment
    if text_too_long:
        # Reddit formatting
        reddit_text = post.text.replace("\r\n\r\n", "\n\n>")
        reddit_text = reddit_text.replace("\r\n", "  \n")
        comment_body = "Full text:  \n>" + reddit_text
        submission.reply(comment_body)
        log.info("Text too long. Added to comment.")


def add_to_processed_posts(post):
    # Add to global var
    global processed_posts
    processed_posts.add(post.title)

    # Add to file
    processed_post = 'processed_post_test' if test_mode else 'processed_post'
    postf = open(config['Files'][processed_post], 'a+')
    postf.seek(0)
    postf.write("\n{}".format(post.title))
    postf.close()


if __name__ == '__main__':
    log.info('=== Starting SakuraiBot-Ultimate ===')
    bot_loop()
