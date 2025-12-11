import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, timedelta

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

# --- 3. スプレッドシート接続機能 ---
def connect_to_gsheets():
    """Google Sheetsに接続"""
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
        data = sheet.get_all_records()
        if not data:
            return None
        df = pd.DataFrame(data)
        
        # カラム名を統一（台本 → 台本メモ）
        if "台本" in df.columns and "台本メモ" not in df.columns:
            df = df.rename(columns={"台本": "台本メモ"})
        
        # 土日を除外（曜日列を確認）
        df = df[~df["曜日"].isin(["(土)", "(日)"])].reset_index(drop=True)
        
        # No列を振り直し
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
        sheet.clear()
        # カラム名を統一（台本メモ → 台本）
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
        # 土日を除外（0=月曜, 4=金曜, 5=土曜, 6=日曜）
        if current.weekday() < 5:
            weekdays.append({
                "date": current,
                "wday_str": jp_weekdays[current.weekday()]
            })
        current += timedelta(days=1)
    return weekdays

def calculate_stock_deadline(df):
    """在庫状況から投稿可能日を計算"""
    # 「撮影済」「UP済」のデータを抽出
    finished_df = df[df["ステータス"].isin(["撮影済", "UP済"])].copy()
    
    if len(finished_df) == 0:
        return None, "在庫なし", "撮影頑張りましょう！"
    
    # 公開予定日を日付型に変換
    finished_df["日付"] = pd.to_datetime(finished_df["公開予定日"], format="%m/%d", errors='coerce')
    finished_df["日付"] = finished_df["日付"].apply(lambda x: x.replace(year=datetime.now().year) if pd.notna(x) else None)
    
    # 最も遅い公開予定日を取得
    max_date = finished_df["日付"].max()
    max_row = finished_df[finished_df["日付"] == max_date].iloc[0]
    
    deadline_text = f"{max_row['公開予定日']} {max_row['曜日']} まで"
    sub_text = "投稿可能！✨"
    
    return len(finished_df), deadline_text, sub_text

# --- 5. メイン処理 ---
st.title("☕️ アニ無理 制作ノート")

with st.sidebar:
    st.header("⚙️ 設定")
    start_date = st.date_input("開始日", datetime(2025, 12, 11))
    target_end_date = datetime(2026, 2, 28)

# --- 6. データ初期化・読み込み ---
sheet = connect_to_gsheets()

if sheet is not None:
    # シートからデータを読み込み（土日は自動除外）
    sheet_df = load_data_from_sheet(sheet)
    
    if sheet_df is not None and not sheet_df.empty:
        # シートにデータがある場合（土日は既に除外済み）
        st.session_state.notebook_df = sheet_df
    elif 'notebook_df' not in st.session_state:
        # 初回起動：新規データを生成（平日のみ）
        days_data = get_weekdays(start_date, target_end_date)
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
        # 初期データをシートに保存
        save_data_to_sheet(sheet, st.session_state.notebook_df)

    df = st.session_state.notebook_df

    # --- 7. 管理指標ダッシュボード（自動計算） ---
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
        st.caption("👇 土日は除外されています（平日のみ表示）")
        
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
                "台本メモ": st.column_config.TextColumn(disabled=True),
            },
            use_container_width=True,
            height=600,
            hide_index=True,
            key="data_editor"
        )
        
        if not edited_df.equals(st.session_state.notebook_df):
            st.session_state.notebook_df = edited_df
            st.rerun()

    with col2:
        st.subheader("🎬 台本を見る・書く")
        st.info("👇 編集したい動画の日付を選んでください")
        
        options = []
        for idx, row in edited_df.iterrows():
            display_title = row['タイトル'] if row['タイトル'] else "（タイトル未定）"
            status_mark = "✅" if row['ステータス'] in ["撮影済", "UP済"] else "📝"
            label = f"{status_mark} {row['公開予定日']} {row['曜日']} : {display_title}"
            options.append(label)
        
        selected_label = st.selectbox("動画を選択", options)
        selected_index = options.index(selected_label)
        selected_row = edited_df.iloc[selected_index]
        
        st.markdown("---")
        st.write(f"**【 No.{selected_row['No']} 】** の台本")
        
        current_text = selected_row["台本メモ"]
        new_text = st.text_area(
            "台本エディタ",
            value=current_text,
            height=450,
            placeholder="ここに台詞や構成を記入..."
        )
        
        if new_text != current_text:
            st.session_state.notebook_df.at[selected_index, "台本メモ"] = new_text
            st.toast(f"No.{selected_row['No']} の台本を更新しました！", icon="💾")
            st.rerun()

    # --- 9. 保存ボタン ---
    st.divider()
    if st.button("💾 変更をスプレッドシートに保存する", type="primary", use_container_width=True):
        with st.spinner("保存中..."):
            if save_data_to_sheet(sheet, st.session_state.notebook_df):
                st.success("✅ 保存しました！Tomomiさんにも共有されました✨")
                st.balloons()
else:
    st.error("⚠️ Google Sheetsに接続できませんでした")
    st.info("Secrets設定を確認してください")
