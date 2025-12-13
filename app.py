import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, timedelta
import time

# --- 1. アプリの設定 ---
st.set_page_config(page_title="アニ無理 制作ノート", layout="wide", page_icon="☕")

# --- 2. デザイン (ミルクティー・クラフト紙風 + 水色バー) ---
st.markdown("""
    <style>
    /* 全体の背景：濃いめの生成り */
    .stApp {
        background-color: #EFEBD6; 
        color: #4A3B2A;
    }
    
    /* 文字色統一：焦げ茶 */
    h1, h2, h3, h4, h5, h6, p, label, span, div, li {
        color: #4A3B2A !important;
        font-family: "Hiragino Mincho ProN", "Yu Mincho", serif;
    }

    /* サイドバー：少し濃い茶色 */
    [data-testid="stSidebar"] {
        background-color: #E6DCCF;
        border-right: 1px solid #C0B2A0;
    }

    /* 入力フォーム等の黒背景対策（念入りに） */
    .stTextInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {
        background-color: #FFFAF0 !important;
        color: #3E2723 !important;
        border: 1px solid #A1887F;
    }
    
    /* 表（データエディタ）の強制白背景化 */
    [data-testid="stDataFrame"] {
        background-color: #FFFAF0 !important;
        border: 1px solid #A1887F;
    }
    
    /* プログレスバー */
    .stProgress > div > div > div {
        background-color: #FFFFFF !important;
    }
    .stProgress > div > div > div > div {
        background-color: #81D4FA !important;
    }

    /* ボタンのデザイン */
    .stButton>button {
        background-color: #D7CCC8;
        color: #3E2723 !important;
        border: 1px solid #8D6E63;
        border-radius: 4px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. スプレッドシート接続機能（キャッシュ付き） ---
@st.cache_resource
def connect_to_gsheets():
    """Google Sheetsに接続（キャッシュで再利用）"""
    try:
        key_dict = json.loads(st.secrets["gcp"]["json_key"])
        creds = Credentials.from_service_account_info(key_dict, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)
        sheet_url = st.secrets["SPREADSHEET_URL"]
        return client.open_by_url(sheet_url).sheet1
    except Exception as e:
        st.error(f"Google Sheets接続エラー: {e}")
        return None

def load_data_from_sheet(sheet):
    """シートからデータを読み込み（土日を自動除外）"""
    if sheet is None:
        return None
    try:
        time.sleep(0.5)
        data = sheet.get_all_records()
        if not data:
            return None
        df = pd.DataFrame(data)
        
        if "台本" in df.columns and "台本メモ" not in df.columns:
            df = df.rename(columns={"台本": "台本メモ"})
        
        df = df[~df["曜日"].isin(["(土)", "(日)"])].reset_index(drop=True)
        df["No"] = range(1, len(df) + 1)
        
        return df
    except Exception as e:
        st.warning(f"データ読み込みエラー: {e}")
        return None

def save_data_to_sheet(sheet, df):
    """データをシートに保存"""
    if sheet is None:
        st.error("シート接続がありません")
        return False
    try:
        time.sleep(0.5)
        sheet.clear()
        save_df = df.copy()
        if "台本メモ" in save_df.columns:
            save_df = save_df.rename(columns={"台本メモ": "台本"})
        sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"保存エラー: {e}")
        return False

# --- 4. ロジック関数 ---
def get_weekdays(start_date, end_date):
    """開始日から終了日までの平日リストを生成（土日を除外）"""
    current = start_date
    weekdays = []
    jp_weekdays = ["(月)", "(火)", "(水)", "(木)", "(金)", "(土)", "(日)"]
    while current <= end_date:
        if current.weekday() < 5:
            weekdays.append({
                "date": current,
                "wday_str": jp_weekdays[current.weekday()]
            })
        current += timedelta(days=1)
    return weekdays

def calculate_stock_deadline(df):
    """在庫状況から投稿可能日を計算"""
    finished_df = df[df["ステータス"].isin(["撮影済", "UP済"])].copy()
    
    if len(finished_df) == 0:
        return None, "在庫なし", "撮影頑張りましょう！"
    
    finished_df["日付"] = pd.to_datetime(finished_df["公開予定日"], format="%m/%d", errors='coerce')
    finished_df["日付"] = finished_df["日付"].apply(lambda x: x.replace(year=datetime.now().year) if pd.notna(x) else None)
    
    max_date = finished_df["日付"].max()
    max_row = finished_df[finished_df["日付"] == max_date].iloc[0]
    
    deadline_text = f"{max_row['公開予定日']} {max_row['曜日']} まで"
    sub_text = "投稿可能！✨"
    
    return len(finished_df), deadline_text, sub_text

# --- 5. メイン処理 ---
st.title("☕️ アニ無理 制作ノート")

# セッションステート初期化
if 'selected_row_index' not in st.session_state:
    st.session_state.selected_row_index = 0
if 'current_month' not in st.session_state:
    st.session_state.current_month = 12  # 12月から開始
if 'current_year' not in st.session_state:
    st.session_state.current_year = 2025

with st.sidebar:
    st.header("⚙️ 設定")
    
    # 月切り替えボタン
    st.subheader("📅 月の切り替え")
    col_prev, col_current, col_next = st.columns([1, 2, 1])
    
    with col_prev:
        if st.button("◀ 前月", key="prev_month"):
            if st.session_state.current_month == 1:
                st.session_state.current_month = 12
                st.session_state.current_year -= 1
            else:
                st.session_state.current_month -= 1
            st.session_state.data_loaded = False  # データ再読み込み
            st.rerun()
    
    with col_current:
        st.markdown(f"### {st.session_state.current_year}年 {st.session_state.current_month}月")
    
    with col_next:
        if st.button("次月 ▶", key="next_month"):
            if st.session_state.current_month == 12:
                st.session_state.current_month = 1
                st.session_state.current_year += 1
            else:
                st.session_state.current_month += 1
            st.session_state.data_loaded = False  # データ再読み込み
            st.rerun()

# --- 6. データ初期化・読み込み ---
sheet = connect_to_gsheets()

if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False

if sheet is not None and not st.session_state.data_loaded:
    sheet_df = load_data_from_sheet(sheet)
    
    if sheet_df is not None and not sheet_df.empty:
        st.session_state.notebook_df = sheet_df
        st.session_state.data_loaded = True
    elif 'notebook_df' not in st.session_state:
        # 選択された月の平日データを生成
        start_date = datetime(st.session_state.current_year, st.session_state.current_month, 1)
        if st.session_state.current_month == 12:
            end_date = datetime(st.session_state.current_year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(st.session_state.current_year, st.session_state.current_month + 1, 1) - timedelta(days=1)
        
        days_data = get_weekdays(start_date, end_date)
        data = []
        for i, d in enumerate(days_data):
            data.append({
                "No": i + 1,
                "公開予定日": d['date'].strftime("%m/%d"),
                "曜日": d['wday_str'],
                "タイトル": "",
                "ステータス": "未",
                "台本メモ": ""
            })
        st.session_state.notebook_df = pd.DataFrame(data)
        st.session_state.data_loaded = True
        save_data_to_sheet(sheet, st.session_state.notebook_df)

if 'notebook_df' in st.session_state:
    df = st.session_state.notebook_df

    # --- 7. 管理指標ダッシュボード ---
    finished_count, deadline_text, sub_text = calculate_stock_deadline(df)
    
    if finished_count is None:
        finished_count = 0
        deadline_text = "在庫なし"
        sub_text = "撮影頑張りましょう！"

    st.markdown("### 📊 ストック状況")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("出来上がっている本数！", f"{finished_count} 本", "撮影済 + UP済")
    with c2:
        st.metric("何月何日まで投稿可能！", deadline_text, sub_text)
    with c3:
        total = len(df)
        st.write(f"**全体の進行率 ({finished_count}/{total})**")
        prog_rate = finished_count / total if total > 0 else 0
        st.progress(prog_rate)

    st.divider()

    # --- 8. スケジュール一覧 & 台本機能 ---
    col1, col2 = st.columns([1.3, 1])

    with col1:
        st.subheader("🗓 スケジュール帳")
        st.caption("👇 台本メモをクリックすると右側の台本エディタに移動します")
        
        # データエディタ
        edited_df = st.data_editor(
            st.session_state.notebook_df,
            column_config={
                "No": st.column_config.NumberColumn(width="small", disabled=True),
                "公開予定日": st.column_config.TextColumn(width="small", disabled=True),
                "曜日": st.column_config.TextColumn(width="small", disabled=True),
                "ステータス": st.column_config.SelectboxColumn(
                    options=["未", "台本完", "撮影済", "UP済"],
                    width="small",
                    required=True
                ),
                "タイトル": st.column_config.TextColumn(width="medium"),
                "台本メモ": st.column_config.TextColumn(width="small"),
            },
            use_container_width=True,
            height=600,
            hide_index=True,
            key="data_editor"
        )
        
        if not edited_df.equals(st.session_state.notebook_df):
            st.session_state.notebook_df = edited_df

    with col2:
        st.subheader("🎬 台本を見る・書く")
        
        # 前へ・次へボタン
        nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
        
        with nav_col1:
            if st.button("⬅ 前へ", use_container_width=True, key="prev_script"):
                if st.session_state.selected_row_index > 0:
                    st.session_state.selected_row_index -= 1
                    st.rerun()
        
        with nav_col2:
            selected_row = st.session_state.notebook_df.iloc[st.session_state.selected_row_index]
            st.info(f"📅 {selected_row['公開予定日']} {selected_row['曜日']}")
        
        with nav_col3:
            if st.button("次へ ➡", use_container_width=True, key="next_script"):
                if st.session_state.selected_row_index < len(st.session_state.notebook_df) - 1:
                    st.session_state.selected_row_index += 1
                    st.rerun()
        
        # 日付選択（クリック連動の代替）
        st.caption("👇 日付を選んで台本を切り替え")
        options = []
        for idx, row in st.session_state.notebook_df.iterrows():
            display_title = row['タイトル'] if row['タイトル'] else "（タイトル未定）"
            status_mark = "✅" if row['ステータス'] in ["撮影済", "UP済"] else "📝"
            label = f"{status_mark} {row['公開予定日']} {row['曜日']} : {display_title}"
            options.append(label)
        
        selected_label = st.selectbox("動画を選択", options, index=st.session_state.selected_row_index, key="script_selector")
        new_index = options.index(selected_label)
        if new_index != st.session_state.selected_row_index:
            st.session_state.selected_row_index = new_index
            st.rerun()
        
        st.markdown("---")
        st.write(f"**【 No.{selected_row['No']} 】** の台本")
        
        # テキストエディタ
        current_text = selected_row["台本メモ"]
        
        st.markdown("💡 **使い方**: Notion等からコピーした文字色付きテキストをそのまま貼り付けてください")
        
        new_text = st.text_area(
            "台本エディタ",
            value=current_text,
            height=400,
            placeholder="ここに台詞や構成を記入...\n\n※文字色付きテキストもそのまま貼り付けOK！",
            key=f"script_{st.session_state.selected_row_index}"
        )
        
        if new_text != current_text:
            st.session_state.notebook_df.at[st.session_state.selected_row_index, "台本メモ"] = new_text
            st.toast(f"No.{selected_row['No']} の台本を更新しました！", icon="💾")

    # --- 9. 保存ボタン ---
    st.divider()
    if st.button("💾 変更をスプレッドシートに保存する", type="primary", use_container_width=True):
        with st.spinner("保存中..."):
            if save_data_to_sheet(sheet, st.session_state.notebook_df):
                st.success("✅ 保存しました！Tomomiさんにも共有されました✨")
                st.balloons()
else:
    st.error("⚠️ データの初期化に失敗しました")
    st.info("Secrets設定を確認してください")
