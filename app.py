import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- 1. 網頁設定與狀態初始化 ---
st.set_page_config(page_title="多檔股息月曆", page_icon="📅", layout="wide")

# 初始化 Session State 來儲存股票清單
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

# --- 2. 側邊欄：新增股票 ---
with st.sidebar:
    st.header("➕ 新增股票到投組")
    
    # 預設值改為 0050 方便測試
    input_ticker = st.text_input("股票代碼", value="0050", help="台股請輸入數字 (如 2330)，美股輸入代號 (如 AAPL)")
    input_shares = st.number_input("持有股數", min_value=1, value=1000, step=100)
    
    col1, col2 = st.columns(2)
    
    if col1.button("加入清單", type="primary"):
        # 簡單的代碼處理
        ticker_clean = input_ticker.strip().upper()
        if ticker_clean.isdigit():
            ticker_clean = f"{ticker_clean}.TW"
            
        # 檢查是否重複
        if any(d['symbol'] == ticker_clean for d in st.session_state.portfolio):
            st.warning(f"{ticker_clean} 已經在清單中囉！")
        else:
            st.session_state.portfolio.append({
                "symbol": ticker_clean,
                "shares": input_shares
            })
            st.success(f"已新增 {ticker_clean}")

    if col2.button("清空全部"):
        st.session_state.portfolio = []
        st.rerun()

    # 顯示目前清單
    st.divider()
    st.subheader(f"目前追蹤 ({len(st.session_state.portfolio)})")
    if st.session_state.portfolio:
        portfolio_df = pd.DataFrame(st.session_state.portfolio)
        st.dataframe(portfolio_df, hide_index=True, use_container_width=True)
    else:
        st.info("目前清單為空")

# --- 3. 核心邏輯：計算多檔股票 (已修正時區問題) ---
def calculate_portfolio_dividends(portfolio_list):
    all_payouts = []
    
    # [修正點 1] 設定基準時間為 UTC，確保有時區資訊
    end_date = pd.Timestamp.now(tz='UTC')
    start_date = end_date - pd.DateOffset(months=12)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, item in enumerate(portfolio_list):
        symbol = item['symbol']
        shares = item['shares']
        
        status_text.text(f"正在處理: {symbol} ...")
        
        try:
            stock = yf.Ticker(symbol)
            divs = stock.dividends
            
            if not divs.empty:
                # [修正點 2] 統一處理 yfinance 回傳的時間索引
                # 如果資料沒有時區 (tz-naive)，加上 UTC
                if divs.index.tz is None:
                    divs.index = divs.index.tz_localize('UTC')
                else:
                    # 如果資料已有時區 (tz-aware)，轉成 UTC 以便統一比較
                    divs.index = divs.index.tz_convert('UTC')
                
                # 進行篩選
                recent_divs = divs[divs.index >= start_date]
                
                for date, amount in recent_divs.items():
                    # 取得月份 (1-12)
                    month = date.month
                    payout = amount * shares
                    
                    all_payouts.append({
                        "Symbol": symbol,
                        "Month": month,
                        "Amount": payout,
                        "PayDate": date.strftime('%Y-%m-%d')
                    })
            else:
                st.toast(f"⚠️ {symbol} 查無配息紀錄")
                
        except Exception as e:
            st.error(f"讀取 {symbol} 失敗: {e}")
            
        # 更新進度條
        progress_bar.progress((idx + 1) / len(portfolio_list))
        
    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(all_payouts)

# --- 4. 主畫面顯示 ---
st.title("📅 投資組合股息月曆")
st.caption("計算邏輯：基於**過去 12 個月**的實際配息紀錄，推算若持有相同股數，各月份可領取的金額。")

if not st.session_state.portfolio:
    st.warning("👈 請先在左側側邊欄新增股票代碼！")
else:
    if st.button("開始計算分析 🚀", use_container_width=True):
        with st.spinner("正在分析投資組合..."):
            df_result = calculate_portfolio_dividends(st.session_state.portfolio)
            
            if df_result.empty:
                st.warning("這段期間內，您的投資組合似乎沒有任何配息紀錄。")
            else:
                # --- 資料處理：轉置成 月份表 ---
                # 建立 1~12 月的完整結構
                months_range = list(range(1, 13))
                
                # Pivot Table: Index=股票, Columns=月份, Values=金額
                pivot_df = df_result.pivot_table(
                    index='Symbol', 
                    columns='Month', 
                    values='Amount', 
                    aggfunc='sum',
                    fill_value=0
                )
                
                # 補齊缺失的月份 (確保 1-12 月都有)
                for m in months_range:
                    if m not in pivot_df.columns:
                        pivot_df[m] = 0
                
                # 依照 1~12 月排序
                pivot_df = pivot_df[months_range]
                
                # 加入「單檔年度總計」
                pivot_df['Total'] = pivot_df.sum(axis=1)
                
                # 計算「每月總收入」 (最下面一行 Total)
                monthly_totals = pivot_df.sum(axis=0)
                
                # --- 視覺化呈現 ---
                
                # 1. 關鍵指標
                annual_total = monthly_totals['Total']
                avg_monthly = annual_total / 12
                
                c1, c2 = st.columns(2)
                c1.metric("💰 預估年股息總額", f"${annual_total:,.0f}")
                c2.metric("📅 平均每月被動收入", f"${avg_monthly:,.0f}")
                
                st.divider()
                
                # 2. 每月配息長條圖
                st.subheader("📊 每月領息分佈圖")
                # 準備畫圖資料 (排除最後一個 Total 欄位)
                chart_data = monthly_totals.drop('Total').reset_index()
                chart_data.columns = ['Month', 'Income']
                
                fig = px.bar(
                    chart_data,
                    x='Month',
                    y='Income',
                    text_auto='.2s',
                    title="每月總配息金額",
                    labels={'Income': '金額 ($)', 'Month': '月份'},
                    color='Income',
                    color_continuous_scale='Greens'
                )
                # 強制 X 軸顯示 1-12
                fig.update_layout(xaxis = dict(tickmode = 'linear', tick0 = 1, dtick = 1))
                st.plotly_chart(fig, use_container_width=True)
                
                # 3. 詳細表格 (熱點圖)
                st.subheader("📋 各股每月配息明細表")
                
                # 格式化表格顯示
                st.dataframe(
                    pivot_df.style.format("{:,.0f}").background_gradient(cmap="Greens", axis=None),
                    use_container_width=True,
                    height=400
                )
                
                st.caption("註：表格中的金額為「預估值」，實際配息日與金額請以各公司公告為準。")