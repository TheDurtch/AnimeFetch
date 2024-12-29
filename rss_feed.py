import sys
import feedparser
import subprocess
import os
import json
import time
import re
from datetime import datetime, timedelta
import requests

# Configuration file with the list of desired torrents and their corresponding URIs
config_file = "conf/rss.conf"

# Directory to save downloaded files
download_dir = ""

# Completed directory
completed_dir = ""

# File to record hashes of downloaded torrents
hash_file = "downloaded_torrents.db"

lock_file = "rss_feed.lock"
max_lock_age = 3600

# Discord Webhook URL for sending notifications
webhook_url = ""

def send_discord_message(message):
    """Send a message to Discord with a 2000 character limit."""
    max_length = 2000  # Discord's message character limit

    # Split the message into chunks if it's too long
    if len(message) > max_length:
        # Split message into chunks of max_length
        for i in range(0, len(message), max_length):
            chunk = message[i:i+max_length]
            data = {"content": chunk}
            response = requests.post(webhook_url, json=data)
            if response.status_code != 204:
                print(f"Failed to send chunk to Discord: {response.status_code}, {response.text}")
    else:
        data = {"content": message}
        response = requests.post(webhook_url, json=data)
        if response.status_code != 204:
            print(f"Failed to send message to Discord: {response.status_code}, {response.text}")


def clean_filename(filename):
    return re.sub(r'(\d{2})v2', r'\1', filename, flags=re.IGNORECASE)


def send_discord_code_block(code_output):
    """Send a long code block output to Discord in chunks, within 2000 character limit."""
    max_length = 1990  # To account for the triple backticks
    code_chunks = [code_output[i:i+max_length] for i in range(0, len(code_output), max_length)]

    for chunk in code_chunks:
        send_discord_message(f"```{chunk}```")
def download_torrent(info_hash, title, no_seed):
    print(f"no_seed: {no_seed}")
    magnet_link = f"magnet:?xt=urn:btih:{info_hash}"
    tracker_url = "http://nyaa.tracker.wf:7777/announce"
    magnet_link_with_tracker = f"{magnet_link}&tr={tracker_url}"
    try:
        # Build the aria2c command with optional --no-seed
        aria2c_command = ["aria2c", "--listen-port=60000-65535", "--bt-prioritize-piece=head,tail", "--bt-max-peers=1024", "--file-allocation=falloc",  "--seed-ratio=15", "--dir", download_dir, magnet_link_with_tracker]
        if no_seed:
            aria2c_command.append("--seed-time=0")
        else:
            aria2c_command.append("--seed-time=15")
        print("Aria2c command:", aria2c_command)
        send_discord_message(f"Started Download for {title}\n ```Aria2c command: {aria2c_command}```")
        # Use aria2c to download the torrent and capture output
        subprocess.run(aria2c_command, check=True)

        # Record the info hash and the current timestamp
        with open(hash_file, "a") as file:
            file.write(info_hash + '|' + datetime.now().isoformat() + "\n")

        # Process and move files
        for file in os.listdir(download_dir):
            file_path = os.path.join(download_dir, file)
            if os.path.isfile(file_path):
                # Attempt to extract English subtitles using mkvmerge
                json_data = subprocess.run(["mkvmerge", "-J", file_path], capture_output=True, text=True).stdout
                subtitle_tracks = subprocess.run(
                    ["jq", "-r", '.tracks[] | select(.type == "subtitles" and .properties.language == "eng") | .id'],
                    input=json_data, capture_output=True, text=True
                ).stdout.strip()

                if subtitle_tracks:
                    output_file = os.path.join(completed_dir, clean_filename(file))
                    result = subprocess.run(
                        ["mkvmerge", "-o", output_file, "--audio-tracks", "1", "--subtitle-tracks", subtitle_tracks, file_path]
                    )

                    # Clean up the original file if muxing was successful
                    if result.returncode == 0:
                        os.remove(file_path)
                        print(f"Muxing successful. {file} has been cleaned up.")
                    else:
                        print(f"Muxing failed. Moving the original file: {file}.")
                        new_file_path = os.path.join(completed_dir, clean_filename(file))
                        os.rename(file_path, new_file_path)

                else:
                    print("No English subtitle track found. Moving the file as is.")
                    new_file_path = os.path.join(completed_dir, clean_filename(file))
                    os.rename(file_path, new_file_path)

        # Send a completion Discord message
        send_discord_message(f"Download completed for {title}")
        print("\n")
    except subprocess.CalledProcessError:
        # Send an error Discord message
        send_discord_message(f"Error downloading {title}")
        print("\n")

def already_downloaded(info_hash):
    if os.path.exists(hash_file):
        with open(hash_file, "r") as file:
            for line in file:
                parts = line.strip().split('|')
                if len(parts) == 2 and parts[0] == info_hash:
                    return True
    return False

def cleanup_old_hashes(days_old=180):
    if not os.path.exists(hash_file):
        return

    threshold_date = datetime.now() - timedelta(days=days_old)

    with open(hash_file, "r") as file:
        lines = file.readlines()

    with open(hash_file, "w") as file:
        for line in lines:
            if '|' not in line.strip():
                # Remove lines that don't contain the delimiter or are blank
                print("Removing invalid line:", line.strip())
                continue
            try:
                hash, timestamp = line.strip().split('|')
                hash_date = datetime.fromisoformat(timestamp)
                if hash_date >= threshold_date:
                    file.write(line)
            except ValueError as e:
                print("Error processing line:", line.strip())
                print("Exception:", e)
                # Optionally remove the problematic line as well
                print("Removing problematic line:", line.strip())

def check_feed(feed_url, desired_torrents, no_seed):
    feed = feedparser.parse(feed_url)
    for entry in feed.entries:
        title = entry.title
        info_hash = None

        # Extract info hash depending on the feed source
        if 'nyaa_infohash' in entry:
            info_hash = entry.get('nyaa_infohash')
        elif 'erai_infohash' in entry:
            info_hash = entry.get('erai_infohash')

        # Skip if the title ends with ".5" (indicating a recap or special episode)
        if ".5" in title.split()[-1]:
            continue

        if any(desired_title in title for desired_title in desired_torrents):
            if info_hash and not already_downloaded(info_hash):
                print(f"Calling download_torrent with no_seed={no_seed}")
                download_torrent(info_hash, title, no_seed=no_seed)


def is_lock_file_stale(lock_file_path, max_age):
    """Check if the lock file is older than the max_age."""
    if os.path.exists(lock_file_path):
        file_age = time.time() - os.path.getmtime(lock_file_path)
        if file_age > max_age:
            return True
    return False

if __name__ == "__main__":
    no_seed = "--no-seed" in sys.argv
    print(f"no_seed: {no_seed} - {sys.argv}")
    # Check if the lock file exists and is not stale
    if os.path.exists(lock_file) and not is_lock_file_stale(lock_file, max_lock_age):
        print("Script is already running or the lock file is stale.")
        exit()

    # Create or update the lock file
    with open(lock_file, 'w') as file:
        file.write("locked")

    try:
        cleanup_old_hashes()
        config = {}
        with open(config_file, 'r') as file:
            config = json.load(file)
        for feed_url, torrents in config.items():
            check_feed(feed_url, torrents, no_seed=no_seed)  # Set no_seed to True or False as needed

    finally:
        # Remove the lock file
        if os.path.exists(lock_file):
            os.remove(lock_file)
