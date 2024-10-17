"""
Playwright based WhatsApp client to interact with x-cortex.
"""

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
from pathlib import Path
import time
import sys

# <---------------------------------------------------->#

BROWSER_INSTANCE = "chromium"
HEADLESS = False
USER_DATA_DIR = "user_data"
BASE_URL = "https://web.whatsapp.com/"


class WhatsappClient:
    def __init__(self) -> None:
        # Optionally we could initialize user constants (eg. phone number, x-cortex name etc.)
        # Haven't decided if we should do this or not
        self.setup_logger()
        logger.info("Starting Playwright...")
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[BrowserContext] = None
        self.page_instance: Optional[Page] = None

    @property
    def page(self) -> Page:
        # Alternatively: assert self.page is not None in every function that uses page
        assert self.page_instance is not None, "Page has not been initialized."
        return self.page_instance

    # currently not used
    @property
    def browser_options(self):
        options = {}
        if sys.platform == "win32":
            options["args"] = ["--profile-directory=Default"]
            options["user_data_dir"] = "C:/Temp/ChromeProfile"
        options["args"] = ["--start-maximized"]
        return options

    # currently not used
    @property
    def context_options(self):
        options = {}
        if sys.platform != "win32":
            options["viewport"] = None
        return options

    def setup_logger(self):
        """Initializes and configures the logger."""
        # TODO: can a better logger be made?
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
        await self.page_instance.set_viewport_size({"width": 1920, "height": 1080})
        logger.info(f"{BROWSER_INSTANCE} launched successfully.")

    async def login(self):
        # TODO: QR code & phone number login via script
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

    async def clear_text(self):
        if sys.platform == "darwin":
            await self.page.keyboard.press("Meta+A")
            await self.page.keyboard.press("Backspace")
        else:
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")

    async def search_pane_scroll_down(self):
        """
        Scrolls down the search pane (div with id="pane-side") by moving the mouse cursor
        to the center of the pane and performing rapid scroll wheel actions to load all chats.
        """
        scroll_selector = "#pane-side"
        try:
            pane = self.page.locator(scroll_selector)
            bounding_box = await pane.bounding_box()
            if not bounding_box:
                logger.error("Could not locate the search pane for scrolling.")
                return

            center_x = bounding_box["x"] + bounding_box["width"] / 2
            center_y = bounding_box["y"] + bounding_box["height"] / 2

            previous_height = await pane.evaluate("element => element.scrollHeight")
            logger.info(
                "Starting to scroll down the search pane to load all chats by rapid mouse scrolling."
            )

            while True:
                await self.page.mouse.move(center_x, center_y)
                await self.page.mouse.wheel(0, 1000)  # Increased scroll down delta
                await asyncio.sleep(0.1)  # Reduced sleep time for faster scrolling

                current_height = await pane.evaluate("element => element.scrollHeight")
                if current_height == previous_height:
                    logger.info(
                        "Reached the bottom of the search pane. All chats are loaded."
                    )
                    break
                previous_height = current_height

        except Exception as e:
            logger.exception(
                f"Error while scrolling down the search pane using mouse: {e}"
            )

    async def chat_pane_scroll_up(self):
        """
        Scrolls up the chat pane (div with id="main") by moving the mouse cursor
        to the center of the pane and performing rapid scroll wheel actions to reach the top.
        """
        scroll_selector = "#main"
        try:
            pane = self.page.locator(scroll_selector)
            bounding_box = await pane.bounding_box()
            if not bounding_box:
                logger.error("Could not locate the chat pane for scrolling.")
                return

            center_x = bounding_box["x"] + bounding_box["width"] / 2
            center_y = bounding_box["y"] + bounding_box["height"] / 2

            previous_scroll_top = await pane.evaluate("element => element.scrollTop")
            logger.info(
                "Starting to scroll up the chat pane to reach the top by rapid mouse scrolling."
            )

            while True:
                await self.page.mouse.move(center_x, center_y)
                await self.page.mouse.wheel(0, -1000)  # Increased scroll up delta
                await asyncio.sleep(0.1)  # Reduced sleep time for faster scrolling

                current_scroll_top = await pane.evaluate("element => element.scrollTop")
                if current_scroll_top == previous_scroll_top:
                    logger.info("Reached the top of the chat pane.")
                    break
                previous_scroll_top = current_scroll_top

        except Exception as e:
            logger.exception(f"Error while scrolling up the chat pane using mouse: {e}")

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

    async def find_user(self, username: str) -> str | bool:
        """
        Returns str | bool: chat_name if the chat is found, False otherwise.

        TODO:
            - find the user without opening the chat panel
            - right now this function is same as openChatPanelUsingName
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

    async def openChatPanelUsingName(self, username: str):
        try:
            search_box = self.get_search_box_locator()

            await search_box.click()
            await self.clear_text()
            await search_box.type(username)
            await search_box.press("Enter")

            chat_name = await self.page.locator(
                selector='#main header ._amig span[dir="auto"]'
            ).first.inner_text()

            if chat_name:
                logger.info(f'Opened the chat panel of "{chat_name}"')
                return chat_name
            else:
                logger.info(f'Username with prefix "{username}" not found')
                return False
        except TimeoutError:
            logger.exception(f'It was not possible to fetch chat "{username}"')
            return False

    async def sendMessage(self, name: str, message: str):
        search_input = await self.openChatPanelUsingName(name)

        if search_input:
            await self.clear_text()
            await self.page.keyboard.type(message, delay=20)
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(100)
            await self.page.keyboard.press("Enter")

            logger.info(f"Sending message to {search_input}: {message}")
        else:
            logger.error(f"Failed to send message to {name}. Search input not found.")

    async def extract_basic_info(self, row) -> Dict:
        """
        Parses a single message row inside the main div of WhatsApp Web and returns
        a dictionary containing sender, time_sent, and message.

        TODO:
            - get additional information such as
            - forwarded = True | False
            - replying to = False | Replying message details
            - simplify the code & wrap it in a try catch block
        """

        obj = {"message": "unknown", "time": "unknown", "sender": "unknown"}

        # Extract message content
        message_span = await row.query_selector("span.selectable-text.copyable-text")
        if message_span:
            obj["message"] = (await message_span.inner_text()).strip()

        # Extract sender and time sent
        temp = await row.query_selector("div._amk6._amlo div.copyable-text")
        if temp:
            data_pre_plain_text = await temp.get_attribute("data-pre-plain-text")
            pattern = r"\[(.*?)\] (.*?):\s*$"
            match = re.match(pattern, data_pre_plain_text)
            if match:
                obj["time"] = match.group(1).strip()
                obj["sender"] = match.group(2).strip()
        else:
            sender_span = await row.query_selector("span._ahxt.x1ypdohk.xt0b8zv._ao3e")
            if sender_span:
                obj["sender"] = (await sender_span.inner_text()).strip()

            time_span = await row.query_selector("span.x1rg5ohu.x16dsc37")
            if time_span:
                obj["time"] = (await time_span.inner_text()).strip()

        # Update sender for sent messages
        sending = await row.query_selector("div.message-out")
        if sending:
            obj["sender"] = "You"
        elif obj["sender"] == "unknown":
            obj["sender"] = "Sender"

        return obj

    async def extract_attachment_details(self, row: Page) -> Dict:
        """
        TODO:
            - fix everything
            - maybe split into multiple functions for images, PDFs, etc.

        TODO: Parse and account for different types of attachment types such as
        - images
        - PDFs
        - Others

        currently only works for pdfs and tht too barely
        """

        attachment_details = {}

        attachment_div = await row.query_selector('div[title^="Download"]')
        if attachment_div:
            attachment_name_span = await attachment_div.query_selector(
                "span.selectable-text"
            )
            attachment_name = (
                (await attachment_name_span.inner_text())
                if attachment_name_span
                else None
            )
            attachment_details["name"] = attachment_name

            # Extract attachment type
            attachment_type_span = await row.query_selector(
                'span[title="PDF"], span[title="Image"], span[title="Document"]'
            )
            attachment_type = (
                (await attachment_type_span.get_attribute("title"))
                if attachment_type_span
                else None
            )
            attachment_details["type"] = attachment_type

            # Extract attachment size
            size_span = await row.query_selector('span[title*="kB"], span[title*="MB"]')
            size = (await size_span.get_attribute("title")) if size_span else None
            attachment_details["size"] = size

            # Extract other details (e.g., number of pages)
            pages_span = await row.query_selector('span[title*="pages"]')
            other_details = (
                (await pages_span.get_attribute("title")) if pages_span else None
            )
            attachment_details["otherdetails"] = other_details

        return attachment_details

    async def extract_messages(self) -> List[Dict]:
        """
        Parses all the message rows inside the main div of WhatsApp Web and returns
        a list of message objects containing sender, time_sent, and message.
        """

        # TODO: parse different row types to different functions
        # ie. text, attachment, etc.

        messages = []

        # Wait for the main messages container to load
        await self.page.wait_for_selector("#main")

        # Select all message rows
        # TODO: update this to also include divs containg the day information
        rows = await self.page.query_selector_all("#main div[role='row']")

        async def process_row(row):
            try:
                obj = await self.extract_basic_info(row)
                has_attachment = await row.query_selector(
                    "div.icon-doc-pdf, div.icon-doc-img, div.icon-doc-video, div.icon-audio-download"
                )
                if has_attachment:
                    obj["attachment_details"] = await self.extract_attachment_details(
                        row
                    )
                else:
                    obj["attachment_details"] = ""

                return obj

            except Exception as e:
                print(f"Error parsing message row: {e}")
                return None

        tasks = [process_row(row) for row in rows]
        results = await asyncio.gather(*tasks)
        messages.extend(filter(None, results))

        return messages

    async def getChatHistoryByName(self, n: int, name: str):
        logger.info(f"Fetching chat history for {name} (last {n} messages).")
        await self.openChatPanelUsingName(name)
        return (await self.extract_messages())[-n:]
