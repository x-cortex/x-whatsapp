import re
import os
import logging as logger
import asyncio
from playwright.async_api import (
    Error,
    async_playwright,
    Playwright,
    BrowserContext,
    Page,
)
from typing import Optional, Callable, Dict, Any, List
import time
import sys

BROWSER_INSTANCE = "chromium"
HEADLESS = False
USER_DATA_DIR = "user_data"
BASE_URL = "https://web.whatsapp.com/"


class WhatsappClient:
    def __init__(self) -> None:
        self.setup_logger()
        logger.info("Starting Playwright...")
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[BrowserContext] = None
        self.page_instance: Optional[Page] = None
        self.sent_messages = []  # TODO: delete

    @property
    def page(self) -> Page:
        assert self.page_instance is not None, "Page has not been initialized."
        return self.page_instance

    def setup_logger(self):
        """Initializes and configures the logger."""
        logger.basicConfig(
            format="%(asctime)s - %(levelname)s - %(message)s",
            level=logger.INFO,
            handlers=[
                logger.FileHandler("whatsapp_client.log"),  # Log to a file
                logger.StreamHandler(),  # Log to console
            ],
        )
        logger.info("Logger initialized.")

    async def initialize_playwright(self):
        self.playwright = await async_playwright().start()
        logger.info(f"Launching {BROWSER_INSTANCE} with persistent context...")
        self.browser = await self.playwright[
            BROWSER_INSTANCE
        ].launch_persistent_context(USER_DATA_DIR, headless=HEADLESS)
        self.page_instance = await self.browser.new_page()
        logger.info(f"{BROWSER_INSTANCE} launched successfully.")

    async def login(self):
        if os.path.exists(USER_DATA_DIR):
            logger.info("User is already logged in. Skipping login step.")
        else:
            logger.info("User not logged in. Redirecting to WhatsApp login page.")

        await self.page.goto(BASE_URL)
        await self.page.bring_to_front()

        logger.info("Waiting for WhatsApp chats to load...")
        await self.page.wait_for_selector(
            '//*[@id="pane-side"]/div[2]/div/div/child::div', timeout=600000
        )
        logger.info("WhatsApp chats loaded.")

    async def logout(self):
        try:
            # Click the menu button -> logout option -> confirm logout
            await self.page.locator(
                'div[role="button"][title="Menu"][aria-label="Menu"][data-tab="2"]'
            ).click(timeout=5000)

            await self.page.locator('div[role="button"][aria-label="Log out"]').click(
                timeout=5000
            )

            await self.page.locator(
                'div:has(h1:text("Log out?")) button:has-text("Log out")'
            ).click(timeout=5000)

            return True
        except TimeoutError as e:
            logger.exception(f"Timeout error during logout: {str(e)}")
        except Exception as e:
            logger.exception(f"Unexpected error during logout: {str(e)}")

        logger.error("Logout failed")
        return False

    def get_search_box_locator(self):
        return self.page.locator(
            "#side div[contenteditable='true'][role='textbox'][data-lexical-editor='true']"
        )

    async def get_focused_element_locator(self):
        """returns None | locator for current focused element"""
        try:
            # Generate a unique selector for the active (focused) element
            selector = await self.page.evaluate(
                """
                () => {
                    const activeElement = document.activeElement;
                    if (!activeElement) return null;
                    
                    // Helper function to generate a unique selector
                    const getSelector = (el) => {
                        if (el.id) {
                            return `#${el.id}`;
                        }
                        if (el === document.body) {
                            return 'body';
                        }
                        let selector = el.tagName.toLowerCase();
                        
                        // Add classes if available
                        if (el.className && typeof el.className === 'string') {
                            const classes = el.className.trim().split(/\\s+/).join('.');
                            selector += `.${classes}`;
                        }
                        
                        // Get the element's position among its siblings
                        const parent = el.parentElement;
                        if (parent) {
                            const siblings = Array.from(parent.children).filter(
                                (child) => child.tagName === el.tagName
                            );
                            if (siblings.length > 1) {
                                const index = siblings.indexOf(el) + 1;
                                selector += `:nth-of-type(${index})`;
                            }
                        }
                        
                        // Recursively build the selector
                        return parent ? `${getSelector(parent)} > ${selector}` : selector;
                    };
                    
                    return getSelector(activeElement);
                }
            """
            )

            if not selector:
                logger.info("No focused element found.")
                return None

            logger.info(f"Generated selector: {selector}")

            locator = self.page.locator(selector)

            # Optionally, verify that the locator actually points to the active element
            is_visible = await locator.is_visible()
            if is_visible:
                return locator
            else:
                logger.info("Locator does not point to a visible element.")
                return None

        except Exception as e:
            logger.exception(f"Error in get_focused_element_locator: {e}")
            return None

    async def clear_text(self):
        """requires you to import sys"""

        if sys.platform == "darwin":
            await self.page.keyboard.press("Meta+A")
            await self.page.keyboard.press("Backspace")
        else:
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")

    async def find_user(self, username: str) -> str | bool:
        """
        Returns str | bool: chat_name if the chat is found, False otherwise.
        """
        try:
            search_box = self.get_search_box_locator()

            await search_box.click()
            await self.clear_text()
            await search_box.type(username)
            await search_box.press("Enter")

            chat_name = await self.page.locator(
                selector='#main header ._amig span[dir="auto"]'
            ).first.inner_text()

            if chat_name and chat_name.upper().startswith(username.upper()):
                logger.info(f'Username with prefix "{username}" found as "{chat_name}"')
                return chat_name
            else:
                logger.info(f'Username with prefix "{username}" not found')
                return False
        except TimeoutError:
            logger.exception(f'It was not possible to fetch chat "{username}"')
            return False

    async def find_user_phone(self, mobile: str) -> None:
        try:
            suffix_link = "https://web.whatsapp.com/send?phone={mobile}&text&type=phone_number&app_absent=1"
            link = suffix_link.format(mobile=mobile)
            await self.page.goto(link)
            await self.page.wait_for_load_state("networkidle")
        except TimeoutError as bug:
            logger.exception(f"An exception occurred: {bug}")
            await self.page.wait_for_timeout(1000)
            await self.find_user_phone(mobile)

    async def openChatPanelUsingName(self, name: str):
        logger.info(f"Opening chat panel for contact: {name}.")
        search_input_selector = (
            "div[contenteditable='true'][role='textbox'][data-lexical-editor='true']"
        )
        await self.page.wait_for_selector(search_input_selector, timeout=60000)
        search_input = await self.page.query_selector(search_input_selector)

        if search_input:
            logger.info(f"Found search input for contact: {name}. Typing contact name.")
            await search_input.click()

            await self.clear_text()

            await search_input.type(name, delay=20)
            await self.page.keyboard.press("Enter")
        else:
            logger.error(f"Search input for contact {name} not found.")

        return search_input

    async def sendMessage(self, name: str, message: str):
        logger.info(f"Sending message to {name}: {message}")
        search_input = await self.openChatPanelUsingName(name)

        if search_input:
            await self.clear_text()
            await self.page.keyboard.type(message, delay=20)
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(100)
            await self.page.keyboard.press("Enter")
        else:
            logger.error(f"Failed to send message to {name}. Search input not found.")

    async def parse_whatsapp_messages(self) -> List[Dict]:
        """
        Parses all the message rows inside the main div of WhatsApp Web and returns
        a list of message objects containing sender, time_sent, and message.

        Args:
            page (Page): The Playwright Page object representing WhatsApp Web.

        Returns:
            List[Dict]: A list of dictionaries, each representing a message with its details.
        """
        messages = []

        # Wait for the main messages container to load
        await self.page.wait_for_selector("#main")

        # Select all message rows
        # TODO: update this to also include divs containg the day information
        rows = await self.page.query_selector_all("#main div[role='row']")

        for row in rows:
            try:
                message_container = await row.query_selector(
                    "div.message-in, div.message-out"
                )
                assert message_container is not None

                # ************************************************************************ #

                message_class = await message_container.get_attribute("class")
                assert message_class is not None

                if "message-out" in message_class:
                    sender = "You"
                else:
                    sender = "Sender"

                # ************************************************************************ #

                temp = await message_container.query_selector(
                    "div._amk6._amlo div.copyable-text"
                )
                assert temp is not None
                data_pre_plain_text = await temp.get_attribute("data-pre-plain-text")
                assert data_pre_plain_text is not None

                # LOGGER.info("Message sent time and sender: ", data_pre_plain_text)

                pattern = r"\[(.*?)\] (.*?):\s*$"
                match = re.match(pattern, data_pre_plain_text)
                if match:
                    time_sent = match.group(1).strip()
                    if sender != "You":
                        sender = match.group(2).strip()

                # ************************************************************************ #

                message_span = await message_container.query_selector(
                    "span.selectable-text.copyable-text"
                )
                if message_span:
                    message_text = await message_span.inner_text()
                    message_text = message_text.strip()

                # ************************************************************************ #

                message = {
                    "sender": sender,
                    "time_sent": time_sent,
                    "message": message_text,
                }

                messages.append(message)

            except Exception as e:
                print(f"Error parsing message row: {e}")
                continue

        return messages

    async def getChatHistory(self, n: int):
        logger.info(f"Fetching chat history for the last {n} messages.")
        selector = "div[role='application']"
        mainDiv = await self.page.wait_for_selector(selector)
        await asyncio.sleep(1)
        if not mainDiv:
            logger.error("Error in opening Chat Panel.")
            raise Error("Error in opening Chat Panel....")

        chats = await mainDiv.query_selector_all("div[role='row']")
        if not chats:
            logger.error("Error in fetching chats.")
            raise Error("Error in fetching chats....")

        formattedChats = []
        if len(chats) >= n:
            chats.reverse()
            chats = chats[:n]
            for chat in chats:
                copyText = await chat.query_selector(".copyable-text")
                if not copyText:
                    continue

                prePlainText = await copyText.get_attribute("data-pre-plain-text")
                message = await chat.query_selector(".copyable-text span")

                if not message or not prePlainText:
                    continue
                messageText = await message.inner_text()

                # Use regex to extract the name and time from data-pre-plain-text
                match = re.search(r"\[(.*?)\] (.*?): ", prePlainText)
                if match:
                    t = match.group(1)  # Extracted time
                    name = match.group(2)  # Extracted name

                    # Append the extracted data to the messages list
                    formattedChats.append(
                        {"name": name, "time": t, "message": messageText}
                    )
        logger.info(f"Fetched chat history: {formattedChats}")
        return formattedChats

    async def getChatHistoryByName(self, n: int, name: str):
        logger.info(f"Fetching chat history for {name} (last {n} messages).")
        await self.openChatPanelUsingName(name)
        return await self.getChatHistory(n)
