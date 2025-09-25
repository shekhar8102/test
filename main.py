import time
import requests
from dhanhq import dhanhq
from config import CLIENT_ID, ACCESS_TOKEN
from datetime import date, timedelta, datetime

# Constants
SENSEX_SECURITY_ID = "1"
BSE_EXCHANGE = "BSE_I"
MODE = "test"  # "test" or "prod"

class MockDhan:
    def get_market_quote(self, securities, exchange_segment, instrument_type):
        return {'status': 'success', 'data': [{'ltp': 75000}]}

    def get_option_chain(self, symbol, exchange_segment, instrument_type, expiry_date=None):
        return {
            'status': 'success',
            'data': {
                'expiry_dates': ['2025-10-31'],
                'option_chain': [
                    {'strike_price': 75000, 'ce_security_id': 'CE75000', 'pe_security_id': 'PE75000'},
                    {'strike_price': 75100, 'ce_security_id': 'CE75100', 'pe_security_id': 'PE75100'},
                    {'strike_price': 74900, 'ce_security_id': 'CE74900', 'pe_security_id': 'PE74900'},
                ]
            }
        }

    def place_order(self, security_id, exchange_segment, transaction_type, quantity, order_type, product_type, price):
        return {'status': 'success', 'data': {'orderId': f"test_{security_id}"}}

    def get_order_by_id(self, order_id):
        return {'status': 'success', 'data': {'status': 'TRADED'}}

    def get_positions(self):
        return {'status': 'success', 'data': []}

def get_sensex_ltp(dhan):
    """
    Fetches the live spot price of the Sensex index.
    """
    try:
        response = dhan.get_market_quote(
            securities=[SENSEX_SECURITY_ID],
            exchange_segment=BSE_EXCHANGE,
            instrument_type='INDEX'
        )
        if response and response.get('status') == 'success':
            return response['data'][0]['ltp']
        else:
            error_message = response.get('errorMessage', 'Unknown error')
            print(f"Error fetching Sensex price: {error_message}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Sensex price: Network error - {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def get_security_id_for_option(dhan, strike, option_type):
    """
    Finds the security ID for a given option strike and type for the nearest weekly expiry.
    """
    try:
        expiry_response = dhan.get_option_chain('SENSEX', 'BSE_FNO', 'INDEX')
        if not expiry_response or expiry_response.get('status') != 'success':
            print(f"Error fetching expiry list: {expiry_response}")
            return None

        expiry_dates = expiry_response['data']['expiry_dates']
        nearest_expiry = expiry_dates[0]

        response = dhan.get_option_chain(
            symbol='SENSEX',
            exchange_segment='BSE_FNO',
            instrument_type='INDEX',
            expiry_date=nearest_expiry
        )

        if response and response.get('status') == 'success':
            option_chain = response['data']['option_chain']
            for option in option_chain:
                if option['strike_price'] == strike:
                    if option_type == 'CE' and option['ce_security_id']:
                        return option['ce_security_id']
                    elif option_type == 'PE' and option['pe_security_id']:
                        return option['pe_security_id']
            print(f"Option not found for strike {strike} and type {option_type}")
            return None
        else:
            print(f"Error fetching option chain: {response}")
            return None
    except Exception as e:
        print(f"Error finding security ID for option: {e}")
        return None

def get_straddle_strikes(spot_price):
    """
    Calculates the three straddle strikes based on the spot price.
    """
    atm_strike = round(spot_price / 100) * 100
    otm_strike_above = atm_strike + 100
    otm_strike_below = atm_strike - 100
    return otm_strike_below, atm_strike, otm_strike_above


def place_short_straddle(dhan, strike, mode):
    """
    Places a short straddle order for a given strike and returns a straddle object.
    """
    try:
        print(f"Placing short straddle for strike: {strike}")

        ce_security_id = get_security_id_for_option(dhan, strike, "CE")
        pe_security_id = get_security_id_for_option(dhan, strike, "PE")

        if not ce_security_id or not pe_security_id:
            return None

        straddle = {'strike': strike, 'ce_security_id': ce_security_id, 'pe_security_id': pe_security_id}

        if mode == "prod":
            ce_order_response = dhan.place_order(security_id=ce_security_id, exchange_segment='BSE_FNO', transaction_type='SELL', quantity=1, order_type='MARKET', product_type='NORMAL', price=0)
            pe_order_response = dhan.place_order(security_id=pe_security_id, exchange_segment='BSE_FNO', transaction_type='SELL', quantity=1, order_type='MARKET', product_type='NORMAL', price=0)

            if ce_order_response and ce_order_response.get('status') == 'success' and pe_order_response and pe_order_response.get('status') == 'success':
                straddle['ce_order_id'] = ce_order_response['data']['orderId']
                straddle['pe_order_id'] = pe_order_response['data']['orderId']
                print(f"Orders placed for straddle {strike}: CE Order ID {straddle['ce_order_id']}, PE Order ID {straddle['pe_order_id']}")
                return straddle
            else:
                print(f"Failed to place full straddle for strike {strike}.")
                return None
        else:
            print(f"Test mode: Would place short straddle for {ce_security_id} and {pe_security_id}")
            straddle['ce_order_id'] = f"test_{ce_security_id}"
            straddle['pe_order_id'] = f"test_{pe_security_id}"
            return straddle

    except Exception as e:
        print(f"Error placing short straddle for strike {strike}: {e}")
        return None

def check_order_status(dhan, order_id):
    """
    Checks the status of a placed order.
    """
    if "test" in order_id:
        return "TRADED"  # Simulate immediate execution for test orders

    try:
        response = dhan.get_order_by_id(order_id)
        if response and response.get('status') == 'success':
            return response['data']['status']
        else:
            print(f"Error checking order status for order {order_id}: {response}")
            return None
    except Exception as e:
        print(f"Error checking order status for order {order_id}: {e}")
        return None

def square_off_straddle(dhan, straddle, mode):
    """
    Squares off a straddle.
    """
    try:
        print(f"Squaring off straddle for strike: {straddle['strike']}")

        if mode == "prod":
            for security_id in [straddle['ce_security_id'], straddle['pe_security_id']]:
                order_response = dhan.place_order(
                    security_id=security_id,
                    exchange_segment='BSE_FNO',
                    transaction_type='BUY',
                    quantity=1,
                    order_type='MARKET',
                    product_type='NORMAL',
                    price=0
                )
                print(f"Square off response for {security_id}: {order_response}")
        else:
            print(f"Test mode: Would square off straddle for {straddle['strike']}")

    except Exception as e:
        print(f"Error squaring off straddle for strike {straddle['strike']}: {e}")

def manage_positions(dhan, tracked_straddles):
    """
    Manages the placed straddle positions.
    """
    while True:
        try:
            positions = dhan.get_positions()
            if positions.get('status') != 'success':
                print(f"Error fetching positions: {positions}")
                time.sleep(5)
                continue

            open_positions = [p for p in positions.get('data', []) if p.get('positionType') != 'CLOSED']

            print("\n--- Current Positions ---")
            for straddle in tracked_straddles:
                ce_leg = next((p for p in open_positions if p.get('securityId') == straddle.get('ce_security_id')), None)
                pe_leg = next((p for p in open_positions if p.get('securityId') == straddle.get('pe_security_id')), None)

                if ce_leg and pe_leg:
                    ce_pnl = (ce_leg.get('sellAvg', 0) - ce_leg.get('ltp', 0)) * ce_leg.get('netQty', 0)
                    pe_pnl = (pe_leg.get('sellAvg', 0) - pe_leg.get('ltp', 0)) * pe_leg.get('netQty', 0)
                    pnl = ce_pnl + pe_pnl
                    print(f"Straddle Strike: {straddle['strike']}, P&L: {pnl:.2f}")

            print("\nOptions: [U]pdate, [M]ove Top, [N]ove Bottom, [E]xit")
            choice = input("Enter your choice: ").upper()

            if choice == 'U':
                continue
            elif choice == 'M':
                if len(tracked_straddles) < 3:
                    print("Not enough straddles to move.")
                    continue
                # Move the top-most straddle down
                top_straddle = max(tracked_straddles, key=lambda s: s['strike'])
                square_off_straddle(dhan, top_straddle, MODE)
                tracked_straddles.remove(top_straddle)

                new_strike = min(s['strike'] for s in tracked_straddles) - 100
                new_straddle = place_short_straddle(dhan, new_strike, MODE)
                if new_straddle:
                    tracked_straddles.append(new_straddle)
                    tracked_straddles.sort(key=lambda s: s['strike'])
                else:
                    print("Failed to place new straddle. Re-adding the old one.")
                    tracked_straddles.append(top_straddle)

            elif choice == 'N':
                if len(tracked_straddles) < 3:
                    print("Not enough straddles to move.")
                    continue
                # Move the bottom-most straddle up
                bottom_straddle = min(tracked_straddles, key=lambda s: s['strike'])
                square_off_straddle(dhan, bottom_straddle, MODE)
                tracked_straddles.remove(bottom_straddle)

                new_strike = max(s['strike'] for s in tracked_straddles) + 100
                new_straddle = place_short_straddle(dhan, new_strike, MODE)
                if new_straddle:
                    tracked_straddles.append(new_straddle)
                    tracked_straddles.sort(key=lambda s: s['strike'])
                else:
                    print("Failed to place new straddle. Re-adding the old one.")
                    tracked_straddles.append(bottom_straddle)

            elif choice == 'E':
                break
            else:
                print("Invalid choice. Please try again.")
        except KeyboardInterrupt:
            print("\nExiting on user request.")
            break
        except Exception as e:
            print(f"An error occurred in position management: {e}")

        time.sleep(5)


def main():
    """
    Main function to run the trading application.
    """
    global MODE

    print("--- Sensex Straddle Trading App ---")
    mode_choice = input("Enter mode (test/prod): ").lower()
    if mode_choice in ["test", "prod"]:
        MODE = mode_choice
    else:
        print("Invalid mode. Defaulting to 'test'.")
    print("-" * 35)

    if MODE == 'test':
        dhan = MockDhan()
    else:
        dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)

    print("Fetching initial Sensex price...")
    sensex_price = get_sensex_ltp(dhan)

    if not sensex_price:
        print("Could not fetch Sensex price. Exiting.")
        return

    print(f"Current Sensex Price: {sensex_price:.2f}")
    strikes = list(get_straddle_strikes(sensex_price))

    while True:
        print("\n--- Initial Straddle Setup ---")
        print(f"Current Straddle Strikes: {strikes[0]}, {strikes[1]}, {strikes[2]}")
        print("Options: [U]p, [D]own, [F]ire, [E]xit")
        choice = input("Enter your choice: ").upper()

        if choice == 'U':
            strikes = [s + 100 for s in strikes]
        elif choice == 'D':
            strikes = [s - 100 for s in strikes]
        elif choice == 'F':
            tracked_straddles = []
            for strike in strikes:
                straddle = place_short_straddle(dhan, strike, MODE)
                if straddle:
                    tracked_straddles.append(straddle)

            # Confirm all orders are executed
            all_executed = False
            while not all_executed:
                all_executed = True
                for straddle in tracked_straddles:
                    for order_id in [straddle['ce_order_id'], straddle['pe_order_id']]:
                        status = check_order_status(dhan, order_id)
                        if status != 'TRADED': # Executed
                            all_executed = False
                            print(f"Order {order_id} is still {status}. Waiting...")
                            time.sleep(2)
                            break
                    if not all_executed:
                        break

            print("All orders executed. Entering position management.")
            manage_positions(dhan, tracked_straddles)
            break
        elif choice == 'E':
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()