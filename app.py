# app.py
# This is our permanent, 24/7 deployment script

import streamlit as st
import feedparser
import trafilatura
import requests
import time
from transformers import T5ForConditionalGeneration, T5Tokenizer
import torch
import threading  # <-- NEW: For running in the background
from huggingface_hub import HfApi, HfFolder, hf_hub_download, upload_file
import os

# ==============================================================================
#  LOAD SECRETS FROM HUGGING FACE (NOT from code)
# ==============================================================================
# This is the secure, professional way to handle tokens
# We will add these in the Hugging Face Space settings
TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")
HF_TOKEN = st.secrets.get("HF_TOKEN")  # A Hugging Face token with "write" access

# ==============================================================================
#  SETTINGS
# ==============================================================================
RSS_URLS = [
    "https://www.news18.com/rss/india.xml",
    "https://feeds.feedburner.com/NDTV-Latest",
    "https://www.hindustantimes.com/feeds/rss/latest-news/rssfeed.xml",
    "https://www.thehindu.com/news/national/?service=rss"
]

# Settings for our persistent database (on Hugging Face Hub)
# IMPORTANT: You must create a public dataset repo on Hugging Face
# and call it "rag-bot-db" or change this name.
DB_REPO_ID = "YOUR_USERNAME/rag-bot-db"  # <-- CHANGE THIS
DB_FILENAME = "seen_links.txt"

# ==============================================================================
#  LOAD MODEL (This runs only once)
# ==============================================================================
@st.cache_resource
def load_model_and_tokenizer():
    print("Loading summarization model (t5-small)...")
    model_name = "t5-small"
    tokenizer = T5Tokenizer.from_pretrained(model_name)
    model = T5ForConditionalGeneration.from_pretrained(model_name)
    print("Model loaded!")
    return model, tokenizer

model, tokenizer = load_model_and_tokenizer()

# ==============================================================================
#  HELPER FUNCTIONS (Scrape, Summarize, Send)
# ==============================================================================
def scrape_article_text(url):
    print(f"...Scraping text from: {url}")
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            return trafilatura.extract(downloaded)
    except Exception as e:
        print(f"Error scraping {url}: {e}")
    return None

def summarize_text(text):
    if not text:
        return "Could not generate summary (no text)."
    print("...Summarizing text...")
    prompt = "summarize: " + text
    inputs = tokenizer.encode(prompt, return_tensors="pt", max_length=512, truncation=True)
    summary_ids = model.generate(inputs, max_length=150, min_length=40, length_penalty=2.0, num_beams=4, early_stopping=True)
    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    print("...Summary complete.")
    return summary

def send_telegram_message(message):
    print("...Sending message to Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("...Message sent successfully!")
        else:
            print(f"...Error sending message: {response.json()}")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

# ==============================================================================
#  DATABASE FUNCTIONS (Our new "memory")
# ==============================================================================
def get_seen_links():
    """Downloads the list of seen links from our HF Dataset repo."""
    print("...Downloading seen links database...")
    try:
        # Download the file from the Hub
        local_path = hf_hub_download(
            repo_id=DB_REPO_ID,
            filename=DB_FILENAME,
            repo_type="dataset",
            token=HF_TOKEN
        )
        with open(local_path, 'r') as f:
            # Read all lines into a set for fast lookup
            links = set(line.strip() for line in f)
        print(f"...Loaded {len(links)} seen links.")
        return links
    except Exception as e:
        # If the file doesn't exist yet, just return an empty set
        print(f"Warning: Could not download seen links: {e}. Starting fresh.")
        return set()

def update_seen_links(seen_links):
    """Uploads the updated list of links back to the HF Dataset repo."""
    print(f"...Uploading {len(seen_links)} seen links to database...")
    try:
        # Write the set back to a local file
        with open(DB_FILENAME, 'w') as f:
            for link in seen_links:
                f.write(f"{link}\n")

        # Upload the file to the Hub
        upload_file(
            path_or_fileobj=DB_FILENAME,
            path_in_repo=DB_FILENAME,
            repo_id=DB_REPO_ID,
            repo_type="dataset",
            token=HF_TOKEN,
            commit_message="Update seen links"
        )
        print("...Database updated.")
    except Exception as e:
        print(f"Error uploading seen links: {e}")

# ==============================================================================
#  THE MAIN PIPELINE (This will run in the background)
# ==============================================================================
def run_pipeline():
    # 1. Get our "memory" from the database
    seen_articles = get_seen_links()

    print(f"\n--- {time.ctime()} ---")
    print("BOT IS RUNNING. Checking all feeds...")

    new_links_added = False
    for url in RSS_URLS:
        print(f"Checking RSS feed: {url}")
        feed = feedparser.parse(url)

        for entry in reversed(feed.entries):
            article_link = entry.link

            if article_link not in seen_articles:
                print(f"\nNEW Article Found: {entry.title}")
                full_text = scrape_article_text(article_link)

                if full_text:
                    summary = summarize_text(full_text)
                    message_to_send = f"""
🆕 *New Article Summary*
*Source:* {feed.feed.title}
*Title:* {entry.title}
*Summary:*
{summary}
*Link:* {article_link}
                    """
                    send_telegram_message(message_to_send)

                    # Add to our local set
                    seen_articles.add(article_link)
                    new_links_added = True
                else:
                    print("...Skipping article, couldn't get text.")

                # Only process one new article per feed to avoid spamming
                break

    # 2. If we added new links, update our "memory" in the database
    if new_links_added:
        update_seen_links(seen_articles)
    else:
        print("No new articles found this cycle.")

def background_task():
    """This function runs our pipeline in a loop forever."""
    print("Background thread started. Bot is now running.")
    while True:
        try:
            run_pipeline()
            # Wait for 30 minutes
            print(f"\n--- Waiting for 30 minutes... ---")
            time.sleep(1800)
        except Exception as e:
            print(f"Error in main loop: {e}. Restarting in 60s.")
            time.sleep(60)

# ==============================================================================
#  STREAMLIT APP (The "Dummy" UI)
# ==============================================================================
st.title("🤖 RAG Telegram Bot")
st.write("This bot is running 24/7 in the background.")
st.success("The pipeline is active and checking for new articles every 30 minutes.")

st.header("Feeds Being Monitored:")
for url in RSS_URLS:
    st.write(f"- `{url}`")

# --- THIS IS THE MAGIC ---
# Check if the background thread is already running
# We use st.session_state to remember
if "bot_thread" not in st.session_state:
    print("Starting background bot thread...")
    # Create and start the new thread
    thread = threading.Thread(target=background_task, daemon=True)
    thread.start()
    st.session_state.bot_thread = thread
