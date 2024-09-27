"""
Playwright based WhatsApp client to interact with your Exocortex.
"""

import sys
import logging
from typing import Optional
from pathlib import Path
from playwright.async_api import async_playwright

LOGGER = logging.getLogger()

# <---------------------------------------------------->#


class WhatsApp(object):

    def __init__(self):
        self.BASE_URL = "https://web.whatsapp.com/"
        self.suffix_link = "https://web.whatsapp.com/send?phone={mobile}&text&type=phone_number&app_absent=1"
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.mobile = ""

    async def initialize(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        self.cli()
        await self.login()

    @property
    def browser_options(self):
        options = {}
        if sys.platform == "win32":
            options["args"] = ["--profile-directory=Default"]
            options["user_data_dir"] = "C:/Temp/ChromeProfile"
        else:
            options["args"] = ["--start-maximized"]
        return options

    @property
    def context_options(self):
        options = {}
        if sys.platform != "win32":
            options["viewport"] = None
        return options

    def cli(self):
        """
        LOGGER settings  [nCKbr]
        """
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s -- [%(levelname)s] >> %(message)s"
            )
        )
        LOGGER.addHandler(handler)
        LOGGER.setLevel(logging.INFO)

    async def login(self):
        await self.page.goto(self.BASE_URL)
        await self.page.wait_for_timeout(20000)
        if sys.platform == "win32":
            await self.page.bring_to_front()
        else:
            await self.page.set_viewport_size({"width": 1920, "height": 1080})

    async def logout(self):
        prefix = "//div[@id='side']/header/div[2]/div/span/div[3]"
        dots_button = await self.page.wait_for_selector(f"{prefix}/div[@role='button']")
        await dots_button.click()

        logout_item = await self.page.wait_for_selector(
            f"{prefix}/span/div[1]/ul/li[last()]/div[@role='button']"
        )
        await logout_item.click()

        # Wait for logout to complete
        await self.page.wait_for_navigation()

    async def get_list_of_messages(self):
        """get_list_of_messages()

        gets the list of messages in the page
        """
        messages = await self.page.query_selector_all(
            '//*[@id="pane-side"]/div[2]/div/div/child::div'
        )

        clean_messages = []
        for message in messages:
            _message = (await message.inner_text()).split("\n")
            if len(_message) == 2:
                clean_messages.append(
                    {
                        "sender": _message[0],
                        "time": _message[1],
                        "message": "",
                        "unread": False,
                        "no_of_unread": 0,
                        "group": False,
                    }
                )
            elif len(_message) == 3:
                clean_messages.append(
                    {
                        "sender": _message[0],
                        "time": _message[1],
                        "message": _message[2],
                        "unread": False,
                        "no_of_unread": 0,
                        "group": False,
                    }
                )
            elif len(_message) == 4:
                clean_messages.append(
                    {
                        "sender": _message[0],
                        "time": _message[1],
                        "message": _message[2],
                        "unread": _message[-1].isdigit(),
                        "no_of_unread": (
                            int(_message[-1]) if _message[-1].isdigit() else 0
                        ),
                        "group": False,
                    }
                )
            elif len(_message) == 5:
                clean_messages.append(
                    {
                        "sender": _message[0],
                        "time": _message[1],
                        "message": "",
                        "unread": _message[-1].isdigit(),
                        "no_of_unread": (
                            int(_message[-1]) if _message[-1].isdigit() else 0
                        ),
                        "group": True,
                    }
                )
            elif len(_message) == 6:
                clean_messages.append(
                    {
                        "sender": _message[0],
                        "time": _message[1],
                        "message": _message[4],
                        "unread": _message[-1].isdigit(),
                        "no_of_unread": (
                            int(_message[-1]) if _message[-1].isdigit() else 0
                        ),
                        "group": True,
                    }
                )
            else:
                LOGGER.info(f"Unknown message format: {_message}")
        return clean_messages
