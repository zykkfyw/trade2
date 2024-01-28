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
    
    def _get_account(self):
        return self.account

    def _get_current_price(self, symbol):
        """Get the current price of a symbol."""
        try:
            quote = self.api.get_bars(symbol, TimeFrame.Minute, limit=1).df.iloc[-1]['close']
            return quote
        except:
            # A GET request to the API
            response = requests.get("https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes?symbols=" + symbol).text
            quote = json.loads(response).get('quotes').get(symbol).get('ap')
            return quote

    def _is_asset_being_traded(self, symbol):
        # Fetch the current quantity of the asset
        qty = 0
        try:
            # check if asset is already being traded
            current_positions = self.api.list_positions()
            for pos in current_positions:
                if symbol.lower().replace("/", "") == pos._raw.get("symbol").lower():
                    return True
            return False
        except:
            return False

    def _get_quanity(self, symbol):
        # Fetch the current quantity of the asset
        try:
            current_positions = self.api.list_positions()
            for pos in current_positions:
                if symbol.lower().replace("/", "") == pos._raw.get("symbol").lower():
                    qty = pos._raw.get("qty")
                    return float(qty)
        except:
            return qty 

    def _get_quanity(self, symbol):
        # Fetch the current quantity of the asset
        try:
            current_positions = self.api.list_positions()
            for pos in current_positions:
                if symbol.lower().replace("/", "") == pos._raw.get("symbol").lower():
                    qty = pos._raw.get("qty")
                    return float(qty)
        except:
            return qty  

    def _close_order(self, symbol):
        # Close a order
        try:
            while 1:
                qty = self._get_quanity(symbol)
                if self._is_asset_being_traded(symbol) == True:
                    entry_price = round(self.get_entry_price(symbol),5)
                    if round(( self._get_current_price(symbol),5)  > ( entry_price + self.MIN_EXIT_PRICE )): 
                        sell_order = self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
                if self._is_asset_being_traded(symbol) == False:
                    self.purchase_price.pop(symbol)
                    print(f"SOLD ... {symbol} @  Current_Price = {round(self._get_current_price(symbol),5)} on a Sell Signal")
                    break
                time.sleep(self.RETRY_WAIT)
        except Exception as e:
            print(f'An error occurred closing ... {symbol}  : {e}')
            return f"An error occurred closing ... {symbol}  : {e}", 407 

    def _calculate_qty_to_trade(self, current_price, total_funds, symbol):
        """Calculate the quantity to trade based on available funds and price."""
        max_trade_funds = total_funds * self.MAX_SINGLE_TRADE_PERCENTAGE
        #qty = int(max_trade_funds / current_price)
        qty = max_trade_funds / current_price
        # Check if fractional trading is supported and adjust quantity accordingly
        if self.api.get_asset(symbol).fractionable:
            if self.api.get_asset(symbol)._raw.get("class").lower() == "crypto":
                return qty  # Return fractional quantity for assets that support it
            else:
                return int(qty)
        else:
            return int(qty)  # Return whole number for assets that don't support fractional trading

    def load_existing_trades(self):
        # Fetch the current quantity of the asset
        try:
            current_positions = self.api.list_positions()
            for pos in current_positions:
                symbol = pos._raw.get("symbol")
                if pos._raw.get("asset_class").lower() == "crypto":
                    symbol = symbol.replace("USD", "/USD")
                current_price = pos._raw.get("current_price")
                entry_price =  float(current_price) + float(pos._raw.get("unrealized_pl"))
                try:
                    self.purchase_price[symbol] = entry_price
                except:
                    pass
                stop_loss = entry_price - (entry_price * 0.01)
                take_profit = entry_price + (float(self.profit_loss_ratio) * (entry_price - stop_loss))
                # Start a thread to monitor and execute the sell order
                threading.Thread(target=self._monitor_and_execute, args=(symbol, round(take_profit,5), round(stop_loss,5))).start()
                print(f"AAdded an Existing order of {self._get_quanity(symbol)} units of {symbol} .. is being monitored -- profit at {round(take_profit,5)}  stop loss at {round(stop_loss,5)}")
        except Exception as e:
            return f"Error: {e}", 406 

    def get_entry_price(self, symbol):
        entry_price = 0
        # Fetch the current quantity of the asset
        try:
            current_positions = self.api.list_positions()
            for pos in current_positions:
                symbol = pos._raw.get("symbol")
                if symbol.lower() == pos._raw.get("symbol").replace("/", "").lower():    
                    current_price = pos._raw.get("current_price")
                    entry_price =  float(current_price) + float(pos._raw.get("unrealized_pl"))
                    return round(entry_price,5)
                            
            if entry_price == 0:
                return round(self._get_current_price(symbol),5)
       
        except Exception as e:
            return f"Error: {e}", 406 
        

    def _monitor_and_execute(self, symbol, take_profit, stop_loss):
        """Monitor price and execute sell order based on conditions."""
        time.sleep(self.RETRY_WAIT)
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                #Exit the thread if the position was closed
                if self._is_asset_being_traded(symbol) == False:
                    print(f"{symbol} ---> The position is no longer being traded ...Stopping the monitoring")
                    try:
                        self.purchase_price.pop(symbol)
                    except:
                        pass
                    break

                current_price = self._get_current_price(symbol)
                print(f"Checking ... {symbol} ---> Current_Price = {round(current_price,5)} Take_Profit = {round(take_profit,5)} Stop_Loss = {round(stop_loss,5)}")
                try:
                    self.purchase_price[symbol] = self.get_entry_price(symbol)
                except:
                    pass
                if round(current_price,5) >= round(take_profit,5) or round(current_price,5) <= round(stop_loss,5):
                    if round(current_price,5) >= round(take_profit,5):
                        profit_loss = "PROFIT"
                    else:
                        profit_loss = "LOSS"
                    # Fetch the current quantity of the asset
                    qty = self._get_quanity(symbol)
                    print(f"Selling @ ( {profit_loss} ) ... {symbol} ---> Current_Price = {round(current_price,5)} Take_Profit = {round(take_profit,5)} Stop_Loss = {round(stop_loss,5)}")
                    sell_order = self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
                    if sell_order.status == 'filled':
                        print(f"SOLD @ ( {profit_loss} )... {symbol} ---> Current_Price = {round(current_price,5)} Take_Profit = {round(take_profit,5)} Stop_Loss = {round(stop_loss,5)}")
                        try:
                            self.purchase_price.pop(symbol)
                        except:
                            pass
                        break
            except Exception as e:
                print(f"Error with sell order for {symbol}: {e}")
            #retries += 1
            time.sleep(self.RETRY_WAIT)


    def initiate_trade(self, symbol, type, terminate_trade):
        """Initiate a trade for the given symbol."""
        try:
            print(f'Check point 1')
            # Only Buy or Sell order types can be accepted
            if type.lower() != "buy" and type.lower() != "sell":
                return f"{type.upper()} is not a valid order type. Use Buy or Sell as order type!", 400
            print(f'Check point 2')
            # Check if the symbol is already being traded. Is triggerd by a sell symbol Stop the trade
            
            if (self._is_asset_being_traded(symbol)) or (symbol in self.purchase_price):
                if type.lower() == "sell":
                    print(f"Check point 1.1")
                    entry_price = round(self.get_entry_price(symbol),5)
                    if round(( self._get_current_price(symbol),5)  > ( entry_price + self.MIN_EXIT_PRICE )) or int(terminate_trade) == 1:
                        threading.Thread(target=self._close_order, args=(symbol, self._get_quanity(symbol))).start()
                        return f"SOLD ( on a Sell Signal ) ... {symbol} @  Current_Price = {round(self._get_current_price(symbol),5)} > entry_Price {entry_price} + min_exit_price  {self.MIN_EXIT_PRICE}  = {entry_price + self.MIN_EXIT_PRICE}", 200
                    else:
                        return f"Trade was not closed on a Sell Signal because ... {symbol} @ Current_Price = {round(self._get_current_price(symbol),5)} < @ Entry_Price {entry_price} + min_exit_price  {self.MIN_EXIT_PRICE}  = {entry_price + self.MIN_EXIT_PRICE}", 200 
                else:
                     return f"Asset {symbol} is already being traded .. skipping buying another {symbol}", 401    
            print(f'Check point 3')
            #Only Buy orders are being processed  at this time
            if type.lower() != "buy":
                return f"{symbol} {type.upper()} order was not processed  - Only BUY orders can be processed at this time!!", 200
            print(f'Check point 4')
            current_price = self._get_current_price(symbol)
            print(f'Check point 5')
            account = self._get_account()
            print(f'Check point 6')
            total_funds = float(account.buying_power)
            print(f'Check point 7')
            if total_funds * self.MAX_TOTAL_PERCENTAGE <= sum(float(pos.market_value) for pos in self.api.list_positions()):
                return "Max active trade funds limit reached", 402
            print(f'Check point 8')
            qty = self._calculate_qty_to_trade(current_price, total_funds, symbol)
            print(f'Check point 9')
            actual_purchace_price = round(round(qty,5) * current_price,1)
            allowable_purchase_per_trade = round(total_funds * self.MAX_SINGLE_TRADE_PERCENTAGE,1)
            if ( actual_purchace_price > allowable_purchase_per_trade) or ( qty == 0 ):
                return "Trade exceeds limit", 403
            print(f'Check point 10')
            stop_loss = current_price - (current_price * 0.01)
            take_profit = current_price + (self.profit_loss_ratio * (current_price - stop_loss))
            print(f'Check point 11')
            # Place the order
            buy_order = self.api.submit_order(symbol=symbol, qty=round(qty,5), side='buy', type='market', time_in_force='gtc')
            print(f'Check point 12')
            try:
                self.purchase_price[symbol] = self.get_entry_price(symbol)
            except:
                pass
            print(f'Check point 13')
            if buy_order.status == 'rejected':
                try:
                    self.purchase_price.pop(symbol)
                except:
                    pass
                return f"Buy order for {symbol} rejected: {buy_order.rejected_reason}", 404
            print(f'Check point 14')
            # Start a thread to monitor and execute the sell order
            threading.Thread(target=self._monitor_and_execute, args=(symbol, round(take_profit,5), round(stop_loss,5))).start()
            print(f'Check point 15')
            return f"Order submitted for {self._get_quanity(symbol)} of {symbol} .. take profit at {round(take_profit,5)}  stop loss at {round(stop_loss,5)}", 200
        except Exception as e:
            print(f'Error 405 --> {e}')
            return f"Error: {e}", 405