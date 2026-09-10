from datetime import date, timedelta

import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="PiT-HAF",
    page_icon="📈",
    layout="wide",
)

st.title("PiT-HAF — Financial Agentic AI Platform")
st.caption("Baseline v0.1: Market Data → Agent → Backtest → Evaluation")

with st.sidebar:
    st.header("Cấu hình")

    ticker = st.text_input(
        "Mã cổ phiếu",
        value="AAPL",
    ).strip().upper()

    start_date = st.date_input(
        "Ngày bắt đầu",
        value=date(2024, 1, 1),
    )

    end_date = st.date_input(
        "Ngày kết thúc",
        value=date(2024, 6, 30),
    )

    initial_cash = st.number_input(
        "Vốn ban đầu",
        min_value=1_000,
        value=100_000,
        step=1_000,
    )

    run_button = st.button(
        "Chạy baseline",
        type="primary",
        use_container_width=True,
    )


if not run_button:
    st.info("Thiết lập cấu hình và nhấn **Chạy baseline**.")
    st.stop()

if not ticker:
    st.error("Bạn chưa nhập mã cổ phiếu.")
    st.stop()

if start_date >= end_date:
    st.error("Ngày bắt đầu phải nhỏ hơn ngày kết thúc.")
    st.stop()


with st.spinner(f"Đang tải dữ liệu {ticker}..."):
    prices = yf.download(
        ticker,
        start=start_date,
        end=end_date + timedelta(days=1),
        auto_adjust=True,
        progress=False,
        multi_level_index=False,
    )


if prices.empty:
    st.error(f"Không tìm thấy dữ liệu của {ticker}.")
    st.stop()


close_prices = prices["Close"].dropna()

buy_hold_return = (
    close_prices.iloc[-1] / close_prices.iloc[0] - 1
)

final_value = initial_cash * (1 + buy_hold_return)

metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric("Ticker", ticker)
metric2.metric("Số phiên giao dịch", len(close_prices))
metric3.metric("Buy & Hold", f"{buy_hold_return:+.2%}")
metric4.metric("Giá trị cuối", f"${final_value:,.2f}")

st.subheader("Giá cổ phiếu")
st.line_chart(close_prices)

with st.expander("Dữ liệu thị trường"):
    st.dataframe(
        prices.tail(30),
        use_container_width=True,
    )

st.success(
    "Data layer và frontend đã hoạt động. "
    "Technical Agent sẽ được bổ sung ở bước tiếp theo."
)
