import json
import webbrowser

import os
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, request
from flask import render_template, redirect
from stravalib.client import Client
from stravalib.util import limiter

try:
    from local import MY_STRAVA_CLIENT_SECRET
    MY_STRAVA_CLIENT_ID = 119
except ImportError as e:
    print("strava client secret token required in local.py")
    raise ImportError(e.__str__())


app = Flask(__name__)
PORT = int(os.environ.get("PORT", 8001))
APP_NAME = os.environ.get("HEROKU_APP_NAME")
DOMAIN = "https://{}.herokuapp.com".format(APP_NAME) if APP_NAME else "http://127.0.0.1:" + str(PORT)
print("DEBUG: running on :" + DOMAIN)


"""
# one image. public.
activity_url = "https://www.strava.com/activities/648092664"
# two images, private activity, so we can only get one
activity_url = "https://www.strava.com/activities/648107295"
# no images
activity_url = "https://www.strava.com/activities/646906435"
# redirect from segment_effort
activity_url = "https://www.strava.com/segment_efforts/15839916336"

# <meta content="https://dgtzuqphqg23d.cloudfront.net/wMOQejtoja69VLObx5nr_1B5zVD-ju7OSyszGll35ww-768x432.jpg" property="og:image">

segment_id = 1670623 #
segment_id = 3896014 #shred it!
"""


def get_images_from_segment(segment_id, client):
    leaderboard = client.get_segment_leaderboard(segment_id, timeframe='this_week', top_results_limit=100)
    activities = [x.activity_id for x in leaderboard]

    p = []
    for actid in activities:
        p.extend(get_pictures_from_activity("https://www.strava.com/activities/{}".format(actid)))

    return p


@app.route("/demo")
def show_images_demo():
    # look into this: https://github.com/saimn/sigal/
    with open("demo_images.json") as f:
        images = json.load(f)['images']
    return render_template('test.html', images=images)


@app.route("/segment/<segment_id>")
def get_images(segment_id):
    access_token = request.cookies.get('access_token')
    if not access_token:
        return redirect("/")
    client = Client(rate_limiter=limiter.DefaultRateLimiter())
    client.access_token = access_token

    # look into this: https://github.com/saimn/sigal/
    images = get_images_from_segment(segment_id, client)
    return render_template('test.html', images=images)


@app.route("/")
def auth():
    access_token = request.cookies.get('access_token')
    if access_token:
        # Success!
        return show_images_demo()
    else:
        client = Client()
        url = client.authorization_url(client_id=MY_STRAVA_CLIENT_ID, redirect_uri=DOMAIN + '/authorization')
        print("DEBUG: auth url :" + url)
        return redirect(url, code=302)


@app.route("/authorization")
def authorization():
    code = request.args.get('code')
    client = Client()
    access_token = client.exchange_code_for_token(client_id=MY_STRAVA_CLIENT_ID,
                                                  client_secret=MY_STRAVA_CLIENT_SECRET,
                                                  code=code)
    response = redirect("/")
    response.set_cookie('access_token', access_token)
    return response


def show_page(html):
    # for debugging purposes
    path = os.path.abspath('temp.html')
    url = 'file://' + path
    with open(path, 'wb') as f:
        f.write(html)
    webbrowser.open(url)


def get_pictures_from_activity(activity_url):
    h = requests.get(activity_url)
    activity_id = int(h.url.rsplit("/")[-1].split("#")[0])
    # show_page(h.text.encode('utf-8'))
    soup = BeautifulSoup(h.text, 'lxml')

    try:
        s = [s for s in soup.find_all("script") if s.string and "renderInstagram" in s.string][0]
        photosJS = re.findall('var photosJson = (.*?);', s.string)

        if len(photosJS) == 0:
            # This is probably a private activity, so we can only get the first image. from the html mttadata
            # This seems like a bug in strava as it works even with private activities? But only for the first image
            images = set([x['content'] for x in soup.find_all("meta", property=["og:image", 'twitter:image'])])
            photos = [{'url': x, 'lat': None, 'lng': None, 'activity_id': activity_id} for x in images if
                      "summary_activity_generic" not in x]
            return photos

        photosStrava = json.loads(photosJS[0])
        photos = [{'url': x['large'], 'lat': x['lat'], 'lng': x['lng'], 'activity_id': x['activity_id']}
                  for x in photosStrava]
        return photos
    except Exception as e:
        print(e)
        return []


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
