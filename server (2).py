"""
Monte Carlo Options Pricer — Flask Backend
Deploy to Railway: https://railway.app
"""

import os
import traceback
import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf

app = Flask(__name__)

# Allow all origins — required for file:// HTML and GitHub Pages
CORS(app, resources={r"/*": {"origins": "*"}})


@app.after_request
def add_cors_headers(response):
    """Belt-and-braces CORS — ensures headers are always present."""
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/", methods=["GET", "OPTIONS"])
def health():
    return jsonify({"status": "ok", "message": "Monte Carlo Options API is running"})


@app.route("/api/stock", methods=["GET", "OPTIONS"])
def get_stock():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    ticker = request.args.get("ticker", "").upper().strip()
    if not ticker:
        return jsonify({"error": "No ticker provided"}), 400

    try:
        stock = yf.Ticker(ticker)
        info  = stock.fast_info
        price = (
            getattr(info, "last_price", None)
            or getattr(info, "previous_close", None)
        )

        if price is None:
            full  = stock.info
            price = (
                full.get("currentPrice")
                or full.get("regularMarketPrice")
                or full.get("previousClose")
            )

        if not price:
            return jsonify({"error": f"Could not fetch price for '{ticker}'. Check the ticker is valid."}), 404

        try:
            name     = stock.info.get("longName") or stock.info.get("shortName") or ticker
            currency = stock.info.get("currency", "USD")
        except Exception:
            name     = ticker
            currency = "USD"

        return jsonify({
            "ticker":   ticker,
            "price":    round(float(price), 2),
            "name":     name,
            "currency": currency,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error fetching {ticker}: {str(e)}"}), 500


@app.route("/api/options", methods=["GET", "OPTIONS"])
def get_options():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    ticker   = request.args.get("ticker", "").upper().strip()
    expiry   = request.args.get("expiry", None)
    opt_type = request.args.get("type", "calls").lower()

    if not ticker:
        return jsonify({"error": "No ticker provided"}), 400

    try:
        stock    = yf.Ticker(ticker)
        expiries = list(stock.options)

        if not expiries:
            return jsonify({"error": f"No options data available for '{ticker}'."}), 404

        selected = expiry if (expiry and expiry in expiries) else expiries[0]
        chain    = stock.option_chain(selected)
        df       = chain.calls if opt_type == "calls" else chain.puts

        rows = []
        for _, row in df.iterrows():
            try:
                rows.append({
                    "strike":       round(float(row["strike"]), 2),
                    "lastPrice":    round(float(row.get("lastPrice")  or 0), 4),
                    "bid":          round(float(row.get("bid")        or 0), 4),
                    "ask":          round(float(row.get("ask")        or 0), 4),
                    "impliedVol":   round(float(row.get("impliedVolatility") or 0), 4),
                    "volume":       int(row.get("volume")       or 0),
                    "openInterest": int(row.get("openInterest") or 0),
                    "inTheMoney":   bool(row.get("inTheMoney",  False)),
                })
            except Exception:
                continue

        return jsonify({
            "ticker":   ticker,
            "expiry":   selected,
            "type":     opt_type,
            "expiries": expiries[:12],
            "options":  rows,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error fetching options for {ticker}: {str(e)}"}), 500


@app.route("/api/volatility", methods=["GET", "OPTIONS"])
def get_volatility():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    ticker = request.args.get("ticker", "").upper().strip()
    if not ticker:
        return jsonify({"error": "No ticker provided"}), 400

    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="1y")

        if hist.empty:
            return jsonify({"error": f"No price history found for '{ticker}'."}), 404

        log_returns = np.log(hist["Close"] / hist["Close"].shift(1)).dropna()
        daily_vol   = float(log_returns.std())
        annual_vol  = round(daily_vol * np.sqrt(252), 4)

        return jsonify({
            "ticker":       ticker,
            "annualVol":    annual_vol,
            "dailyVol":     round(daily_vol, 6),
            "observations": len(log_returns),
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error computing volatility for {ticker}: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Monte Carlo Options API running -> http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
