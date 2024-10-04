import numpy as np
import yfinance as yf


# 基本面資料
def stock_fundamental(stock_id="大盤"):
  if stock_id == "大盤":
      return None

  stock_id += ".TW"
  stock = yf.Ticker(stock_id)

  # 營收成長率
  quarterly_revenue_growth = np.round(
      stock.quarterly_financials.loc["Total Revenue"].pct_change(-1).dropna().tolist(), 2)

  # 檢查是否存在 "Reported EPS" 欄位
  if "Reported EPS" in stock.get_earnings_dates().columns:
      # 每季EPS
      quarterly_eps = np.round(
          stock.get_earnings_dates()["Reported EPS"].dropna().tolist(), 2)

      # EPS季增率
      quarterly_eps_growth = np.round(
          stock.get_earnings_dates()["Reported EPS"].ffill().pct_change(-1).dropna().tolist(), 2)
  else:
      quarterly_eps = [None] * 3
      quarterly_eps_growth = [None] * 3

  # 轉換日期
  dates = [
      date.strftime('%Y-%m-%d') for date in stock.quarterly_financials.columns
  ]

  data = {
      '季日期': dates[:len(quarterly_revenue_growth)],
      '營收成長率': quarterly_revenue_growth.tolist(),
      'EPS': quarterly_eps[0:3],
      'EPS 季增率': quarterly_eps_growth[0:3]
  }

  return data


