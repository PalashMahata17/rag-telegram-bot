# RAG RSS Feed Summarizer & Telegram Bot

This is a data science project for my NLU (Natural Language Understanding) course. It is a 24/7, fully automated RAG (Retrieval-Augmented Generation) pipeline that:

1.  **Monitors** multiple news RSS feeds.
2.  **Retrieves** new articles as they are published.
3.  **Augments** the data by scraping the full, clean text from each article's URL.
4.  **Generates** a concise summary of the text using a `t5-small` LLM.
5.  **Sends** the final summary directly to a Telegram chat, keeping me updated on the news.

## 🚀 Live Demo

This app is running live on a Hugging Face Space.

[](https://www.google.com/search?q=https://huggingface.co/spaces/Palash112/my-rag-bot)

*(This is the Streamlit frontend. The actual bot runs in a background thread.)*

## ⚙️ Project Architecture (Flowchart)

The entire pipeline runs on a continuous loop, ensuring that new content is fetched and processed as it appears.


graph TD;
    A[Start Loop (every 30 min)] --> B(Get 'Seen Links' from DB);
    B --> C[Loop Through RSS Feeds];
    C --> D{New Article Found?};
    D -- No --> E[End Loop / Wait];
    D -- Yes --> F[Retrieve: Get Article Link];
    F --> G[Augment: Scrape Full Text];
    G --> H{Scraping Successful?};
    H -- No --> C;
    H -- Yes --> I[Generate: Summarize Text (T5-Small)];
    I --> J[Notify: Send to Telegram];
    J --> K[Update 'Seen' List];
    K --> L[Upload New 'Seen Links' to DB];
    L --> C;
```

## 🛠️ Technologies Used

  * **Python 3:** The core language for the project.
  * **Hugging Face `transformers`:** Used to load and run the `t5-small` summarization model.
  * **Streamlit:** Provides the simple, free web UI for the app.
  * **Hugging Face Spaces:** Hosts the Streamlit app 24/7 on a free CPU.
  * **Hugging Face Hub (Datasets):** Used as a free, persistent, file-based database to store the `seen_links.txt` file.
  * **`feedparser`:** The "Retrieval" tool. Parses RSS and Atom feeds.
  * **`trafilatura`:** The "Augmentation" tool. Scrapes and cleans the main article text from HTML.
  * **`requests`:** Used to send the final message to the Telegram Bot API.

-----

## 🔧 Setup and Deployment

Here is how to deploy this project from scratch.

### 1\. Get Telegram Secrets

First, you need two pieces of information from Telegram.

1.  **Bot Token:**
      * Start a chat with `@BotFather` on Telegram.
      * Send the `/newbot` command and follow the instructions.
      * `BotFather` will give you a **`TELEGRAM_BOT_TOKEN`**.
2.  **Chat ID:**
      * Start a chat with `@userinfobot` on Telegram.
      * It will immediately reply with your **`TELEGRAM_CHAT_ID`**.

### 2\. Create the "Database" (HF Dataset)

The app needs a place to remember which articles it has already sent. We use a free Hugging Face Dataset for this.

1.  Go to your Hugging Face profile and click "New Dataset".
2.  Name it `rag-bot-db` (or any name you want).
3.  Make it **Public**.
4.  In this new dataset, create a **new file** named `seen_links.txt`. You can leave this file completely blank. This is critical so the bot's first run doesn't fail.
5.  In your `app.py` file, make sure the `DB_REPO_ID` variable matches your username and dataset name (e.g., `Palash112/rag-bot-db`).

### 3\. Create the App (HF Space)

This is the final step to go live.

1.  Create a **New Space** on Hugging Face.
2.  Give it a name (e.g., `my-rag-bot`).
3.  Select the **Streamlit** SDK.
4.  Select the **"CPU basic - Free"** hardware. This is all we need.
5.  Click "Create Space".
6.  Go to the **"Files"** tab and upload the `app.py` and `requirements.txt` files for this project.

### 4\. Add the Secrets

Your app will restart, but it will fail until you add your secret keys.

1.  In your new Space, go to the **"Settings"** tab.
2.  Scroll down to **"Variables and Secrets"**.
3.  Add the following three secrets:
      * `TELEGRAM_BOT_TOKEN`: (The token you got from `BotFather`).
      * `TELEGRAM_CHAT_ID`: (The ID you got from `@userinfobot`).
      * `HF_TOKEN`: Your personal Hugging Face token (create one in your main settings). It **must** have the **`write`** role so it can update your database.

After you add the last secret, the app will restart, and the bot will be **live**.

-----

## 📜 File Structure

```
.
├── app.py          # The main Streamlit app and all RAG pipeline logic
└── requirements.txt  # The list of Python libraries to install
```

## 🧠 How the Code Works (RAG Pipeline)

The `app.py` script has two main parts:

1.  **The Streamlit UI:**

      * This is the simple webpage that shows the bot's status.
      * It uses `@st.cache_resource` to load the `t5-small` model into memory only once.
      * Its most important job is to **start the background thread**. It checks `st.session_state` to make sure it only starts this thread *one time*.

2.  **The Background Thread (`background_task`)**

      * This function runs in a `while True:` loop and does all the real work.
      * **`run_pipeline()`:**
        1.  **Retrieve (DB):** Calls `get_seen_links()` to download `seen_links.txt` from the Hugging Face Hub using the `hf_hub_download` function.
        2.  **Retrieve (Web):** Loops through the `RSS_URLS` list and uses `feedparser` to get all new articles.
        3.  **Filter:** It compares the article links to the `seen_articles` set.
        4.  **Augment:** If an article is new, it uses `trafilatura` to scrape the full, clean text.
        5.  **Generate:** The full text is passed to the `summarize_text` function, which uses the `t5-small` model to generate a summary.
        6.  **Notify:** The formatted summary is sent to your Telegram using a `requests.post()` call to the Telegram Bot API.
        7.  **Update (DB):** At the end of the run, if new links were added, it calls `update_seen_links()` to upload the new `seen_links.txt` file back to the Hugging Face Hub.
      * **`time.sleep(1800)`:** The bot waits for 30 minutes before starting the loop all over again.

## 👤 Author

  * **Palash Mahata**
