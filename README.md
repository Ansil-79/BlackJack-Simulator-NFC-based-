# Overview

An NFC-integrated blackjack platform that allows players to load funds from NFC cards, play blackjack through a browser interface, and cash out updated balances back to the card.

The system uses a Python backend to communicate with an NFC reader and manage card data, while a JavaScript frontend provides the game interface. Browser and server communication is handled through WebSockets, enabling real-time balance updates and card interactions.

## Technologies

* Python 3.14.3
* Pyscard
* JavaScript
* HTML/CSS
* WebSockets
* NFC reader (ACR122U -A9)
* NFC chips (NTAG215)

## Features

* NFC card authentication and balance management
* Real-time communication between browser and NFC reader
* Blackjack gameplay with betting support
* Load funds from NFC cards into a game session
* Cash out winnings directly back to the NFC card

```
## Setup

INSTALLING THE REQUIRED FILES:
Download index.html and nfc_server.py into your local system


SETTING UP THE HARDWARE:
conncet any compatible nfc reader to your system and preload your nfc tags using any software from apple store
Eg: For this project, ACR122U -A9 was used as reader, NTAG215 was used as nfc tags, and 'NFC TOOLS' was used to preload the chips.
Load the chip in the given format: BALANCE:250

GATHERING THE LIBRARIES REQUIRED:
In the terminal, run:
pip install pyscard websockets
python3 nfc_server.py
Open `index.html` in your browser.
```


# Demo Video:
https://drive.google.com/file/d/1MeWXi_cNxmfGNmEsVV94_PDxY1V564T1/view?usp=drivesdk










