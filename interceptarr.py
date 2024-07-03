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
                        episode_url = "https://thetvdb.com" + cols[1].find('a')['href']
                        logging.info(f"First aired date for S{season}E{episode}: {first_aired_date_formatted}")
                        return first_aired_date_raw, first_aired_date_formatted, episode_url
        else:
            logging.warning("Episode table not found")
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
            thumbnail_url = thumbnail_div.find('a')['href']
            logging.info(f"Episode thumbnail URL found: {thumbnail_url}")
            return thumbnail_url
        else:
            logging.warning("Thumbnail div not found")
    except requests.RequestException as e:
        logging.error(f"Error fetching episode thumbnail: {e}")
    return None

# Webhook listener
@app.route('/webhook', methods=['POST'])
def webhook_listener():
    data = request.json
    logging.info("Received webhook data")
    if 'embeds' in data:
        for embed in data['embeds']:
            if 'title' in embed and 'url' in embed:
                title_parts = embed['title'].split(' - ')
                if len(title_parts) == 3:
                    series_title, season_episode, episode_title = title_parts
                    season, episode = map(lambda x: x.lstrip('0'), season_episode.split('x', 1))
                    logging.info(f"Processing episode: {series_title}, Episode: {season_episode} - {episode_title}")

                    # Directly use the URL from the embed
                    series_url = embed['url']

                    # Extract the overview from the fields so the embed can be reformatted
                    overview = next((field.get('value', '') for field in embed.get('fields', []) if field.get('name') == 'Overview'), '')

                    # Get the first aired date and episode URL from TVDB
                    first_aired_date_raw, first_aired_date_formatted, episode_url = get_episode_info(series_title, season, episode, series_url)
                    if first_aired_date_formatted:
                        first_aired_date_formatted = datetime.strptime(first_aired_date_formatted, '%Y-%m-%d')
                        if first_aired_date_formatted > datetime.now() - timedelta(weeks=1):
                            logging.info("First aired date is within the last week, forwarding...")

                            # Prepare and overwrite the data to forward to the Discord webhook
                            fields = [
                                {"name": "Released", "value": f"{first_aired_date_raw}", "inline": True},
                                {"name": "Overview", "value": f"{overview}", "inline": False},
                            ]
                            embed.update({
                                'author': {'name': "New Episode Now Available", 'icon_url': ''},
                                'description': '',
                                'color': 0x2ECB6F,
                                'fields': fields
                            })
                            # Optionally include the episode thumbnail
                            if SHOW_EPISODE_THUMBNAIL == 'True':
                                embed.update({'image': {'url': get_episode_thumbnail(episode_url)}})

                            # Forward the data to the Discord webhook
                            try:
                                response = requests.post(DISCORD_WEBHOOK_URL, json=data)
                                response.raise_for_status()
                                logging.info(f"Forwarded with response status: {response.status_code}")
                                return jsonify({'status': 'forwarded', 'response': response.status_code}), response.status_code
                            except requests.RequestException as e:
                                logging.error(f"Error forwarding to Discord webhook: {e}")
                                return jsonify({'status': 'error', 'message': str(e)}), 500

                        # If the first aired date is not within the last week, ignore it
                        else:
                            logging.info("First aired date is not within the last week, ignoring...")
                            return jsonify({'status': 'ignored'}), 200

    # If the data does not match the expected format, ignore it
    logging.info("Ignoring webhook data")
    return jsonify({'status': 'ignored'}), 200

if __name__ == '__main__':
    logging.info(f"Starting webhook listener on port {PORT}...")
    app.run(host=HOST, port=PORT)
