import os
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from dotenv import load_dotenv

load_dotenv()

client = StockHistoricalDataClient(
    api_key=os.environ["ALPACA_API_KEY"],
    secret_key=os.environ["ALPACA_API_SECRET"],
)

quote = client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols="SPY"))
print(quote)
