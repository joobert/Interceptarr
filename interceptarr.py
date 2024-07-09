import os
import requests
import logging
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dotenv import load_dotenv

app = Flask(__name__)

load_dotenv()

# Configuration from environment variables
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DISCORD_OVERRIDE_WEBHOOK_URL = os.getenv('DISCORD_OVERRIDE_WEBHOOK_URL')
SHOW_EPISODE_THUMBNAIL = os.getenv('SHOW_EPISODE_THUMBNAIL', 'True')
HOST = os.getenv('WEBHOOK_HOST')
PORT = int(os.getenv('WEBHOOK_PORT', 8700))

# Set up logging
log_file = 'interceptarr_logs.txt'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler(log_file),
    logging.StreamHandler()
])

# Get the first aired date for a given series, season, and episode
def get_episode_info(series_title, season, episode, series_url):
    logging.info(f"Searching TVDB for: {series_title}, Season: {season}, Episode: {episode}")

    # Search for the series season data on TVDB
    season_url = f"{series_url}/seasons/official/{season}"
    try:
        response = requests.get(season_url)
        logging.info(f"Fetch response status: {response.status_code}")
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table', {'class': 'table table-bordered'})
        if table:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) > 1:
                    # Format the season and episode to match the expected format, e.g., "S02E03"
                    season_episode_code = cols[0].text.strip()
                    expected_code = f"S{int(season):02}E{int(episode):02}"
                    if season_episode_code == expected_code:
                        first_aired_date_raw = cols[2].text.strip().split('\n')[0]
                        first_aired_date_formatted = datetime.strptime(first_aired_date_raw, '%B %d, %Y').strftime('%Y-%m-%d')
                        episode_hyperlink = cols[1].find('a')
                        episode_url = "https://thetvdb.com" + episode_hyperlink['href']
                        episode_title_tvdb = episode_hyperlink.text.strip()
                        logging.info(f"First aired date for S{season}E{episode}: {first_aired_date_formatted}")
                        return first_aired_date_raw, first_aired_date_formatted, episode_url, episode_title_tvdb
        else:
            logging.warning("Episode data not found")
    except requests.RequestException as e:
        logging.error(f"Error fetching episode data from TVDB: {e}")

    return None, None, None

# Get the thumbnail URL for a given episode
def get_episode_thumbnail(episode_url):
    try:
        response = requests.get(episode_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        thumbnail_div = soup.find('div', class_='col-xs-12 col-sm-4 col-md-4 col-lg-3 col-xl-2')
        if thumbnail_div:
            thumbnail_img = thumbnail_div.find('img')
            if thumbnail_img and thumbnail_img['src'] != '/images/missing/episode.jpg':
                thumbnail_url = thumbnail_div.find('a')['href']
                logging.info(f"Episode thumbnail URL found: {thumbnail_url}")
                return thumbnail_url
            else:
                logging.info("Episode thumbnail not found. Defaulting to series thumbnail.")
        else:
            logging.info("Episode thumbnail not found. Defaulting to series thumbnail.")
    except requests.RequestException as e:
        logging.error(f"Error fetching episode thumbnail: {e}")

    return None

# Function to fetch the overview of the episode if it is not present in the webhook data
def get_episode_overview(episode_url):
    try:
        response = requests.get(episode_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        overview_div = soup.find('div', class_='change_translation_text', attrs={'data-language': 'eng'})
        if overview_div:
            overview = overview_div.find('p').text.strip()
            return overview
        else:
            logging.info("Episode overview not found.")
    except requests.RequestException as e:
        logging.error(f"Error fetching episode overview: {e}")

    return None

# Notify a separate Discord webhook that the episode data was overwritten
def notify_discord_on_overwrite(episode_title, episode_title_tvdb, episode_url, full_title):
    logging.info("Notifying Discord of improper/overwritten data...")
    data = {
        "embeds": [
            {
                "author": {"name": "Warning - Improper Episode Metadata"},
                "title": f"{full_title}",
                "url": f"{episode_url}",
                "description": "Sonarr did not have the proper metadata when importing this episode. Although the episode was successfully imported, its title and overview in Sonarr may still be incorrect or missing. \n\nSonarr will update this automatically when it fetches the correct metadata, however, __your Plex/Jellyfin metadata will need to be refreshed manually__.",
                "color": 0xFFC030,
                "fields": [
                    {"name": "Original Episode Title", "value": f"{episode_title}", "inline": False},
                    {"name": "New Episode Title", "value": f"{episode_title_tvdb}", "inline": False},
                ]
            }
        ]
    }
    try:
        response = requests.post(DISCORD_OVERRIDE_WEBHOOK_URL, json=data)
        response.raise_for_status()
        logging.info(f"Notified Discord with response status: {response.status_code}")
    except requests.RequestException as e:
        logging.error(f"Error notifying Discord: {e}")

# Webhook listener
@app.route('/', methods=['POST'])
def webhook_listener():
    data = request.json
    logging.info("Received webhook data from Sonarr")
    if 'embeds' in data:
        for embed in data['embeds']:
            embed_overwritten = False  # Flag to check if the embed data (excluding thumbnail) has been overwritten by TVDB data
            if 'title' in embed and 'url' in embed:
                title_parts = embed['title'].split(' - ')
                if len(title_parts) == 3:
                    series_title, season_episode, episode_title = title_parts
                    season, episode = map(lambda x: x.lstrip('0'), season_episode.split('x', 1))
                    logging.info(f"Processing episode: {series_title}, Episode: {season_episode} - {episode_title}")

                    # Get the base URL for the series on TVDB and the URL it redirects to
                    series_url_base = embed['url']
                    series_url = requests.get(series_url_base).url

                    # Extract the overview from the fields so the embed can be reformatted
                    overview = next((field.get('value', '') for field in embed.get('fields', []) if field.get('name') == 'Overview'), '')

                    # Get the first aired date and episode URL from TVDB
                    first_aired_date_raw, first_aired_date_formatted, episode_url, episode_title_tvdb = get_episode_info(series_title, season, episode, series_url)
                    if first_aired_date_formatted:
                        first_aired_date_formatted = datetime.strptime(first_aired_date_formatted, '%Y-%m-%d')
                        if first_aired_date_formatted > datetime.now() - timedelta(weeks=1):
                            logging.info("First aired date is within the last week, continuing...")

                            # Update the embed with the episode title from TVDB if it differs from the webhook data
                            if episode_title_tvdb != episode_title:
                                logging.info(f"Episode title found in webhook data from Sonarr is improper. Updating episode title to: {episode_title_tvdb}")
                                full_title = f"{series_title} - {season_episode} - {episode_title_tvdb}"
                                embed.update({'title': f"{full_title}"})
                                embed_overwritten = True

                            # Update the embed with the episode overview if it is not present in the webhook data
                            if overview == '':
                                logging.info("Episode overview not found in webhook data from Sonarr, fetching from TVDB...")
                                overview = get_episode_overview(episode_url)
                                embed_overwritten = True

                            # Prepare and overwrite the data to forward to the Discord webhook
                            fields = [
                                {"name": "Released", "value": f"{first_aired_date_raw}", "inline": True},
                                {"name": "Overview", "value": f"{overview}", "inline": False},
                            ]
                            embed.update({
                                'author': {'name': "New Episode Now Available"},
                                'description': '',
                                'color': 0x2ECB6F,
                                'fields': fields
                            })

                            # Optionally include the episode thumbnail
                            if SHOW_EPISODE_THUMBNAIL == 'True':
                                thumbnail_url = get_episode_thumbnail(episode_url)
                                if thumbnail_url is not None:
                                    embed.update({'image': {'url': thumbnail_url}})

                            # Forward the data to the main Discord webhook
                            try:
                                logging.info("Notifying Discord of new episode...")
                                response = requests.post(DISCORD_WEBHOOK_URL, json=data)
                                response.raise_for_status()
                                logging.info(f"Notified Discord with response status: {response.status_code}")

                                # Notify the other Discord webhook (if present) if the embed was overwritten with new data
                                if embed_overwritten and DISCORD_OVERRIDE_WEBHOOK_URL:
                                    notify_discord_on_overwrite(episode_title, episode_title_tvdb, episode_url, full_title)

                                return jsonify({'status': 'forwarded', 'response': response.status_code}), response.status_code
                            except requests.RequestException as e:
                                logging.error(f"Error notifying Discord: {e}")
                                return jsonify({'status': 'error', 'message': str(e)}), 500

                        # If the first aired date is not within the last week, ignore the episode
                        else:
                            logging.info("First aired date is not within the last week, ignoring...")
                            return jsonify({'status': 'ignored'}), 200

    # If the data does not match the expected format, ignore it
    logging.info("Ignoring webhook data")
    return jsonify({'status': 'ignored'}), 200

if __name__ == '__main__':
    logging.info(f"Starting Interceptarr server on port {PORT}...")
    app.run(host=HOST, port=PORT)
