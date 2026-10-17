from datetime import date, datetime, timedelta

import streamlit as st

from pit_haf.data.vnstock_provider import (
    VIETNAM_TZ,
    MarketDataError,
    VietnamMarketDataProvider,
)

st.set_page_config(page_title="PiT-HAF", page_icon="📈", layout="wide")
st.title("PiT-HAF — Phân tích cổ phiếu Việt Nam")
st.caption("Mốc hiện tại: quan sát dữ liệu thị trường. Agentic-RAG và backtest chưa được tích hợp.")

with st.sidebar:
    st.header("Dữ liệu thị trường")
    ticker = st.text_input("Mã cổ phiếu", value="FPT").strip().upper()
    start_date = st.date_input("Ngày bắt đầu", value=date(2024, 1, 1))
    end_date = st.date_input(
        "Ngày kết thúc", value=date(2024, 6, 30),
        max_value=datetime.now(VIETNAM_TZ).date() - timedelta(days=1),
    )
    include_index = st.checkbox("Xem thêm VNINDEX", value=False)
    run_button = st.button("Tải dữ liệu", type="primary", use_container_width=True)

st.warning(
    "Nguồn giá hiện chưa xác minh lịch sử điều chỉnh và thời điểm khả dụng từng phiên bản. "
    "Biểu đồ này chưa phải dữ liệu đầu vào đã kiểm chứng Point-in-Time."
)
if not run_button:
    st.info("Chọn mã cổ phiếu Việt Nam và khoảng ngày, rồi nhấn **Tải dữ liệu**.")
    st.stop()
if not ticker:
    st.error("Bạn chưa nhập mã cổ phiếu.")
    st.stop()
if start_date > end_date:
    st.error("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.")
    st.stop()

provider = VietnamMarketDataProvider()
try:
    with st.spinner(f"Đang tải dữ liệu {ticker} từ Vnstock/KBS..."):
        prices = provider.get_prices(ticker, start_date.isoformat(), end_date.isoformat())
except (MarketDataError, ValueError) as exc:
    st.error(f"Không tải được dữ liệu: {exc}")
    st.stop()

first_close, last_close = prices["close"].iloc[0], prices["close"].iloc[-1]
price_return = last_close / first_close - 1
metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric("Mã cổ phiếu", ticker)
metric2.metric("Số phiên quan sát", len(prices))
metric3.metric("Thay đổi giá đầu/cuối", f"{price_return:+.2%}")
metric4.metric("Giá đóng cửa cuối (VND)", f"{last_close:,.0f}")
st.caption(
    "Thay đổi giá được tính bằng close cuối / close đầu − 1. "
    "Chưa mô phỏng giao dịch, phí, slippage hoặc cổ tức."
)
st.subheader(f"Giá đóng cửa {ticker} (VND/cổ phiếu)")
st.line_chart(prices.set_index("session_date")["close"])
with st.expander("Dữ liệu và nguồn"):
    st.dataframe(prices.tail(30), use_container_width=True)
    st.json(prices.attrs)

if include_index:
    try:
        with st.spinner("Đang tải VNINDEX..."):
            benchmark = provider.get_prices(
                "VNINDEX", start_date.isoformat(), end_date.isoformat(), asset_type="index"
            )
        st.subheader("VNINDEX (điểm chỉ số)")
        st.line_chart(benchmark.set_index("session_date")["close"])
        st.caption(
            "VNINDEX là đối chứng chỉ số, không phải một danh mục có thể mua trực tiếp. "
            "Hai chuỗi chưa được căn chỉnh phiên để tính relative return."
        )
    except (MarketDataError, ValueError) as exc:
        st.error(f"Không tải được VNINDEX: {exc}")
