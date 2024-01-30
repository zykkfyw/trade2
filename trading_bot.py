import alpaca_trade_api as tradeapi
from alpaca_trade_api import TimeFrame
import threading
import time
import requests
import json

class TradingBot:
    """A trading bot class for managing stock and crypto trades."""

    MAX_TOTAL_PERCENTAGE = 0.20  # Maximum percentage of total funds for active trades
    MAX_SINGLE_TRADE_PERCENTAGE = 0.02  # Maximum percentage of total funds for a single trade
    profit_loss_ratio = 1.0 # this value is the profit to loss ratio in percentage
    MAX_RETRIES = 5  # Maximum number of retries for selling a position
    RETRY_WAIT = 30  # Wait time (in seconds) between retries
    MIN_EXIT_PRICE = 25 # The minimum amount in below the take_profit price a trade can be exited on
    
    def __init__(self, api_key, api_secret, base_url):
        """Initialize the trading bot with Alpaca API credentials."""
        self.api = tradeapi.REST(api_key, api_secret, base_url=base_url)
        self.account = self.api.get_account()
        self.purchase_price = {}
        self.lock = threading.Lock()  # Lock for synchronization
        
    def _get_account(self):
        return self.account
        
    def _get_current_price(self, symbol):
        """Get the current price of a symbol."""
        try:
            quote = self.api.get_bars(symbol, TimeFrame.Minute, limit=1).df.iloc[-1]['close']
            return quote
        except Exception as e:
            # If an exception occurs when fetching data from Alpaca, try an alternative source
            response = requests.get(f"https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes?symbols={symbol}").text
            quote = json.loads(response).get('quotes').get(symbol).get('ap')
            return quote

    def _is_asset_being_traded(self, symbol):
        """Check if an asset is already being traded."""
        try:
            current_positions = self.api.list_positions()
            for pos in current_positions:
                if symbol.lower().replace("/", "") == pos._raw.get("symbol").lower():
                    return True
            return False
        except Exception as e:
            return False

    def _get_quantity(self, symbol):
        """Fetch the current quantity of the asset."""
        try:
            current_positions = self.api.list_positions()
            for pos in current_positions:
                if symbol.lower().replace("/", "") == pos._raw.get("symbol").lower():
                    qty = pos._raw.get("qty")
                    return float(qty)
        except Exception as e:
            return 0.0

    def _close_order(self, symbol):
        """Close an order."""
        try:
            while True:
                qty = self._get_quantity(symbol)
                if self._is_asset_being_traded(symbol):
                    entry_price = round(self.get_entry_price(symbol), 5)
                    if round(self._get_current_price(symbol), 5) > (entry_price + self.MIN_EXIT_PRICE):
                        sell_order = self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
                if not self._is_asset_being_traded(symbol):
                    self.purchase_price.pop(symbol)
                    print(f"SOLD ... {symbol} @ Current_Price = {round(self._get_current_price(symbol), 5)} on a Sell Signal")
                    break
                time.sleep(self.RETRY_WAIT)
        except Exception as e:
            print(f'An error occurred closing ... {symbol} : {e}')
            return f"An error occurred closing ... {symbol} : {e}", 407

    def _calculate_qty_to_trade(self, current_price, total_funds, symbol):
        """Calculate the quantity to trade based on available funds and price."""
        max_trade_funds = total_funds * self.MAX_SINGLE_TRADE_PERCENTAGE
        qty = max_trade_funds / current_price
        if self.api.get_asset(symbol).fractionable:
            if self.api.get_asset(symbol)._raw.get("class").lower() == "crypto":
                self.MIN_EXIT_PRICE = 50
                return qty  # Return fractional quantity for crypto assets
            else:
                self.MIN_EXIT_PRICE = 2
                return int(qty)
        else:
            return int(qty)

    def load_existing_trades(self):
        """Load existing trades from the Alpaca account."""
        try:
            current_positions = self.api.list_positions()
            for pos in current_positions:
                symbol = pos._raw.get("symbol")
                if pos._raw.get("asset_class").lower() == "crypto":
                    symbol = symbol.replace("USD", "/USD")
                current_price = pos._raw.get("current_price")
                entry_price = float(current_price) + float(pos._raw.get("unrealized_pl"))
                try:
                    self.purchase_price[symbol] = entry_price
                except:
                    pass
                stop_loss = entry_price - (entry_price * 0.01)
                take_profit = entry_price + (float(self.profit_loss_ratio) * (entry_price - stop_loss))
                threading.Thread(target=self._monitor_and_execute, args=(symbol, round(take_profit, 5), round(stop_loss, 5))).start()
                print(f"Added an Existing order of {self._get_quantity(symbol)} units of {symbol} .. is being monitored -- profit at {round(take_profit, 5)} stop loss at {round(stop_loss, 5)}")
        except Exception as e:
            return f"Error: {e}", 406

    def get_entry_price(self, symbol):
        """Get the entry price of a symbol."""
        entry_price = 0
        try:
            current_positions = self.api.list_positions()
            for pos in current_positions:
                symbol = pos._raw.get("symbol")
                if symbol.lower() == pos._raw.get("symbol").replace("/", "").lower():
                    current_price = pos._raw.get("current_price")
                    entry_price = float(current_price) + float(pos._raw.get("unrealized_pl"))
                    return round(entry_price, 5)
            if entry_price == 0:
                return round(self._get_current_price(symbol), 5)
        except Exception as e:
            return f"Error: {e}", 406

    def _monitor_and_execute(self, symbol, take_profit, stop_loss):
        """Monitor price and execute sell order based on conditions."""
        time.sleep(self.RETRY_WAIT)
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                if not self._is_asset_being_traded(symbol):
                    print(f"{symbol} ---> The position is no longer being traded ... Stopping the monitoring")
                    try:
                        self.purchase_price.pop(symbol)
                    except:
                        pass
                    break

                current_price = self._get_current_price(symbol)
                print(f"Checking ... {symbol} ---> Current_Price = {round(current_price, 5)} Take_Profit = {round(take_profit, 5)} Stop_Loss = {round(stop_loss, 5)}")
                try:
                    self.purchase_price[symbol] = self.get_entry_price(symbol)
                except:
                    pass
                if round(current_price, 5) >= round(take_profit, 5) or round(current_price, 5) <= round(stop_loss, 5):
                    if round(current_price, 5) >= round(take_profit, 5):
                        profit_loss = "PROFIT"
                    else:
                        profit_loss = "LOSS"
                    qty = self._get_quantity(symbol)
                    print(f"Selling @ ({profit_loss}) ... {symbol} ---> Current_Price = {round(current_price, 5)} Take_Profit = {round(take_profit, 5)} Stop_Loss = {round(stop_loss, 5)}")
                    sell_order = self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
                    if sell_order.status == 'filled':
                        print(f"SOLD @ ({profit_loss})... {symbol} ---> Current_Price = {round(current_price, 5)} Take_Profit = {round(take_profit, 5)} Stop_Loss = {round(stop_loss, 5)}")
                        try:
                            self.purchase_price.pop(symbol)
                        except:
                            pass
                        break
            except Exception as e:
                print(f"Error with sell order for {symbol}: {e}")
            time.sleep(self.RETRY_WAIT)


    def initiate_trade(self, symbol, order_type, terminate_trade):
        """Initiate a trade for the given symbol with synchronization."""
        try:
            # Lock to prevent multiple threads from trading the same symbol simultaneously
            with self.lock:
                if order_type.lower() == "buy" and not self._is_asset_being_traded(symbol):
                    current_price = self._get_current_price(symbol)
                    account = self._get_account()
                    total_funds = float(account.buying_power)
                    if total_funds * self.MAX_TOTAL_PERCENTAGE <= sum(float(pos.market_value) for pos in self.api.list_positions()):
                        return "Max active trade funds limit reached", 402
                    qty = self._calculate_qty_to_trade(current_price, total_funds, symbol)
                    actual_purchase_price = round(round(qty, 5) * current_price, 1)
                    allowable_purchase_per_trade = round(total_funds * self.MAX_SINGLE_TRADE_PERCENTAGE, 1)
                    if actual_purchase_price > allowable_purchase_per_trade or qty == 0:
                        return "Trade exceeds limit", 403
                    stop_loss = current_price - (current_price * 0.01)
                    take_profit = current_price + (self.profit_loss_ratio * (current_price - stop_loss))
                    buy_order = self.api.submit_order(symbol=symbol, qty=round(qty, 5), side='buy', type='market', time_in_force='gtc')
                    try:
                        self.purchase_price[symbol] = self.get_entry_price(symbol)
                    except:
                        pass
                    if buy_order.status == 'rejected':
                        try:
                            self.purchase_price.pop(symbol)
                        except:
                            pass
                        return f"Buy order for {symbol} rejected: {buy_order.rejected_reason}", 404
                    threading.Thread(target=self._monitor_and_execute, args=(symbol, round(take_profit, 5), round(stop_loss, 5))).start()
                    return f"Order submitted for {self._get_quantity(symbol)} of {symbol} .. take profit at {round(take_profit, 5)} stop loss at {round(stop_loss, 5)}", 200
                elif order_type.lower() == "sell" and self._is_asset_being_traded(symbol):
                    entry_price = round(self.get_entry_price(symbol), 5)
                    if round(self._get_current_price(symbol), 5) > (entry_price + self.MIN_EXIT_PRICE) or int(terminate_trade) == 1:
                        threading.Thread(target=self._close_order, args=(symbol,)).start()
                        return f"SOLD ( on a Sell Signal ) ... {symbol} @  Current_Price = {round(self._get_current_price(symbol), 5)} > entry_Price {entry_price} + min_exit_price {self.MIN_EXIT_PRICE} = {entry_price + self.MIN_EXIT_PRICE}", 200
                    else:
                        return f"Trade was not closed on a Sell Signal because ... {symbol} @ Current_Price = {round(self._get_current_price(symbol), 5)} < @ Entry_Price {entry_price} + min_exit_price {self.MIN_EXIT_PRICE} = {entry_price + self.MIN_EXIT_PRICE}", 200
                else:
                    return f"Asset {symbol} is already being traded .. skipping buying another {symbol}", 401
        except Exception as e:
            print(f'Error 405 --> {e}')
            return f"Error: {e}", 405