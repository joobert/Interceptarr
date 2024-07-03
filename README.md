<h1 align="center">
  Interceptarr
</h1>

<p align="center">
  <img width="192" height="180" src="https://i.imgur.com/EnrnpKp.png">
</p>

**Interceptarr** is a simple Flask-based web application specifically designed to send notifications for new episodes of continuing series in Sonarr. This is done by fetching "On Import" webhooks from Sonarr and forwarding them to a user-defined Discord webhook URL. The script listens for webhooks from Sonarr, processes the data, and if the release date of the episode is less than a week old, it forwards the message to the specified Discord webhook.

## Features

- Listens for webhook events from Sonarr and processes incoming data.
- Fetches and parses data from TVDB to extract episode air dates.
- Forwards processed data to a Discord webhook if the episode is less than a week old.
- Logs all events and errors to `interceptarr_logs.txt`.

## Prerequisites

- Python 3.7+
- `requests` library
- `beautifulsoup4` library
- `python-dotenv` library

## Configuration

Create a '**.env**' file in the same directory as the script with the following variables:
- **DISCORD_WEBHOOK_URL**: The Discord webhook URL where notifications will be sent.
- **SHOW_EPISODE_THUMBNAIL**: Optionally replace the generic show thumbnail with the episode thumbnail.
- **WEBHOOK_HOST**: The IP address or hostname the Flask app will bind to.
- **WEBHOOK_PORT**: The port the Flask app will listen on.

## Sonarr Configuration

To integrate Interceptarr with Sonarr, create a new connection in Sonarr with only the "On Import" notification trigger checked, and set the connection's webhook URL to point to the IP address and port where Interceptarr is running with `/webhook` appended to the end. (e.g., '**http://10.0.0.1:8700/webhook**')

### Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/joobert/interceptarr.git
    cd interceptarr
    ```

2. Install dependencies:
    ```sh
    pip install -r requirements.txt
    ```

3. Create a `.env` file with the following content:
    ```env
    DISCORD_WEBHOOK_URL=your_webhook_url
    SHOW_EPISODE_THUMBNAIL=False
    WEBHOOK_HOST=your_host_ip
    WEBHOOK_PORT=8700
    ```

4. Run the application:
    ```sh
    python interceptarr.py
    ```

### (Optional) Running with Docker

###### Ensure you have both Docker and Docker Compose installed on your machine.

1. Clone the repository:
    ```sh
    git clone https://github.com/joobert/interceptarr.git
    cd interceptarr
    ```

2. Create a `.env` file with the following content:
    ```env
    DISCORD_WEBHOOK_URL=your_webhook_url
    SHOW_EPISODE_THUMBNAIL=False
    WEBHOOK_HOST=your_host_ip
    WEBHOOK_PORT=8700
    ```

3. Ensure that the port configurations in both the `compose.yml` and `Dockerfile` match the port specified in your `.env` file (`WEBHOOK_PORT`). By default, it should be set to `8700`. Adjust the port settings in these files if necessary.  

4. Create an empty `interceptarr_logs.txt` file:
    ```sh
    touch interceptarr_logs.txt
    ```

5. Start the service with Docker Compose:
    ```sh
    docker-compose up -d
    ```

## Usage

Once the script or container is running, the application will be listening for webhook events on the specified IP address and port.

- **Webhook Listener**: The application listens for POST requests at the endpoint (`/webhook`) and processes incoming webhook data.
- **Logging**: All events and errors are logged to `interceptarr_logs.txt`.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request or open an Issue.

## License

[MIT](https://choosealicense.com/licenses/mit/)
