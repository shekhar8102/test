# This will be the main file for the trading bot.
import time
import argparse
import pandas as pd
from delta_rest_client import DeltaRestClient, APIError
from stock_indicators import indicators
from config import (
    DELTA_API_KEY_PROD,
    DELTA_API_SECRET_PROD,
    DELTA_API_KEY_TEST,
    DELTA_API_SECRET_TEST,
    DELTA_API_URL_PROD,
    DELTA_API_URL_TEST,
)

# Constants
SYMBOL = "BTCUSD"
PRODUCT_ID = 27  # Assuming BTCUSD product ID is 27, will verify.
ATR_PERIOD = 8
ATR_MULTIPLIER = 2
TIMEFRAMES = {
    "3min": {"resolution": "3m", "seconds": 180, "data": pd.DataFrame(), "position": {}},
    "5min": {"resolution": "5m", "seconds": 300, "data": pd.DataFrame(), "position": {}},
    "15min": {"resolution": "15m", "seconds": 900, "data": pd.DataFrame(), "position": {}},
}
LOOP_INTERVAL = 30  # seconds


def get_historical_data(delta_client, product_id, resolution):
    """
    Fetches historical OHLC data and calculates Supertrend.
    """
    try:
        # Fetching enough data for indicator warm-up
        end_time = int(time.time())
        start_time = end_time - (250 * TIMEFRAMES[resolution]['seconds']) # 250 candles to be safe

        candles = delta_client.get_history_candles(
            product_id=product_id,
            resolution=TIMEFRAMES[resolution]["resolution"],
            start=start_time,
            end=end_time,
        )

        if not candles["result"]:
            print(f"No historical data found for {resolution}.")
            return None

        # Convert to stock-indicators Quote format
        quotes = [
            indicators.Quote(
                d=pd.to_datetime(c["time"], unit="s"),
                o=c["open"],
                h=c["high"],
                l=c["low"],
                c=c["close"],
                v=c["volume"],
            )
            for c in candles["result"]
        ]
        return quotes
    except APIError as e:
        print(f"Error fetching historical data for {resolution}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while fetching historical data: {e}")
        return None


def calculate_supertrend(quotes):
    """
    Calculates the Supertrend indicator from a list of quotes.
    """
    if not quotes:
        return None
    supertrend_results = indicators.get_super_trend(
        quotes, ATR_PERIOD, ATR_MULTIPLIER
    )
    return supertrend_results


def place_order(delta_client, product_id, side, size, mode):
    """
    Places a market order on Delta Exchange.
    """
    if mode == "test":
        print(f"--- [TEST MODE] ---")
        print(f"Side: {side.upper()}, Size: {size}")
        # Simulate a successful order placement for testing purposes
        return {"id": f"test_{side}_{int(time.time())}", "size": size, "side": side}

    try:
        order = delta_client.place_order(
            product_id=product_id,
            size=size,
            side=side,
            order_type="market_order",
        )
        print(f"--- [PROD MODE] Order placed successfully ---")
        print(f"OrderID: {order['id']}, Side: {order['side']}, Size: {order['size']}")
        return order
    except APIError as e:
        print(f"--- [PROD MODE] Order placement failed ---")
        print(f"Error: {e}")
        return None

def check_and_place_order(delta_client, tf_name, tf_props, mode):
    """
    Checks for Supertrend signals and places orders accordingly.
    """
    df = tf_props["data"]
    if len(df) < 2:
        return # Not enough data to check for a signal

    # Get the last two closed candles
    last_candle = df.iloc[-2]
    current_price = df.iloc[-1]["close"]

    # Supertrend values
    supertrend_value = last_candle["supertrend"]
    is_uptrend = last_candle["lower_band"] is not None

    position = tf_props.get("position", {})

    # ---== Trading Signals ==---
    # BUY SIGNAL: Price crosses above the Supertrend line
    if current_price > supertrend_value and not is_uptrend and not position:
        print(f"[{tf_name}] BUY SIGNAL DETECTED at {current_price}")

        # Define order size (e.g., 1 contract for simplicity)
        order_size = 1

        # Place order
        order_result = place_order(delta_client, PRODUCT_ID, "buy", order_size, mode)

        if order_result:
            # Set stop loss based on the low of the signal candle or the lower band
            stop_loss = min(last_candle["low"], last_candle["lower_band"] if pd.notna(last_candle["lower_band"]) else last_candle["low"])
            tf_props["position"] = {
                "status": "LONG",
                "entry_price": current_price,
                "size": order_size,
                "stop_loss": stop_loss,
                "order_id": order_result["id"]
            }
            print(f"[{tf_name}] Entered LONG position at {current_price}, Stop Loss: {stop_loss}")

    # SELL SIGNAL: Price crosses below the Supertrend line
    elif current_price < supertrend_value and is_uptrend and not position:
        print(f"[{tf_name}] SELL SIGNAL DETECTED at {current_price}")

        order_size = 1
        order_result = place_order(delta_client, PRODUCT_ID, "sell", order_size, mode)

        if order_result:
            # Set stop loss based on the high of the signal candle or the upper band
            stop_loss = max(last_candle["high"], last_candle["upper_band"] if pd.notna(last_candle["upper_band"]) else last_candle["high"])
            tf_props["position"] = {
                "status": "SHORT",
                "entry_price": current_price,
                "size": order_size,
                "stop_loss": stop_loss,
                "order_id": order_result["id"]
            }
            print(f"[{tf_name}] Entered SHORT position at {current_price}, Stop Loss: {stop_loss}")

    # ---== Stop Loss Check ==---
    # This is a simple check. In a real-world scenario, you'd also need to handle position closing orders.
    elif position:
        if position["status"] == "LONG" and current_price < position["stop_loss"]:
            print(f"[{tf_name}] STOP LOSS HIT for LONG position at {current_price}. Closing position.")
            place_order(delta_client, PRODUCT_ID, "sell", position["size"], mode)
            tf_props["position"] = {} # Clear position
        elif position["status"] == "SHORT" and current_price > position["stop_loss"]:
            print(f"[{tf_name}] STOP LOSS HIT for SHORT position at {current_price}. Closing position.")
            place_order(delta_client, PRODUCT_ID, "buy", position["size"], mode)
            tf_props["position"] = {} # Clear position


def print_status(latest_price):
    """
    Prints the status of all timeframes.
    """
    print("-" * 80)
    print(f"Current BTC Price: {latest_price:.2f} | Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)

    for tf_name, tf_props in TIMEFRAMES.items():
        df = tf_props["data"]
        if df.empty:
            print(f"{tf_name:<5}: Data not available.")
            continue

        position = tf_props.get("position", {})
        last_candle = df.iloc[-1]

        # Determine Supertrend direction
        supertrend_direction = "UP" if pd.notna(last_candle["lower_band"]) else "DOWN"

        # Position details
        pos_status = position.get("status", "NONE")
        entry_price = position.get("entry_price", 0)
        stop_loss = position.get("stop_loss", 0)
        pnl = 0

        if pos_status == "LONG":
            pnl = (latest_price - entry_price) * position.get("size", 0)
        elif pos_status == "SHORT":
            pnl = (entry_price - latest_price) * position.get("size", 0)

        status_line = (
            f"{tf_name:<5} | "
            f"Position: {pos_status:<5} | "
            f"Trend: {supertrend_direction:<4} | "
            f"Entry: {entry_price: >9.2f} | "
            f"P&L: {pnl: >8.2f} | "
            f"Stop: {stop_loss: >9.2f}"
        )
        print(status_line)
    print("-" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Delta Exchange Supertrend Trading Bot")
    parser.add_argument(
        "--mode",
        type=str,
        default="test",
        choices=["test", "prod"],
        help="Trading mode: 'test' or 'prod'",
    )
    args = parser.parse_args()

    print(f"--- Starting Supertrend Trading Bot in {args.mode.upper()} mode ---")

    # Setup Delta Client
    if args.mode == "prod":
        delta_client = DeltaRestClient(
            base_url=DELTA_API_URL_PROD,
            api_key=DELTA_API_KEY_PROD,
            api_secret=DELTA_API_SECRET_PROD,
        )
    else:
        delta_client = DeltaRestClient(
            base_url=DELTA_API_URL_TEST,
            api_key=DELTA_API_KEY_TEST,
            api_secret=DELTA_API_SECRET_TEST,
        )

    # Verify product ID
    try:
        product = delta_client.get_product(SYMBOL)
        global PRODUCT_ID
        PRODUCT_ID = product["id"]
        print(f"Verified Product ID for {SYMBOL}: {PRODUCT_ID}")
    except (APIError, KeyError) as e:
        print(f"Error fetching product details for {SYMBOL}: {e}")
        return

    # Initialize data for all timeframes
    for tf_name, tf_props in TIMEFRAMES.items():
        print(f"Fetching initial data for {tf_name}...")
        quotes = get_historical_data(delta_client, PRODUCT_ID, tf_name)
        if quotes:
            supertrend_results = calculate_supertrend(quotes)

            # Convert results to a pandas DataFrame for easier handling
            df = pd.DataFrame(
                [
                    {
                        "date": r.date,
                        "open": q.open,
                        "high": q.high,
                        "low": q.low,
                        "close": q.close,
                        "volume": q.volume,
                        "supertrend": r.super_trend,
                        "upper_band": r.upper_band,
                        "lower_band": r.lower_band,
                    }
                    for q, r in zip(quotes, supertrend_results)
                ]
            )
            tf_props["data"] = df
            print(f"Successfully loaded {len(df)} candles for {tf_name}.")
            # print(df.tail(2)) # For debugging
        else:
            print(f"Could not initialize data for {tf_name}. Exiting.")
            return

    print("\nInitialization complete. Starting main loop...\n")

    while True:
        try:
            # Fetch the latest price
            ticker = delta_client.get_ticker(SYMBOL)
            latest_price = float(ticker["spot_price"])

            current_timestamp = time.time()

            for tf_name, tf_props in TIMEFRAMES.items():
                df = tf_props["data"]
                if df.empty:
                    continue

                # Candle management
                last_candle_time = df.iloc[-1]["date"].timestamp()
                time_since_last_candle = current_timestamp - last_candle_time

                if time_since_last_candle < tf_props["seconds"]:
                    # Update current (last) candle
                    df.loc[df.index[-1], "high"] = max(df.iloc[-1]["high"], latest_price)
                    df.loc[df.index[-1], "low"] = min(df.iloc[-1]["low"], latest_price)
                    df.loc[df.index[-1], "close"] = latest_price
                else:
                    # A new candle has closed
                    print(f"New {tf_name} candle closed at {df.iloc[-1]['close']}.")

                    # Create a new candle
                    new_candle_timestamp = pd.to_datetime(current_timestamp, unit='s').floor(f'{tf_props["seconds"]}s')
                    new_candle = {
                        "date": new_candle_timestamp,
                        "open": df.iloc[-1]["close"],
                        "high": latest_price,
                        "low": latest_price,
                        "close": latest_price,
                        "volume": 0, # Volume data is not available from ticker, so we'll have to manage without it or find another source
                    }

                    # Recalculate supertrend with the new candle
                    # First, convert dataframe back to quotes
                    quotes = [indicators.Quote(d=row['date'], o=row['open'], h=row['high'], l=row['low'], c=row['close'], v=row['volume']) for index, row in df.iterrows()]
                    quotes.append(indicators.Quote(d=new_candle['date'], o=new_candle['open'], h=new_candle['high'], l=new_candle['low'], c=new_candle['close'], v=new_candle['volume']))

                    supertrend_results = calculate_supertrend(quotes)

                    # Update the dataframe
                    new_df = pd.DataFrame(
                        [
                            {
                                "date": r.date,
                                "open": q.open,
                                "high": q.high,
                                "low": q.low,
                                "close": q.close,
                                "volume": q.volume,
                                "supertrend": r.super_trend,
                                "upper_band": r.upper_band,
                                "lower_band": r.lower_band,
                            }
                            for q, r in zip(quotes, supertrend_results)
                        ]
                    )
                    tf_props["data"] = new_df

                    # --- TRADING LOGIC ---
                    check_and_place_order(delta_client, tf_name, tf_props, args.mode)


            # Display current status
            print_status(latest_price)

            time.sleep(LOOP_INTERVAL)

        except APIError as e:
            print(f"An API error occurred in the main loop: {e}")
            time.sleep(LOOP_INTERVAL)
        except Exception as e:
            print(f"An unexpected error occurred in the main loop: {e}")
            break


if __name__ == "__main__":
    main()