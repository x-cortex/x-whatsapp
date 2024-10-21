# x-whatsapp

`x-whatsapp` by x-cortex is a python library for automating WhatsApp interactions. It uses playwright to automate tasks such as sending messages, fetching chat history, and listening for new messages on WhatsApp Web.

<!-- To be added after publishing to PyPI -->
<!-- ## Installation

You can install `x-whatsapp` from PyPI using pip:

```bash
pip install x-whatsapp
``` -->

## Usage

### Initializing the Client

```python
from x_whatsapp import WhatsappClient

# Initialize the client with debugging enabled
client = WhatsappClient(DEBUG=True)
# Initialize Playwright and launch the browser
await client.initialize_playwright()
# Log in to WhatsApp
await client.login()
```

### Sending a Message

```python
await client.send_message("contact_name", "Hello from x-whatsapp!")
```

### Fetching Chat History

```python
await client.open_chat_panel("contact_name")
messages = await client.extract_messages()
for message in messages:
    print(message)
```

<!-- ### Listening for New Messages

```python
def on_new_message(message):
    print(f"New message from {message['sender']}: {message['message']}")

await client.on_new_message(on_new_message, interval=2)
``` -->

### Logging Out

```python
await client.logout()
```

<!-- To be added -->
<!-- # Configuration

You can configure various settings like the browser instance, headless mode, and user data directory.

```python
BROWSER_INSTANCE = "chromium"
HEADLESS = False
USER_DATA_DIR = "user_data"
BASE_URL = "https://web.whatsapp.com/"
``` -->

# Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

