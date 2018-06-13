from collections import namedtuple

import requests
from bs4 import BeautifulSoup

from globals import config, log, test_mode

SMASH_BLOG_JSON = 'https://www.smashbros.com/data/bs/en_US/json/en_US.json'
IMGUR_UPLOAD_API = 'https://api.imgur.com/3/image'
IMGUR_CREATE_ALBUM_API = 'https://api.imgur.com/3/album'

Post = namedtuple('Post', 'title date text images link')

processed_posts = None


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
    headers = {'Authorization': 'Client-ID ' + config['Secrets']['imgur_client_id']}

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
    url


def add_to_processed_posts(post):
    # Add to global var
    global processed_posts
    processed_posts.add(post.title)

    # Add to file
    postf = open(config['Files']['processed_posts'], 'a+')
    postf.seek(0)
    postf.write("\n{}".format(post.title))
    postf.close()


if __name__ == '__main__':
    log.info('=== Starting SakuraiBot-Ultimate ===')
    all_posts = get_all_blog_posts()
    new_posts = find_new_posts(all_posts)

    for post in new_posts:
        log.info(post)
        if len(post.images) > 0:
            url = upload_to_imgur(post)
        post_to_reddit(post, url)
        if not test_mode:
            add_to_processed_posts(post)
