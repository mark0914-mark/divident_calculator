import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- 1. 網頁設定與狀態初始化 ---
st.set_page_config(page_title="存股族福音!計算每月幫自己加薪多少", page_icon="📅", layout="wide")

# 初始化 Session State 來儲存股票清單
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

# --- 2. 側邊欄：新增股票與輸入參數 ---
with st.sidebar:
    st.header("➕ 新增股票到投組")
    
    input_ticker = st.text_input("股票代碼", value="0050", help="台股輸入數字或代號(如 0050 or 00679B.TWO)，美股輸入代號(如 AAPL)")
    
    # 單位從「股」改為「仟股」(K Shares)，並允許小數點後三位輸入
    input_k_shares = st.number_input(
        "持有股數 (仟股, K Shares)",
        min_value=0.001,       # 最小輸入值為 0.001 仟股 (即 1 股)
        value=1.000,           # 預設值改為 1 仟股
        step=0.001,            # 步長為 0.001 仟股 (即 1 股)
        format="%.3f"          # 顯示到小數點後三位
    )
    
    # 計算實際股數 (Shares)
    actual_shares = input_k_shares * 1000
    
    col1, col2 = st.columns(2)
    
    if col1.button("加入清單", type="primary"):
        # 步驟 1: 清理並準備代碼
        ticker_clean = input_ticker.strip().upper()
        
        # 步驟 2: 建立最終的搜尋代碼 (Search Symbol)
        search_symbol = ticker_clean
        
        # 判斷是否為台股
        if "." not in search_symbol and search_symbol.isalnum():
            search_symbol = f"{search_symbol}.TW"
        
        # 步驟 3: 檢查是否重複，並加入清單
        if any(d['symbol'] == search_symbol for d in st.session_state.portfolio):
            st.warning(f"{search_symbol} 已經在清單中囉！")
        else:
            st.session_state.portfolio.append({
                "symbol": search_symbol,
                "shares": actual_shares  # 儲存實際股數
            })
            st.success(f"已新增 {search_symbol} ({actual_shares:,.0f} 股)")

    if col2.button("清空全部"):
        st.session_state.portfolio = []
        st.rerun()

    # --- 顯示與移除功能 ---
    st.divider()
    st.subheader(f"目前追蹤 ({len(st.session_state.portfolio)})")
    
    if st.session_state.portfolio:
        
        # 建立表頭
        col_sym_header, col_shares_header, col_del_header = st.columns([0.45, 0.35, 0.20])
        col_sym_header.markdown("**代碼**")
        col_shares_header.markdown("**仟股**")
        col_del_header.markdown("**移除**")
        
        st.markdown("---")
        
        # 迭代清單，為每檔股票添加移除按鈕
        for i, item in enumerate(st.session_state.portfolio):
            symbol = item['symbol']
            shares_k = item['shares'] / 1000 # 轉換為仟股
            
            # 使用 columns 對齊代碼、仟股數和按鈕
            col_sym, col_shares, col_del = st.columns([0.45, 0.35, 0.20])

            col_sym.write(symbol)
            col_shares.write(f"{shares_k:,.3f}") # 格式化為小數點後三位

            # 移除按鈕 (必須使用唯一的 key)
            if col_del.button("❌", key=f"remove_{symbol}_{i}"):
                # 刪除該索引位置的項目
                del st.session_state.portfolio[i]
                st.rerun() # 重新執行腳本以更新顯示
    else:
        st.info("目前清單為空")
# --- 側邊欄結束 ---


# --- 3. 核心邏輯：計算多檔股票 ---
def calculate_portfolio_dividends(portfolio_list):
    all_payouts = []
    
    # 設定基準時間為 UTC
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
                # 統一處理 yfinance 回傳的時間索引
                divs_index = divs.index
                if divs_index.tz is None:
                    divs_index = divs_index.tz_localize('UTC')
                else:
                    divs_index = divs_index.tz_convert('UTC')
                
                divs.index = divs_index
                recent_divs = divs[divs.index >= start_date]
                
                for date, amount in recent_divs.items():
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
            
        progress_bar.progress((idx + 1) / len(portfolio_list))
        
    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(all_payouts)

# --- 4. 主畫面顯示 ---
st.title("📅 每月領息金額 (NTD)")
st.caption("計算邏輯：基於**過去 12 個月**的實際配息紀錄，推算若持有相同股數，各月份可領取的金額。")

if not st.session_state.portfolio:
    st.warning("👈 請先在左側側邊欄新增股票代碼！")
else:
    if st.button("開始計算分析 🚀", use_container_width=True):
        
        df_result = calculate_portfolio_dividends(st.session_state.portfolio)
        
        if df_result.empty:
            st.warning("這段期間內，您的投資組合似乎沒有任何配息紀錄。")
        else:
            # --- 資料處理：轉置成 月份表 ---
            months_range = list(range(1, 13))
            
            pivot_df = df_result.pivot_table(
                index='Symbol', 
                columns='Month', 
                values='Amount', 
                aggfunc='sum',
                fill_value=0
            )
            
            for m in months_range:
                if m not in pivot_df.columns:
                    pivot_df[m] = 0
            
            pivot_df = pivot_df[months_range]
            pivot_df['Total'] = pivot_df.sum(axis=1)
            monthly_totals = pivot_df.sum(axis=0)
            
            # --- 表格加總行 ---
            monthly_totals_row = pd.DataFrame(monthly_totals).T
            monthly_totals_row.index = ['每月總和']
            display_pivot_df = pd.concat([pivot_df, monthly_totals_row])
            
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
            chart_data = monthly_totals.drop('Total').reset_index()
            chart_data.columns = ['Month', 'Income']
            
            # 【修正點】: 更換色階以避免白色
            fig = px.bar(
                chart_data,
                x='Month',
                y='Income',
                text_auto='.2s',
                title="每月總配息金額",
                labels={'Income': '金額 ($)', 'Month': '月份'},
                color='Income',
                color_continuous_scale='algae' 
            )
            fig.update_layout(xaxis = dict(tickmode = 'linear', tick0 = 1, dtick = 1))
            st.plotly_chart(fig, use_container_width=True)
            
            # 3. 詳細表格 (熱點圖)
            st.subheader("📋 各股每月配息明細表")
            
            # 定義 Styler 函數來強調最後一列 (每月總和)
            def highlight_total_row(row):
                if row.name == '每月總和':
                    return ['font-weight: bold; background-color: #dee2e6'] * len(row)
                return [''] * len(row)
            
            # 應用樣式
            styled_df = display_pivot_df.style \
                .format("{:,.0f}") \
                .background_gradient(cmap="Greens", axis=None) \
                .apply(highlight_total_row, axis=1)
                
            st.dataframe(
                styled_df, 
                use_container_width=True,
                height=400
            )
            
            st.caption("註1：表格中的金額為「預估值」，實際配息日與金額請以各公司公告為準。註2：實際領到錢 (Payment Date) 通常會晚 3~5 週。")
