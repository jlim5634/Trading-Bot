import csv
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import OrderStatus
from datetime import datetime, time



# -------------------------
# Alpaca API credentials
# -------------------------
API_KEY = "PKTZQ676PWSMIM1KGC2T"
API_SECRET = "Z48aCwy4BKvRtSTyYXOdqCNqMhIYrTDp1Fper9sK"

now = datetime.now()
current_time = now.time()
current_day = now.strftime("%A")

market_open = time(6, 30)
market_close = time(13, 0)

# Connect to paper account + WebSocket
api = TradingClient(API_KEY, API_SECRET, paper=True)
stream = TradingStream(API_KEY, API_SECRET, paper=True)


trade_data = {"cost": None, "qty": None, "symbol": None}

if current_time < market_open or current_time > market_close or current_day in ["Saturday", "Sunday"]:
    current_time = now.strftime("%H:%M")
    print("\nMarket is closed. Can only trade from 6:30 - 13:00 , Mon-Fri")
    print(f"Current time and day is {current_time} {current_day}\n")
    quit()
else:
    print("Market is open, you can trade")

    request_params = GetOrdersRequest(status="open", limit=50)
    open_orders = api.get_orders(request_params)
    for o in open_orders:
        api.cancel_order(o.id)
        print(f"Cancelled old order {o.id}")

    # Track order IDs
    buy_order = None
    sell_order = None
    csv_file = "trade_history.csv"

    with open(csv_file, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Datetime", "Symbol", "Side", "Quantity", "Price", "Total", "P/L"])

    def log_trade(symbol, side, qty, price, total, profit_loss=""):
        with open (csv_file, mode="a", newline='') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now(), symbol, side, qty, f"{price:.2f}", f"{total:.2f}", f"{profit_loss:.2f}" if profit_loss != ""else""])

    # -------------------------
    # Event handler for order updates
    # -------------------------
    async def on_order_update(data):
        global buy_order, sell_order
        order = data.order
        print(f"🔔 Order update: {data.event} | ID: {order.id} | Status: {order.status}")

        if order.status == "filled" and order.side == "buy":
            print(f"✅ Buy filled: {order.qty} shares of {order.symbol} at ${order.filled_avg_price}")
            total_cost = float(order.qty) * float(order.filled_avg_price)
            trade_data["cost"] = total_cost
            trade_data["qty"] = float(order.qty)
            trade_data["symbol"] = order.symbol
            print(f" Total cost: ${total_cost:.2f} | Filled at: {order.filled_at}")

            log_trade(order.symbol, "BUY", order.qty, float(order.filled_avg_price), total_cost)

            sell_order_data = MarketOrderRequest(
                symbol="SPY",
                qty=1,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC
            )
            sell_order = api.submit_order(sell_order_data)
            print(f"✅ Sell order submitted for {order.qty} {order.symbol}. ID: {sell_order.id}")

        elif order.status == "filled" and order.side == "sell":
            proceeds = float(order.qty) * float(order.filled_avg_price)
            print(f" Sell filled: {order.qty} shares of {order.symbol} at ${order.filled_avg_price}")
            print(f" Total Proceeds: ${proceeds:.2f} | Filled at {order.filled_at}")

            profit_loss=0
            if trade_data["cost"] is not None:
                profit_loss = proceeds - trade_data["cost"]
                print(f"Trade complete! P/L: ${profit_loss:.2f}")
            else:
                print("Could not calculate P/L (buy cost not recorded)")

            log_trade(order.symbol, "SELL", order.qty, float(order.filled_avg_price), proceeds, profit_loss)


    # Subscribe to trade updates
    stream.subscribe_trade_updates(on_order_update)

    # -------------------------
    # Submit BUY order
    # -------------------------
    buy_order_data = MarketOrderRequest(
        symbol="SPY",
        qty=1,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.GTC
    )
    buy_order = api.submit_order(buy_order_data)
    print(f"✅ Buy order submitted: {buy_order.qty} {buy_order.symbol}")

    # -------------------------
    # Start WebSocket listener
    # -------------------------
    print("Waiting for order updates...")
    stream.run()

    start_date = datetime(2025, 3, 20)
    end_date = datetime(2025, 4,18)
