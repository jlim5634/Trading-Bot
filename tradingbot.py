from lumibot.brokers import Alpaca
from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies.strategy import Strategy
from lumibot.traders import Trader
from datetime import datetime, timedelta 
from alpaca_trade_api import REST 
from finbert_utils import estimate_sentiment
import math
import logging

API_KEY="PKTZQ676PWSMIM1KGC2T" 
API_SECRET="Z48aCwy4BKvRtSTyYXOdqCNqMhIYrTDp1Fper9sK" 
BASE_URL="https://paper-api.alpaca.markets/v2"

ALPACA_CREDS = {
    "API_KEY":API_KEY, 
    "API_SECRET": API_SECRET, 
    "PAPER": True
}

class MLTrader(Strategy): 
    def initialize(self, symbol:str="SPY", cash_at_risk:float=.5): 
        self.symbol = symbol #makes self.symbol represent the stock (SPY)
        self.position = 0
        self.sleeptime = "1m" #how often the bot trades
        self.last_trade = None 
        self.stop_loss_pct = 0.01
        self.take_profit_pct = 0.015
        self.cash_at_risk = cash_at_risk #makes the variable represent the cash_at_risk
        self.api = REST(base_url=BASE_URL, key_id=API_KEY, secret_key=API_SECRET) #allows for direct API calls
        logging.basicConfig(level=logging.INFO)

    def position_sizing(self): #calculates how many shares to buy/sell
        cash = self.get_cash() #gets available cash from account
        last_price = self.get_last_price(self.symbol) #gets last traded price of self.symbol
        raw_quantity = (cash * self.cash_at_risk) / last_price if last_price and last_price > 0 else 0
        quantity = max(0, int(math.floor(raw_quantity))) #calculates number of shares to trade
        return cash, last_price, quantity

    def get_dates(self): #computes today and 3 days before
        today = self.get_datetime() 
        three_days_prior = today - timedelta(days=3) 
        return today.strftime('%Y-%m-%d'), three_days_prior.strftime('%Y-%m-%d') #returns date in string format (2025-5-10) for API reading

    def get_sentiment(self): #fetches news for stock and gets sentiment
        today, three_days_prior = self.get_dates() #gets the date range for the news based on trading timeline
        try:
            news = self.api.get_news(symbol=self.symbol, #
                                 start=three_days_prior, 
                                 end=today) 
        except Exception as e:
            logging.exception("ERROR fetching news") #logs error details
            return 0.0, "neutral" #fallback values so trading loop still runs
        headlines = []
        for ev in news:
            try:
                raw = getattr(ev, "_raw", None) or ev.__dict__.get("_raw")
                if raw and "headline" in raw:
                    headlines.append(raw["headline"])
            except Exception:
                continue
        if not headlines: 
            return 0.0, "neutral" #if no headlines, returns neutral
      
        probability, sentiment = estimate_sentiment(headlines) #passes the list of headline string of the news to method 
        return probability, sentiment #returns estimated probability and sentiment from finbert

    def on_trading_iteration(self): #called on each trade/iteration. Based on the sleeptime
        current_price = self.get_latest_price(self.symbol)
        cash, last_price, quantity = self.position_sizing() #recomputes the three on each iteration
        
        if quantity <= 0 or last_price is None: #skips trading if no shares can be bought
            logging.info("Not enough cash or no price data; skipping trade")
            return

        probability, sentiment = self.get_sentiment() #gets latest sentiment and probability

        if sentiment == "positive" and probability > .6: 
            if self.last_trade == "sell": 
                self.close_positions(self.symbol) #if last trade was sell, it closes position (smart thing to do)
            order = self.create_order( #creates object to BUY quantity shares with a brakcet
                self.symbol, 
                quantity, 
                "buy", 
                type="bracket", 
                take_profit_price=last_price*1.20, #take profit at 20%
                stop_loss_price=last_price*.95 #stop-loss -5%
            )
            self.submit_order(order) #submits order to broker
            self.last_trade = "buy" #records that lat trade was a "buy"
        elif sentiment == "negative" and probability > .6: 
            if self.last_trade == "buy": 
                self.close_positions(self.symbol) 
            order = self.create_order(
                self.symbol, 
                quantity, 
                "sell", 
                type="bracket", 
                take_profit_price=last_price*.8, #profit target is 20% below entry
                stop_loss_price=last_price*1.05 #stop-loss 5% above entry
            )
            self.submit_order(order) 
            self.last_trade = "sell"

start_date = datetime(2025,1,5) #start date
end_date = datetime(2025,4,1) #end_date
broker = Alpaca(ALPACA_CREDS) 
strategy = MLTrader(name='mlstrat', broker=broker, 
                    parameters={"symbol":"SPY", 
                                "cash_at_risk":.5})
strategy.backtest( #runs backtest from yfinance 
    YahooDataBacktesting, 
    start_date, 
    end_date, 
    parameters={"symbol":"SPY", "cash_at_risk":.5}
)