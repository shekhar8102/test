# Delta Exchange Bitcoin Futures Supertrend Trading Bot

This Python application automates a trading strategy for Bitcoin (BTC/BTCUSD) futures on the Delta Exchange. It operates on multiple timeframes (3-minute, 5-minute, and 15-minute) and uses the Supertrend indicator to generate buy and sell signals.

## Features

- **Multi-Timeframe Analysis**: Tracks 3-min, 5-min, and 15-min charts simultaneously.
- **Supertrend Indicator**: Uses the Supertrend indicator (ATR Period: 8, Multiplier: 2) to determine market trends and generate trading signals.
- **Automated Trading**: Places market orders automatically when a buy or sell signal is detected on a closed candle.
- **Stop-Loss Management**: Sets a stop-loss order at the time of entry based on the Average True Range (ATR), helping to manage risk.
- **Live Status Monitoring**: Provides a real-time command-line display of the bot's status every 30 seconds, showing the current trend, position details (entry price, P&L), and stop-loss for each timeframe.
- **Test and Production Modes**:
  - **`test` mode**: Simulates order placements without risking real capital, allowing you to observe the bot's behavior.
  - **`prod` mode**: Places live orders on the Delta Exchange (India).

## Prerequisites

- Python 3.7+
- A Delta Exchange account (a separate testnet account is recommended for `test` mode).

## Setup Instructions

1.  **Clone the Repository**:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Install Dependencies**:
    It's recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Configure API Credentials**:
    Create a file named `.env` in the root directory of the project. This file will store your API keys securely.

    You will need to generate API keys from your Delta Exchange account for both the production and testnet environments.

    Add your keys to the `.env` file like this:

    ```env
    # Delta Exchange API Credentials for Production (India)
    DELTA_API_KEY_PROD="YOUR_PRODUCTION_API_KEY"
    DELTA_API_SECRET_PROD="YOUR_PRODUCTION_API_SECRET"

    # Delta Exchange API Credentials for Testnet (India)
    DELTA_API_KEY_TEST="YOUR_TESTNET_API_KEY"
    DELTA_API_SECRET_TEST="YOUR_TESTNET_API_SECRET"
    ```

## How to Run the Bot

You can run the bot in either `test` or `prod` mode using the `--mode` command-line argument.

-   **To run in Test Mode (default)**:
    ```bash
    python trading_bot.py --mode test
    ```
    or simply:
    ```bash
    python trading_bot.py
    ```

-   **To run in Production Mode (use with caution)**:
    ```bash
    python trading_bot.py --mode prod
    ```

The bot will start, initialize the historical data, and then enter a loop to fetch live prices and manage trades. The status of each timeframe will be printed to the console every 30 seconds.

## Disclaimer

Trading cryptocurrencies involves significant risk. This bot is provided as-is, and the user assumes all risks associated with its use. It is highly recommended to thoroughly test the bot in `test` mode before deploying it in a live `prod` environment. The author is not responsible for any financial losses.