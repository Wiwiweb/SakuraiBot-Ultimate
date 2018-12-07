from collections import namedtuple
from datetime import datetime, timedelta
from time import sleep

import praw
import prawcore.exceptions
import requests
from bs4 import BeautifulSoup

from globals import config, log, test_mode

SMASH_BLOG_JSON = 'https://www.smashbros.com/data/bs/en_US/json/en_US.json'
SMASH_MUSIC_PAGE = 'https://www.smashbros.com/en_US/sound/index.html'
SMASH_MUSIC_JSON = 'https://www.smashbros.com/assets_v2/data/sound.json'
LINKS_PREFIX = 'https://www.smashbros.com'
YOUTUBE_PREFIX = 'https://www.youtube.com/watch?v='
IMGUR_UPLOAD_API = 'https://api.imgur.com/3/image'
IMGUR_CREATE_ALBUM_API = 'https://api.imgur.com/3/album'
REDDIT_TITLE_LIMIT = 300

USER_AGENT = "SakuraiBotUltimate by /u/Wiwiweb for /r/smashbros"

Post = namedtuple('Post', 'title date text images link bonus_links')

processed_posts = None


def bot_loop():
    sleep_time = int(config['Sleep']['new_post_check'])
    error_sleep_time = int(config['Sleep']['error'])

    while True:
        all_posts = get_all_blog_posts()
        if all_posts is None:
            # There was an error getting the blog posts
            sleep(error_sleep_time)
            continue
        new_posts = find_new_posts(all_posts)

        for post in new_posts:
            log.info(post)
            image_url = None
            if len(post.images) > 0:
                image_url = upload_to_imgur(post)
            try:
                post_to_reddit(post, image_url)
            except prawcore.exceptions.ResponseException as e:
                log.error(e)
                if 500 <= e.response.status_code <= 504:
                    continue
                else:
                    raise e
            add_to_processed_posts(post)

        sleep(sleep_time)


def get_all_blog_posts():
    try:
        req = requests.get(SMASH_BLOG_JSON)
        posts_json = req.json()
        posts = {}
        for post_json in posts_json:

            title = post_json['title']['rendered']
            date = post_json['date_gmt']
            text = post_json['acf']['editor']
            link = post_json['acf']['link_url']
            if link is '':
                link = None

            images = []
            for i in range(1, 5):
                image_url = post_json['acf']['image{}'.format(i)]['url']
                if image_url is not None:
                    image_url = LINKS_PREFIX + image_url[7:]
                    images.append(image_url)

            # Find links in text
            bonus_links = {}
            soup = BeautifulSoup(text, 'html.parser')
            a_tags = soup.find_all('a')
            a_tags = [a_tag.extract() for a_tag in a_tags]
            if len(a_tags) == 1 and link is None and len(images) == 0:
                # Make this link found in text the main link
                link = format_link(a_tags[0]['href'])
            elif len(a_tags) > 0:
                bonus_links = {a_tag.text: format_link(a_tag['href']) for a_tag in a_tags}

            if link == SMASH_MUSIC_PAGE:
                link = fetch_last_music_youtube()

            # Strip other HTML
            text = soup.text

            posts[title] = Post(title=title, date=date, text=text, images=images, link=link, bonus_links=bonus_links)
        return posts
    except (requests.HTTPError, requests.ConnectionError) as e:
        log.error(e)
        return None


def format_link(link):
    if link[0] is '/':  # Relative link
        return LINKS_PREFIX + link
    else:  # Absolute link
        return link


def fetch_last_music_youtube():
    try:
        req = requests.get(SMASH_MUSIC_JSON)
        full_json = req.json()
        youtube_id = full_json['sound'][0]['youtubeID']
        return YOUTUBE_PREFIX + youtube_id
    except (requests.HTTPError, requests.ConnectionError) as e:
        log.error(e)
        return SMASH_MUSIC_PAGE


def find_new_posts(all_posts):
    global processed_posts
    if processed_posts is None:
        processed_posts = read_processed_posts_file()

    all_posts_titles = set(all_posts.keys())
    new_post_titles = all_posts_titles - processed_posts
    new_posts = [all_posts[new_post_title] for new_post_title in new_post_titles]
    return new_posts


def read_processed_posts_file():
    processed_post = 'processed_posts_test' if test_mode else 'processed_posts'
    postf = open(config['Files'][processed_post], 'r', encoding='utf-8')
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


def post_to_reddit(post, image_url):
    reddit_config = 'Reddit_test' if test_mode else 'Reddit'
    reddit = praw.Reddit(client_id=config['Secrets']['reddit_client_id'],
                         client_secret=config['Secrets']['reddit_client_secret'],
                         username=config[reddit_config]['username'],
                         password=config['Secrets']['reddit_password'],
                         user_agent=USER_AGENT)

    subreddit = reddit.subreddit(config[reddit_config]['subreddit'])

    text = '"' + post.text.strip().replace('\n', ' - ') + '"'
    date = datetime.strptime(post.date, '%Y/%m/%d %H:%M:%S')
    us_date = date - timedelta(hours=8)  # Copies the behaviour of the smash blog
    date_string = "{}/{}/{}".format(us_date.strftime('%m').lstrip('0'), us_date.strftime('%d').lstrip('0'), us_date.strftime('%Y'))
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
            text = text.rsplit(' ', 1)[0]  # Remove last word
        text += too_long
        title = title_format.format(date_string, text)
        text_too_long = True

    url = image_url if post.link is None else post.link
    selftext = '' if url is None else None
    submission = subreddit.submit(title=title, url=url, selftext=selftext,
                                  flair_id=config[reddit_config]['flair_id'], resubmit=True)
    log.info("Created reddit post: {}".format(submission.shortlink))

    # Comment
    comment_format = '{full_text}\n\n' \
                     '{bonus_links}\n\n' \
                     '{bonus_pictures}\n\n' \
                     '[Super Smash Blog](https://www.smashbros.com/en_US/blog/index.html)\n\n' \
                     '---\n\n' \
                     "#It's been a pleasure everyone! See you all for Smash 6!\n\n" \
                     "^(Who am I kidding. With DLC, I'll have to stick around as long as blog posts continue. I wonder if I'll ever get to take a break 🤖)"

    full_text = ''
    if text_too_long:
        # Reddit formatting
        reddit_text = post.text.replace("\r\n\r\n", "\n\n>")
        reddit_text = reddit_text.replace("\r\n", "  \n")
        full_text = "Full text:  \n>" + reddit_text
        log.info("Text too long. Added to comment.")

    bonus_links = ''
    if len(post.bonus_links) > 0:
        plural = 's' if len(post.bonus_links) > 1 else ''
        bonus_links = 'Link{} from this post:  \n'.format(plural)
        for text, url in post.bonus_links.items():
            bonus_links += "[{}]({})  \n".format(text, url)
            log.info("Bonus links. Added to comment.")

    bonus_pictures = ''
    # Show bonus pictures only when they were not the main link
    if post.link is not None and image_url is not None:
        plural = 's' if len(post.images) > 1 else ''
        bonus_pictures = "[Bonus pic{}!]({})".format(plural, image_url)
        log.info("Bonus pics. Added to comment.")

    comment_body = comment_format.format(full_text=full_text, bonus_links=bonus_links, bonus_pictures=bonus_pictures)
    submission.reply(comment_body)


def add_to_processed_posts(post):
    # Add to global var
    global processed_posts
    processed_posts.add(post.title)

    # Add to file
    processed_post = 'processed_posts_test' if test_mode else 'processed_posts'
    postf = open(config['Files'][processed_post], 'a+', encoding='utf-8')
    postf.seek(0)
    postf.write("\n{}".format(post.title))
    postf.close()


if __name__ == '__main__':
    log.info('=== Starting SakuraiBot-Ultimate ===')

    # Create file if it doesn't exist
    processed_post = 'processed_posts_test' if test_mode else 'processed_posts'
    open(config['Files'][processed_post], 'a').close()

    bot_loop()
