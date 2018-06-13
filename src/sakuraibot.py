from collections import namedtuple
import requests

from globals import config, log, test_mode

SMASH_BLOG_JSON = 'https://www.smashbros.com/data/bs/en_US/json/en_US.json'

Post = namedtuple('Post', 'title date text images link')


def get_blog_posts():
    req = requests.get(SMASH_BLOG_JSON)
    posts_json = req.json()
    posts = []
    for post_json in posts_json:
        title = post_json['title']['rendered']
        date = post_json['date_gmt']
        text = post_json['acf']['editor']
        images = []
        for i in range(1, 5):
            image_url = post_json['acf']['image{}'.format(i)]['url']
            if image_url is not None:
                images.append(image_url)
        link = post_json['acf']['link_url']
        posts.append(Post(title=title, date=date, text=text, images=images, link=link))
    return posts


if __name__ == '__main__':
    log.info('=== Starting SakuraiBot-Ultimate ===')
    posts = get_blog_posts()
    for post in posts:
        print(post)
