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

# バージョン表示（確認用）
st.markdown('<span class="version-badge">🔄 Version 8.2.0 - スケジュール一覧表示復活</span>', unsafe_allow_html=True)

# セッションステート初期化
if 'selected_row_index' not in st.session_state:
    st.session_state.selected_row_index = 0
if 'current_month' not in st.session_state:
    st.session_state.current_month = 12
if 'current_year' not in st.session_state:
    st.session_state.current_year = 2024
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "preview"

# モバイルモード切り替え
with st.sidebar:
    st.header("⚙️ 設定")
    
    if is_mobile_from_url:
        st.info("📱 スマホ版で表示中")
        is_mobile = True
    else:
        device_mode = st.radio(
            "表示モード",
            options=["🖥 PC版（フル機能）", "📱 スマホ版（閲覧のみ）"],
            index=0
        )
        
        is_mobile = (device_mode == "📱 スマホ版（閲覧のみ）")
    
    if not is_mobile:
        st.divider()
        st.subheader("📱 スマホ版URL")
        mobile_url = "https://tiktok-app-5wwg8zhowhqokpxasht6tg.streamlit.app?mobile=true"
        st.code(mobile_url, language=None)
        st.caption("👆 このURLをスマホで開くと、自動的にスマホ版で表示されます")
    
    if not is_mobile:
        st.divider()
        st.subheader("📅 月の切り替え")
        col_prev, col_current, col_next = st.columns([1, 2, 1])
        
        with col_prev:
            if st.button("◀ 前月", key="month_prev"):
                if st.session_state.current_month == 1:
                    st.session_state.current_month = 12
                    st.session_state.current_year -= 1
                else:
                    st.session_state.current_month -= 1
                st.session_state.selected_row_index = 0
                st.rerun()
        
        with col_current:
            st.markdown(f"### {st.session_state.current_year}年 {st.session_state.current_month}月")
        
        with col_next:
            if st.button("次月 ▶", key="month_next"):
                if st.session_state.current_month == 12:
                    st.session_state.current_month = 1
                    st.session_state.current_year += 1
                else:
                    st.session_state.current_month += 1
                st.session_state.selected_row_index = 0
                st.rerun()
        
        st.divider()
        
        st.subheader("📊 エピソード番号")
        st.markdown("""
        - **12月**: #48〜#61（平日のみ）
        - **1月**: #62〜#84（平日のみ）
        - **2月**: #85〜（平日のみ）
        """)
        
        st.divider()
        
        st.subheader("📝 台本フォーマット")
        st.markdown("""
        **正しい書き方：**
        - `赤：「Tomomiのセリフ」`
        - `青：「道ゐのセリフ」`
        - `黒：「ナレーション」`
        
        **プレビュー表示：**
        - 赤 → **Tomomi：** （赤色）
        - 青 → **道ゐ：** （青色）
        - 黒 → そのまま（黒色）
        """)
        
        st.divider()
        
        # キャッシュクリアボタン
        if st.button("🔄 最新データを取得", type="secondary", use_container_width=True):
            load_data_from_sheet.clear()
            st.success("✅ キャッシュをクリアしました！")
            st.rerun()

# --- 6. データ初期化・読み込み（キャッシュあり） ---
sheet = connect_to_gsheets()
sheet_df = load_data_from_sheet(sheet)

if sheet_df is not None and not sheet_df.empty:
    # 1月・2月のデータを自動生成
    sheet_df = ensure_all_months_data(sheet_df)
    sheet_df = update_episode_numbers(sheet_df, start_episode=48)
    st.session_state.notebook_df = sheet_df
else:
    st.error("⚠️ Google Sheetsにデータがありません")
    st.info("先にGoogle Sheetsにデータを入力してください")
    st.stop()

if 'notebook_df' in st.session_state:
    df = st.session_state.notebook_df

    # 現在の月のデータをフィルタリング
    df['月'] = pd.to_datetime(df['公開予定日'], format='%m/%d', errors='coerce').dt.month
    current_month_df = df[df['月'] == st.session_state.current_month].copy()
    
    if current_month_df.empty:
        st.warning(f"{st.session_state.current_year}年{st.session_state.current_month}月のデータがありません")
        st.info("💡 左サイドバーの「月の切り替え」で他の月を確認してください")
    else:
        # --- 7. 管理指標ダッシュボード ---
        finished_count, deadline_text, sub_text = calculate_stock_deadline(current_month_df)
        
        if finished_count is None:
            finished_count = 0
            deadline_text = "在庫なし"
            sub_text = "撮影頑張りましょう！"

        st.markdown("### 📊 ストック状況")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("出来上がっている本数！", f"{finished_count} 本", "編集済 + UP済")
        with c2:
            st.metric("何月何日まで投稿可能！", deadline_text, sub_text)

        st.divider()

        # --- 8. スケジュール一覧 & 台本機能 ---
        if is_mobile:
            # ========== モバイル版（ナビゲーション強化版） ==========
            st.subheader("🗓 スケジュール")
            
            st.caption("**ステータス：** ✅UP済 | ✂️編集済 | 🎬撮影済 | 📝台本完 | ⏳未")
            
            options = []
            for idx, row in current_month_df.iterrows():
                display_title = row['タイトル'] if row['タイトル'] else "（タイトル未定）"
                
                if row['ステータス'] == "UP済":
                    status_mark = "✅"
                elif row['ステータス'] == "編集済":
                    status_mark = "✂️"
                elif row['ステータス'] == "撮影済":
                    status_mark = "🎬"
                elif row['ステータス'] == "台本完":
                    status_mark = "📝"
                else:
                    status_mark = "⏳"
                
                label = f"{status_mark} {row['No']} | {row['公開予定日']} | {display_title}"
                options.append((label, idx))
            
            # 最大インデックスを保存
            max_index = len(options) - 1
            
            if st.session_state.selected_row_index >= len(options):
                st.session_state.selected_row_index = 0
            
            # ★★★ 上部ナビゲーション（ボタン＋セレクトボックス） ★★★
            nav_col1, nav_col2, nav_col3 = st.columns([1, 3, 1])
            
            with nav_col1:
                if st.button("⬅", key="mobile_prev_top", disabled=(st.session_state.selected_row_index == 0), use_container_width=True):
                    st.session_state.selected_row_index -= 1
                    st.rerun()
            
            with nav_col2:
                selected_label = st.selectbox(
                    "エピソードを選択",
                    [opt[0] for opt in options],
                    index=st.session_state.selected_row_index,
                    key="episode_selector_mobile_top",
                    label_visibility="collapsed"
                )
                
                if selected_label:
                    new_index = [opt[0] for opt in options].index(selected_label)
                    if new_index != st.session_state.selected_row_index:
                        st.session_state.selected_row_index = new_index
            
            with nav_col3:
                if st.button("➡", key="mobile_next_top", disabled=(st.session_state.selected_row_index >= max_index), use_container_width=True):
                    st.session_state.selected_row_index += 1
                    st.rerun()
            
            actual_index = options[st.session_state.selected_row_index][1]
            selected_row = st.session_state.notebook_df.loc[actual_index]
            
            st.divider()
            
            st.subheader("📊 ステータス変更")
            current_status = selected_row['ステータス']
            
            col_status1, col_status2 = st.columns(2)
            
            with col_status1:
                st.info(f"現在：**{current_status}**")
            
            with col_status2:
                if current_status != "UP済":
                    if st.button("✅ UP済にする", use_container_width=True, type="primary"):
                        st.session_state.notebook_df.at[actual_index, 'ステータス'] = "UP済"
                        with st.spinner("保存中..."):
                            if save_data_to_sheet(sheet, st.session_state.notebook_df):
                                st.success("✅ UP済に更新しました！")
                                st.balloons()
                                time.sleep(1)
                                st.rerun()
                else:
                    st.success("✅ UP済です！")
            
            st.divider()
            
            st.subheader(f"🎬 {selected_row['No']} の台本")
            st.caption(f"📅 {selected_row['公開予定日']} {selected_row['曜日']} | {selected_row['タイトル']}")
            
            current_text = selected_row["台本メモ"]
            colored_html = colorize_script(current_text)
            
            st.markdown('<div class="preview-box">' + colored_html + '</div>', unsafe_allow_html=True)
            
            # ★★★ 下部ナビゲーション（ボタンのみ） ★★★
            st.markdown('<div class="nav-divider"></div>', unsafe_allow_html=True)
            
            nav_bottom_col1, nav_bottom_col2, nav_bottom_col3 = st.columns([1, 2, 1])
            
            with nav_bottom_col1:
                if st.button("⬅ 前へ", key="mobile_prev_bottom", disabled=(st.session_state.selected_row_index == 0), use_container_width=True):
                    st.session_state.selected_row_index -= 1
                    st.rerun()
            
            with nav_bottom_col2:
                st.markdown(f"<center><strong>{selected_row['No']}</strong></center>", unsafe_allow_html=True)
            
            with nav_bottom_col3:
                if st.button("次へ ➡", key="mobile_next_bottom", disabled=(st.session_state.selected_row_index >= max_index), use_container_width=True):
                    st.session_state.selected_row_index += 1
                    st.rerun()
            
        else:
            # ========== PC版（ラジオボタン一覧表示） ==========
            col1, col2 = st.columns([1.3, 1])

            with col1:
                st.subheader("🗓 スケジュール帳")
                
                st.caption("👇 ラジオボタンで行を選択すると、右側の台本が切り替わります")
                
                st.markdown("""
                **ステータス表示：**
                - ✅ UP済
                - ✂️ 編集済
                - 🎬 撮影済
                - 📝 台本完
                - ⏳ 未
                """)
                
                st.divider()
                
                # ★★★ ラジオボタンによる行選択（一覧表示） ★★★
                options = []
                for idx, row in current_month_df.iterrows():
                    display_title = row['タイトル'] if row['タイトル'] else "（タイトル未定）"
                    
                    if row['ステータス'] == "UP済":
                        status_mark = "✅"
                    elif row['ステータス'] == "編集済":
                        status_mark = "✂️"
                    elif row['ステータス'] == "撮影済":
                        status_mark = "🎬"
                    elif row['ステータス'] == "台本完":
                        status_mark = "📝"
                    else:
                        status_mark = "⏳"
                    
                    label = f"{status_mark} {row['No']} | {row['公開予定日']} {row['曜日']} | {display_title}"
                    options.append((label, idx))
                
                if st.session_state.selected_row_index >= len(options):
                    st.session_state.selected_row_index = 0
                
                selected_label = st.radio(
                    "台本を選択",
                    [opt[0] for opt in options],
                    index=st.session_state.selected_row_index,
                    key="row_selector",
                    label_visibility="collapsed"
                )
                
                if selected_label:
                    new_index = [opt[0] for opt in options].index(selected_label)
                    if new_index != st.session_state.selected_row_index:
                        st.session_state.selected_row_index = new_index

            with col2:
                st.subheader("🎬 台本を見る・書く")
                
                # 現在選択中の行情報を取得
                actual_index = options[st.session_state.selected_row_index][1]
                selected_row = st.session_state.notebook_df.loc[actual_index]
                
                st.info(f"📅 {selected_row['公開予定日']} {selected_row['曜日']} | {selected_row['No']}")
                
                st.markdown("---")
                
                # タイトル入力
                st.write("**📝 タイトル**")
                new_title = st.text_input(
                    "タイトルを入力",
                    value=selected_row['タイトル'],
                    key=f"title_{actual_index}",
                    label_visibility="collapsed"
                )
                
                if new_title != selected_row['タイトル']:
                    st.session_state.notebook_df.at[actual_index, 'タイトル'] = new_title
                    st.toast(f"{selected_row['No']} のタイトルを更新しました！", icon="💾")
                
                # ステータス選択
                st.write("**🎬 ステータス**")
                new_status = st.selectbox(
                    "ステータスを選択",
                    options=["未", "台本完", "撮影済", "編集済", "UP済"],
                    index=["未", "台本完", "撮影済", "編集済", "UP済"].index(selected_row['ステータス']),
                    key=f"status_{actual_index}",
                    label_visibility="collapsed"
                )
                
                if new_status != selected_row['ステータス']:
                    st.session_state.notebook_df.at[actual_index, 'ステータス'] = new_status
                    st.toast(f"{selected_row['No']} のステータスを更新しました！", icon="📊")
                
                st.markdown("---")
                
                # 編集/プレビュー切り替えボタン
                mode_col1, mode_col2 = st.columns(2)
                
                with mode_col1:
                    if st.button("✏️ 編集モード", use_container_width=True, 
                                type="primary" if st.session_state.view_mode == "edit" else "secondary"):
                        st.session_state.view_mode = "edit"
                        st.rerun()
                
                with mode_col2:
                    if st.button("👁 プレビューモード", use_container_width=True,
                                type="primary" if st.session_state.view_mode == "preview" else "secondary"):
                        st.session_state.view_mode = "preview"
                        st.rerun()
                
                st.write(f"**【 {selected_row['No']} 】** の台本")
                
                current_text = selected_row["台本メモ"]
                
                # モードに応じた表示切り替え
                if st.session_state.view_mode == "edit":
                    # 編集モード
                    new_text = st.text_area(
                        "台本エディタ（編集モード）",
                        value=current_text,
                        height=300,
                        placeholder="ここに台本を記入...\n\n例：\n赤：「こんにちは！」\n青：「よろしく！」\n黒：「【ナレーション】」",
                        key=f"script_{actual_index}"
                    )
                    
                    if new_text != current_text:
                        st.session_state.notebook_df.at[actual_index, "台本メモ"] = new_text
                        st.toast(f"{selected_row['No']} の台本を更新しました！", icon="💾")
                
                else:
                    # プレビューモード
                    colored_html = colorize_script(current_text)
                    
                    st.markdown('<div class="preview-box">' + colored_html + '</div>', unsafe_allow_html=True)

            # --- 9. 保存ボタン（PC版のみ） ---
            st.divider()
            if st.button("💾 変更をスプレッドシートに保存する", type="primary", use_container_width=True):
                with st.spinner("保存中..."):
                    if save_data_to_sheet(sheet, st.session_state.notebook_df):
                        st.success("✅ 保存しました！Tomomiさんにも共有されました✨")
                        st.balloons()
else:
    st.error("⚠️ データの初期化に失敗しました")
    st.info("Secrets設定を確認してください")
