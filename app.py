# ==============================================
# 🔥 強制リロード設定（キャッシュ無効化）
# Version: 8.2.0 - 2025-12-13 23:00 JST
# スケジュール一覧表示復活版
# ==============================================

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, timedelta
import time
import re

# キャッシュバスター（ページ読み込みごとに強制更新）
CACHE_BUSTER = f"{datetime.now().strftime('%Y%m%d%H%M%S')}"

# --- 1. アプリの設定 ---
st.set_page_config(
    page_title="アニ無理 制作ノート", 
    layout="wide", 
    page_icon="☕",
    initial_sidebar_state="expanded"
)

# URLパラメータからモバイルモード判定
query_params = st.query_params
is_mobile_from_url = query_params.get("mobile", "false").lower() == "true"

# --- 2. デザイン (ミルクティー・クラフト紙風 + 水色バー) ---
st.markdown(f"""
    <style>
    /* キャッシュバスター: {CACHE_BUSTER} */
    
    /* 全体の背景：濃いめの生成り */
    .stApp {{
        background-color: #EFEBD6; 
        color: #4A3B2A;
    }}
    
    /* 文字色統一：焦げ茶 */
    h1, h2, h3, h4, h5, h6, p, label, span, div, li {{
        color: #4A3B2A !important;
        font-family: "Hiragino Mincho ProN", "Yu Mincho", serif;
    }}

    /* サイドバー：少し濃い茶色 */
    [data-testid="stSidebar"] {{
        background-color: #E6DCCF;
        border-right: 1px solid #C0B2A0;
    }}

    /* 入力フォーム等の黒背景対策（念入りに） */
    .stTextInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {{
        background-color: #FFFAF0 !important;
        color: #3E2723 !important;
        border: 1px solid #A1887F;
    }}
    
    /* 表（データエディタ）の強制白背景化 */
    [data-testid="stDataFrame"] {{
        background-color: #FFFAF0 !important;
        border: 1px solid #A1887F;
    }}
    
    /* プログレスバー */
    .stProgress > div > div > div {{
        background-color: #FFFFFF !important;
    }}
    .stProgress > div > div > div > div {{
        background-color: #81D4FA !important;
    }}

    /* ボタンのデザイン */
    .stButton>button {{
        background-color: #D7CCC8;
        color: #3E2723 !important;
        border: 1px solid #8D6E63;
        border-radius: 4px;
        font-size: 1.1em;
        padding: 12px 20px;
    }}
    
    /* 色付きセリフのスタイル */
    .red-text {{
        color: #E53935 !important;
        font-weight: bold;
        font-size: 1.1em;
        line-height: 1.8;
    }}
    .blue-text {{
        color: #1E88E5 !important;
        font-weight: bold;
        font-size: 1.1em;
        line-height: 1.8;
    }}
    .black-text {{
        color: #212121 !important;
        font-size: 1.0em;
        line-height: 1.8;
    }}
    
    /* プレビューエリアの背景 */
    .preview-box {{
        background-color: #FFFAF0;
        padding: 20px;
        border-radius: 8px;
        border: 2px solid #A1887F;
        min-height: 300px;
    }}
    
    /* バージョン表示 */
    .version-badge {{
        background-color: #4CAF50;
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        font-size: 0.9em;
        font-weight: bold;
    }}
    
    /* ナビゲーション区切り線 */
    .nav-divider {{
        border-top: 2px solid #A1887F;
        margin: 20px 0;
    }}
    
    /* モバイル用スタイル */
    @media (max-width: 768px) {{
        .stApp {{
            padding: 10px;
        }}
        h1 {{
            font-size: 1.5em !important;
        }}
        h2 {{
            font-size: 1.2em !important;
        }}
        .stButton>button {{
            font-size: 1.2em !important;
            padding: 15px 25px !important;
        }}
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. スプレッドシート接続機能（キャッシュあり・API制限対策） ---
@st.cache_resource(ttl=3600)  # 1時間キャッシュ
def connect_to_gsheets():
    """Google Sheetsに接続（1時間キャッシュ）"""
    try:
        json_key_data = st.secrets["gcp"]["json_key"]
        
        if isinstance(json_key_data, str):
            key_dict = json.loads(json_key_data)
        else:
            key_dict = dict(json_key_data)
        
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

@st.cache_data(ttl=600)  # 10分キャッシュ
def load_data_from_sheet(_sheet):
    """シートからデータを読み込み（10分キャッシュ）"""
    if _sheet is None:
        return None
    try:
        time.sleep(0.3)
        data = _sheet.get_all_records()
        if not data:
            return None
        df = pd.DataFrame(data)
        
        if "台本" in df.columns and "台本メモ" not in df.columns:
            df = df.rename(columns={"台本": "台本メモ"})
        
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
        time.sleep(0.3)
        sheet.clear()
        save_df = df.copy()
        if "台本メモ" in save_df.columns:
            save_df = save_df.rename(columns={"台本メモ": "台本"})
        sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
        
        # 保存後にキャッシュをクリア
        load_data_from_sheet.clear()
        
        return True
    except Exception as e:
        st.error(f"保存エラー: {e}")
        return False

def generate_monthly_schedule(year, month, start_episode):
    """指定月のスケジュールを自動生成（土日を除外）"""
    from datetime import date
    import calendar
    
    schedules = []
    episode_no = start_episode
    
    # 月の最終日を取得
    last_day = calendar.monthrange(year, month)[1]
    
    for day in range(1, last_day + 1):
        current_date = date(year, month, day)
        weekday = current_date.weekday()  # 0=月, 6=日
        
        # 土日をスキップ
        if weekday in [5, 6]:  # 5=土, 6=日
            continue
        
        weekday_name = ["月", "火", "水", "木", "金", "土", "日"][weekday]
        
        schedules.append({
            "No": f"#{episode_no}",
            "公開予定日": f"{month}/{day}",
            "曜日": weekday_name,
            "タイトル": "",
            "ステータス": "未",
            "台本メモ": ""
        })
        
        episode_no += 1
    
    return pd.DataFrame(schedules)

def ensure_all_months_data(df):
    """12月・1月・2月のデータを自動生成して統合"""
    df['月'] = pd.to_datetime(df['公開予定日'], format='%m/%d', errors='coerce').dt.month
    
    existing_months = df['月'].unique().tolist()
    
    all_data = [df]
    
    # 12月のデータがない場合
    if 12 not in existing_months:
        dec_data = generate_monthly_schedule(2024, 12, 48)
        all_data.append(dec_data)
    
    # 1月のデータがない場合 (#62から開始)
    if 1 not in existing_months:
        jan_data = generate_monthly_schedule(2025, 1, 62)
        all_data.append(jan_data)
    
    # 2月のデータがない場合
    if 2 not in existing_months:
        jan_df = pd.concat(all_data, ignore_index=True)
        jan_df['月'] = pd.to_datetime(jan_df['公開予定日'], format='%m/%d', errors='coerce').dt.month
        jan_episodes = jan_df[jan_df['月'] == 1]
        
        if not jan_episodes.empty:
            last_jan_episode = jan_episodes['No'].iloc[-1]
            last_jan_no = int(last_jan_episode.replace('#', ''))
            feb_start = last_jan_no + 1
        else:
            feb_start = 85
        
        feb_data = generate_monthly_schedule(2025, 2, feb_start)
        all_data.append(feb_data)
    
    # 全データを統合
    combined_df = pd.concat(all_data, ignore_index=True)
    combined_df['月'] = pd.to_datetime(combined_df['公開予定日'], format='%m/%d', errors='coerce').dt.month
    
    return combined_df

def update_episode_numbers(df, start_episode=48):
    """エピソード番号を更新（#48から開始、#100まで対応）"""
    for idx, row in df.iterrows():
        current_no = str(row['No'])
        if current_no.isdigit():
            new_no = f"#{start_episode + int(current_no) - 1}"
            df.at[idx, 'No'] = new_no
        elif not current_no.startswith('#'):
            if current_no.isdigit():
                df.at[idx, 'No'] = f"#{current_no}"
    
    return df

# --- 4. ロジック関数 ---
def calculate_stock_deadline(df):
    """在庫状況から投稿可能日を計算（編集済 + UP済のみ）"""
    finished_df = df[df["ステータス"].isin(["編集済", "UP済"])].copy()
    
    if len(finished_df) == 0:
        return None, "在庫なし", "撮影頑張りましょう！"
    
    finished_df["日付"] = pd.to_datetime(finished_df["公開予定日"], format="%m/%d", errors='coerce')
    finished_df["日付"] = finished_df["日付"].apply(lambda x: x.replace(year=datetime.now().year) if pd.notna(x) else None)
    
    max_date = finished_df["日付"].max()
    max_row = finished_df[finished_df["日付"] == max_date].iloc[0]
    
    deadline_text = f"{max_row['公開予定日']} {max_row['曜日']} まで"
    sub_text = "投稿可能！✨"
    
    return len(finished_df), deadline_text, sub_text

def colorize_script(script_text):
    """台本テキストを色付きHTMLに変換（名前表示版）"""
    if not script_text:
        return "<p class='black-text'>台本を入力してください</p>"
    
    lines = script_text.split('\n')
    html_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            html_lines.append("<br>")
            continue
            
        if line.startswith('赤：'):
            content = re.sub(r'^赤：', '', line)
            html_lines.append(f'<p class="red-text">Tomomi：{content}</p>')
        elif line.startswith('青：'):
            content = re.sub(r'^青：', '', line)
            html_lines.append(f'<p class="blue-text">道ゐ：{content}</p>')
        elif line.startswith('黒：'):
            content = re.sub(r'^黒：', '', line)
            html_lines.append(f'<p class="black-text">{content}</p>')
        else:
            html_lines.append(f'<p class="black-text">{line}</p>')
    
    return ''.join(html_lines)

# --- 5. メイン処理 ---
st.title("☕️ アニ無理 制作ノート")

# バージョン表示
st.markdown('<span class="version-badge">🔄 Version 8.3.1 - 接続順序修正版</span>', unsafe_allow_html=True)

# 1. まずデータに接続する（ここを先に持ってきたよ！）
sheet = connect_to_gsheets()
sheet_df = load_data_from_sheet(sheet)

# セッションステート初期化
if 'selected_row_index' not in st.session_state:
    st.session_state.selected_row_index = 0
if 'current_month' not in st.session_state:
    st.session_state.current_month = datetime.now().month
if 'current_year' not in st.session_state:
    st.session_state.current_year = datetime.now().year
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "preview"

# --- 月移動の共通ロジック ---
def move_month(direction):
    if direction == "next":
        if st.session_state.current_month == 12:
            st.session_state.current_month = 1
            st.session_state.current_year += 1
        else:
            st.session_state.current_month += 1
    else:
        if st.session_state.current_month == 1:
            st.session_state.current_month = 12
            st.session_state.current_year -= 1
        else:
            st.session_state.current_month -= 1
    st.session_state.selected_row_index = 0
    st.rerun()

# --- 6. サイドバー設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
    
    if is_mobile_from_url:
        st.info("📱 スマホ版で表示中")
        is_mobile = True
    else:
        device_mode = st.radio("表示モード", options=["🖥 PC版（フル機能）", "📱 スマホ版（閲覧のみ）"], index=0)
        is_mobile = (device_mode == "📱 スマホ版（閲覧のみ）")
    
    # PC版限定：一括更新機能
    if not is_mobile:
        st.divider()
        with st.expander("🔄 ステータス一括更新"):
            st.caption("表示中の月の範囲を指定して更新")
            # データの読み込みが完了している場合に実行
            if sheet_df is not None:
                # 月のデータを作る
                temp_df = sheet_df.copy()
                temp_df = ensure_all_months_data(temp_df)
                temp_df['月'] = pd.to_datetime(temp_df['公開予定日'], format='%m/%d', errors='coerce').dt.month
                month_eps = temp_df[temp_df['月'] == st.session_state.current_month]
                
                if not month_eps.empty:
                    ep_list = month_eps['No'].tolist()
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        start_ep = st.selectbox("開始", ep_list, key="bulk_start")
                    with col_b2:
                        end_ep = st.selectbox("終了", ep_list, index=len(ep_list)-1, key="bulk_end")
                    
                    new_stat = st.selectbox("新ステータス", ["未", "台本完", "撮影済", "編集済", "UP済"], key="bulk_stat")
                    
                    if st.button("一括更新を実行", type="primary", use_container_width=True):
                        s_idx = ep_list.index(start_ep)
                        e_idx = ep_list.index(end_ep)
                        targets = ep_list[min(s_idx, e_idx) : max(s_idx, e_idx) + 1]
                        
                        # 全体データ(notebook_df)を更新
                        if 'notebook_df' in st.session_state:
                            st.session_state.notebook_df.loc[st.session_state.notebook_df['No'].isin(targets), 'ステータス'] = new_stat
                            if save_data_to_sheet(sheet, st.session_state.notebook_df):
                                st.success(f"{len(targets)}件を「{new_stat}」に更新！")
                                time.sleep(1)
                                st.rerun()

    st.divider()
    st.subheader("📅 月の切り替え")
    c_prev, c_curr, c_next = st.columns([1, 2, 1])
    with c_prev:
        if st.button("◀", key="side_prev"): move_month("prev")
    with c_curr:
        st.markdown(f"**{st.session_state.current_year}/{st.session_state.current_month}**")
    with c_next:
        if st.button("▶", key="side_next"): move_month("next")

    if st.button("🔄 最新データを取得", type="secondary", use_container_width=True):
        load_data_from_sheet.clear()
        st.rerun()

# --- 7. データ処理 ---
if sheet_df is not None and not sheet_df.empty:
    sheet_df = ensure_all_months_data(sheet_df)
    sheet_df = update_episode_numbers(sheet_df, start_episode=48)
    st.session_state.notebook_df = sheet_df
    
    df = st.session_state.notebook_df
    df['月'] = pd.to_datetime(df['公開予定日'], format='%m/%d', errors='coerce').dt.month
    current_month_df = df[df['月'] == st.session_state.current_month].copy()

    if current_month_df.empty:
        st.warning(f"{st.session_state.current_month}月のデータがありません。")
    else:
        # モバイル版用：メイン画面の月移動ボタン
        if is_mobile:
            m_prev, m_curr, m_next = st.columns([1, 2, 1])
            with m_prev:
                if st.button("◀ 前月", key="m_nav_prev"): move_month("prev")
            with m_curr:
                st.markdown(f"<center><h3>{st.session_state.current_month}月</h3></center>", unsafe_allow_html=True)
            with m_next:
                if st.button("次月 ▶", key="m_nav_next"): move_month("next")
            st.divider()

        # --- 8. ダッシュボード ---
        finished_count, deadline_text, sub_text = calculate_stock_deadline(current_month_df)
        st.markdown("### 📊 ストック状況")
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            st.metric("出来上がっている本数！", f"{finished_count if finished_count else 0} 本", "編集済 + UP済")
        with d_col2:
            st.metric("何月何日まで投稿可能！", deadline_text, sub_text)
        st.divider()

        # --- 9. スケジュール一覧 & 台本機能 ---
        if is_mobile:
            # ========== モバイル版表示 ==========
            options = []
            for idx, row in current_month_df.iterrows():
                status_mark = {"UP済":"✅","編集済":"✂️","撮影済":"🎬","台本完":"📝"}.get(row['ステータス'], "⏳")
                label = f"{status_mark} {row['No']} | {row['公開予定日']} | {row['タイトル'] if row['タイトル'] else '（未定）'}"
                options.append((label, idx))
            
            if st.session_state.selected_row_index >= len(options): st.session_state.selected_row_index = 0
            
            # ナビゲーション
            nav_col1, nav_col2, nav_col3 = st.columns([1, 3, 1])
            with nav_col1:
                if st.button("⬅", key="m_prev", disabled=(st.session_state.selected_row_index == 0)):
                    st.session_state.selected_row_index -= 1
                    st.rerun()
            with nav_col2:
                sel = st.selectbox("選択", [o[0] for o in options], index=st.session_state.selected_row_index, label_visibility="collapsed")
                st.session_state.selected_row_index = [o[0] for o in options].index(sel)
            with nav_col3:
                if st.button("➡", key="m_next", disabled=(st.session_state.selected_row_index >= len(options)-1)):
                    st.session_state.selected_row_index += 1
                    st.rerun()
            
            actual_index = options[st.session_state.selected_row_index][1]
            selected_row = st.session_state.notebook_df.loc[actual_index]
            
            st.markdown(f"#### 🎬 {selected_row['No']} の台本")
            if selected_row['ステータス'] != "UP済":
                if st.button("✅ UP済にする", type="primary", use_container_width=True):
                    st.session_state.notebook_df.at[actual_index, 'ステータス'] = "UP済"
                    save_data_to_sheet(sheet, st.session_state.notebook_df)
                    st.balloons()
                    st.rerun()
            
            st.markdown(f'<div class="preview-box">{colorize_script(selected_row["台本メモ"])}</div>', unsafe_allow_html=True)

        else:
            # ========== PC版表示 ==========
            col_list, col_edit = st.columns([1.3, 1])
            with col_list:
                st.subheader("🗓 スケジュール帳")
                options = []
                for idx, row in current_month_df.iterrows():
                    status_mark = {"UP済":"✅","編集済":"✂️","撮影済":"🎬","台本完":"📝"}.get(row['ステータス'], "⏳")
                    label = f"{status_mark} {row['No']} | {row['公開予定日']} {row['曜日']} | {row['タイトル'] if row['タイトル'] else '（未定）'}"
                    options.append((label, idx))
                
                if st.session_state.selected_row_index >= len(options): st.session_state.selected_row_index = 0
                sel_label = st.radio("選択", [o[0] for o in options], index=st.session_state.selected_row_index, label_visibility="collapsed")
                st.session_state.selected_row_index = [o[0] for o in options].index(sel_label)

            with col_edit:
                actual_index = options[st.session_state.selected_row_index][1]
                selected_row = st.session_state.notebook_df.loc[actual_index]
                
                st.subheader("🎬 台本編集")
                new_title = st.text_input("タイトル", value=selected_row['タイトル'])
                new_status = st.selectbox("ステータス", ["未", "台本完", "撮影済", "編集済", "UP済"], index=["未", "台本完", "撮影済", "編集済", "UP済"].index(selected_row['ステータス']))
                
                if new_title != selected_row['タイトル'] or new_status != selected_row['ステータス']:
                    st.session_state.notebook_df.at[actual_index, 'タイトル'] = new_title
                    st.session_state.notebook_df.at[actual_index, 'ステータス'] = new_status
                    st.toast("自動保存（仮）", icon="💾")

                m_col1, m_col2 = st.columns(2)
                with m_col1:
                    if st.button("✏️ 編集", type="primary" if st.session_state.view_mode=="edit" else "secondary", use_container_width=True):
                        st.session_state.view_mode = "edit"
                        st.rerun()
                with m_col2:
                    if st.button("👁 プレビュー", type="primary" if st.session_state.view_mode=="preview" else "secondary", use_container_width=True):
                        st.session_state.view_mode = "preview"
                        st.rerun()

                if st.session_state.view_mode == "edit":
                    new_text = st.text_area("台本エディタ", value=selected_row["台本メモ"], height=400)
                    if new_text != selected_row["台本メモ"]:
                        st.session_state.notebook_df.at[actual_index, "台本メモ"] = new_text
                else:
                    st.markdown(f'<div class="preview-box">{colorize_script(selected_row["台本メモ"])}</div>', unsafe_allow_html=True)
                
                if st.button("💾 全ての変更を保存", type="primary", use_container_width=True):
                    if save_data_to_sheet(sheet, st.session_state.notebook_df):
                        st.success("保存完了！")
                        st.balloons()
else:
    st.error("データの初期化に失敗しました。Secrets設定を確認してください。")
