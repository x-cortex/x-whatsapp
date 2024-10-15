import re
import os
import logging
from playwright.sync_api import Error, sync_playwright
import time

BROWSER_INSTANCE = "chromium"
HEADLESS = False
USER_DATA_DIR = "user_data"


class WhatsappClient:
    def __init__(self) -> None:
        self.setup_logger()
        logging.info("Starting Playwright...")
        self.playwright = sync_playwright().start()
        self.sent_messages = []

        logging.info(f"Launching {BROWSER_INSTANCE} with persistent context...")
        self.browser = self.playwright[BROWSER_INSTANCE].launch_persistent_context(
            USER_DATA_DIR, headless=HEADLESS
        )
        self.page = self.browser.new_page()
        logging.info(f"{BROWSER_INSTANCE} launched successfully.")

    def setup_logger(self):
        """Initializes and configures the logger."""
        logging.basicConfig(
            format="%(asctime)s - %(levelname)s - %(message)s",
            level=logging.INFO,
            handlers=[
                logging.FileHandler("whatsapp_client.log"),  # Log to a file
                logging.StreamHandler(),  # Log to console
            ],
        )
        logging.info("Logger initialized.")

    def login(self):
        if os.path.exists(USER_DATA_DIR):
            logging.info("User is already logged in. Skipping login step.")
        else:
            logging.info("User not logged in. Redirecting to WhatsApp login page.")

        self.page.goto("https://web.whatsapp.com")

        logging.info("Waiting for WhatsApp chats to load...")
        self.page.wait_for_selector(
            '//*[@id="pane-side"]/div[2]/div/div/child::div', timeout=60000
        )
        logging.info("WhatsApp chats loaded.")

    def clearScreen(self):
        logging.info("Clearing the screen (Ctrl+A, Backspace).")
        self.page.keyboard.down("Control")
        self.page.keyboard.press("A")
        self.page.keyboard.up("Control")
        self.page.keyboard.press("Backspace")

    def openChatPanelUsingName(self, name: str):
        logging.info(f"Opening chat panel for contact: {name}.")
        search_input_selector = (
            "div[contenteditable='true'][role='textbox'][data-lexical-editor='true']"
        )
        self.page.wait_for_selector(search_input_selector, timeout=60000)
        search_input = self.page.query_selector(search_input_selector)

        if search_input:
            logging.info(
                f"Found search input for contact: {name}. Typing contact name."
            )
            search_input.click()

            self.clearScreen()

            search_input.type(name, delay=20)
            self.page.keyboard.press("Enter")
        else:
            logging.error(f"Search input for contact {name} not found.")

        return search_input

    def sendMessage(self, name: str, message: str):
        logging.info(f"Sending message to {name}: {message}")
        page = self.page
        search_input = self.openChatPanelUsingName(name)

        if search_input:
            self.clearScreen()

            page.keyboard.type(message, delay=20)
            page.keyboard.press("Enter")
            page.wait_for_timeout(100)
            page.keyboard.press("Enter")

            page.wait_for_timeout(200)
            if len(self.sent_messages) >= 20:
                self.sent_messages.pop(0)
            self.sent_messages.append(message)
            logging.info(f"Message sent to {name}: {message}")
        else:
            logging.error(f"Failed to send message to {name}. Search input not found.")

    def extract_message_details(self, message):
        logging.info("Extracting message details.")
        name_element = message.query_selector("div._ak8q > div > span")
        name = name_element.inner_text() if name_element else "N/A"
        logging.info(f"Extracted name: {name}")

        time_element = message.query_selector("div._ak8i")
        time = time_element.inner_text() if time_element else "N/A"
        logging.info(f"Extracted time: {time}")

        message_element = message.query_selector("div._ak8k > span > span")
        message_text = message_element.inner_text() if message_element else "N/A"
        logging.info(f"Extracted message: {message_text}")

        return {"name": name, "time": time, "message": message_text}

    def fetchLatestMessage(self):
        logging.info("Fetching the latest message.")
        selector = '//*[@id="pane-side"]/div[2]/div/div/child::div'
        page = self.page
        page.wait_for_selector(selector)
        list_items = page.query_selector_all(selector)

        for item in list_items:
            transform = item.evaluate(
                "element => window.getComputedStyle(element).transform"
            )

            if transform:
                if "matrix" in transform:
                    parts = (
                        transform.replace("matrix(", "").replace(")", "").split(", ")
                    )
                    if len(parts) == 6:
                        translate_y = float(parts[5])
                        if translate_y == 0:
                            logging.info("Found latest message.")
                            return self.extract_message_details(item)
                elif "translateY(0px)" in transform:
                    logging.info("Div with translateY(0px) found.")
                    return self.extract_message_details(item)

        logging.info("Desired div not found.")
        return None

    def onNewMessage(self, callbackFunction):
        logging.info("Starting to listen for new messages.")
        new_message = self.fetchLatestMessage()
        assert new_message is not None

        name = new_message.get("name", None)

        iteration_count = 0

        while True:
            try:
                # Check for new WhatsApp messages
                new_message = self.fetchLatestMessage()
                if new_message:
                    if not (
                        (
                            new_message.get("message") in self.sent_messages
                            or new_message.get("message") == "N/A"
                        )
                        and new_message.get("name", None) == name
                    ):
                        name = new_message.get("name", None)
                        messages = self.getChatHistory(10)
                        logging.info(f"New message received: {messages}")
                        callbackFunction(new_message)

                iteration_count += 1
            except Exception as e:
                logging.error(f"Error while fetching messages: {e}")

            self.page.wait_for_timeout(1000)

    def getChatHistory(self, n: int):
        logging.info(f"Fetching chat history for the last {n} messages.")
        selector = "div[role='application']"
        mainDiv = self.page.wait_for_selector(selector)
        time.sleep(1)
        if not mainDiv:
            logging.error("Error in opening Chat Panel.")
            raise Error("Error in opening Chat Panel....")

        chats = mainDiv.query_selector_all("div[role='row']")
        if not chats:
            logging.error("Error in fetching chats.")
            raise Error("Error in fetching chats....")

        formattedChats = []
        if len(chats) >= n:
            chats.reverse()
            chats = chats[:n]
            for chat in chats:
                copyText = chat.query_selector(".copyable-text")
                if not copyText:
                    continue

                prePlainText = copyText.get_attribute("data-pre-plain-text")
                message = chat.query_selector(".copyable-text span")

                if not message or not prePlainText:
                    continue
                messageText = message.inner_text()

                # Use regex to extract the name and time from data-pre-plain-text
                match = re.search(r"\[(.*?)\] (.*?): ", prePlainText)
                if match:
                    t = match.group(1)  # Extracted time
                    name = match.group(2)  # Extracted name

                    # Append the extracted data to the messages list
                    formattedChats.append(
                        {"name": name, "time": t, "message": messageText}
                    )
        logging.info(f"Fetched chat history: {formattedChats}")
        return formattedChats

    def getChatHistoryByName(self, n: int, name: str):
        logging.info(f"Fetching chat history for {name} (last {n} messages).")
        self.openChatPanelUsingName(name)
        selector = "div[role='application']"
        mainDiv = self.page.wait_for_selector(selector)
        time.sleep(1)
        if not mainDiv:
            logging.error(f"Error in opening Chat Panel for {name}.")
            raise Error("Error in opening Chat Panel....")

        chats = mainDiv.query_selector_all("div[role='row']")
        if not chats:
            logging.error(f"Error in fetching chats for {name}.")
            raise Error("Error in fetching chats....")

        formattedChats = []
        if len(chats) >= n:
            chats.reverse()
            chats = chats[:n]
            for chat in chats:
                copyText = chat.query_selector(".copyable-text")
                if not copyText:
                    continue

                prePlainText = copyText.get_attribute("data-pre-plain-text")
                message = chat.query_selector(".copyable-text span")

                if not message or not prePlainText:
                    continue
                messageText = message.inner_text()

                match = re.search(r"\[(.*?)\] (.*?): ", prePlainText)
                if match:
                    t = match.group(1)  # Extracted time
                    name = match.group(2)  # Extracted name

                    formattedChats.append(
                        {"name": name, "time": t, "message": messageText}
                    )
        logging.info(f"Fetched chat history for {name}: {formattedChats}")
        return formattedChats

    def persist(self):
        logging.info("Browser is persisting (open indefinitely).")
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            logging.info("Shutting down client.")
            self.page.close()
            self.browser.close()
            self.playwright.stop()
