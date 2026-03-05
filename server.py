"""
Monte Carlo Options Pricer — Flask Backend
Deploy to Railway: https://railway.app
"""

import os
import traceback
from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import numpy as np

app = Flask(__name__)

# Allow requests from any origin (needed for GitHub Pages / file:// HTML)
CORS(app, origins="*")


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "Monte Carlo Options API is running"})


@app.route("/api/stock", methods=["GET"])
def get_stock():
    ticker = request.args.get("ticker", "").upper().strip()
    if not ticker:
        return jsonify({"error": "No ticker provided"}), 400
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        if price is None:
            return jsonify({"error": f"Could not fetch price for {ticker}"}), 404
        return jsonify({
            "ticker":   ticker,
            "price":    round(float(price), 2),
            "name":     info.get("longName") or info.get("shortName") or ticker,
            "currency": info.get("currency", "USD"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/options", methods=["GET"])
def get_options():
    ticker  = request.args.get("ticker", "").upper().strip()
    expiry  = request.args.get("expiry", None)
    opt_type = request.args.get("type", "calls").lower()
    if not ticker:
        return jsonify({"error": "No ticker provided"}), 400
    try:
        stock    = yf.Ticker(ticker)
        expiries = list(stock.options)
        if not expiries:
            return jsonify({"error": f"No options available for {ticker}"}), 404
        selected = expiry if (expiry and expiry in expiries) else expiries[0]
        chain = stock.option_chain(selected)
        df    = chain.calls if opt_type == "calls" else chain.puts
        rows  = []
        for _, row in df.iterrows():
            rows.append({
                "strike":       round(float(row["strike"]), 2),
                "lastPrice":    round(float(row.get("lastPrice", 0)), 4),
                "bid":          round(float(row.get("bid", 0)), 4),
                "ask":          round(float(row.get("ask", 0)), 4),
                "impliedVol":   round(float(row.get("impliedVolatility", 0)), 4),
                "volume":       int(row.get("volume", 0) or 0),
                "openInterest": int(row.get("openInterest", 0) or 0),
                "inTheMoney":   bool(row.get("inTheMoney", False)),
            })
        return jsonify({
            "ticker":   ticker,
            "expiry":   selected,
            "type":     opt_type,
            "expiries": expiries[:12],
            "options":  rows,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/volatility", methods=["GET"])
def get_volatility():
    ticker = request.args.get("ticker", "").upper().strip()
    if not ticker:
        return jsonify({"error": "No ticker provided"}), 400
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="1y")
        if hist.empty:
            return jsonify({"error": f"No history for {ticker}"}), 404
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
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Monte Carlo Options API running on port {port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
