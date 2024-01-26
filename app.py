import os
from flask import Flask, request
from trading_bot import TradingBot  # Assuming TradingBot is in a separate file named trading_bot.py


# Alpaca-py API Key
api_key = os.environ.get("APCA_API_KEY_ID") #'PK0OETIBZ3DNA8NI2NAQ'
api_secret = os.environ.get("APCA_API_SECRET_KEY") #'QfyY3c3ehhyyElBNLyiPmWfJqTvXiQaNLIGfKaz6'
api_base_url = os.environ.get("APCA_API_BASE_URLclear") #'https://paper-api.alpaca.markets'

app = Flask(__name__)

# Initialize trading bot with API credentials and base URL
trading_bot = TradingBot(api_key, api_secret, api_base_url)
trading_bot.load_existing_trades()

@app.route('/trade', methods=['POST'])
def trade():
    """Handle trade requests."""
    data = request.json
    symbol = data.get('symbol')
    type = data.get('type')
    terminate_trade = data.get('terminate')
    if not symbol:
        return "Missing symbol", 400

    print(f"Symbol = {symbol} type = {type} terminate = {terminate_trade}")

    # Initiate the trade using the trading bot
    response, status_code = trading_bot.initiate_trade(symbol, type, terminate_trade)
    return response, status_code

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=5000)
    #app.run(port=80, host='0.0.0.0', debug=True)