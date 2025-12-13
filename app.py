import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime, timedelta
import calendar
import re

# ページ設定
st.set_page_config(page_title="TikTok投稿管理", layout="wide")

# デバイス判定（モバイルかPCか）
def is_mobile():
    user_agent = st.context.headers.get("User-Agent", "").lower()
    return any(device in user_agent for device in ["mobile", "android", "iphone"])

# Google認証情報
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)

# スプレッドシートID
SPREADSHEET_ID = "1ZAWJdojWmlkspv0YnxjsVg9secrdKNP2sgbDAclcNpI"

# Google Sheets APIクライアント
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

# エピソード番号を計算する関数（12月=48スタート、1月=70スタート）
def calculate_episode_start(year, month):
    if year == 2025 and month == 12:
        return 48
    elif year == 2026 and month == 1:
        return 70
    else:
        # 将来的な拡張用（22営業日/月で計算）
        base_month = 12 if year == 2025 else 1
        base_episode = 48 if year == 2025 else 70
        month_diff = (year - 2025) * 12 + (month - base_month)
        return base_episode + (month_diff * 22)

# シート名を生成（例：2025年12月）
def get_sheet_name(year, month):
    return f"{year}年{month}月"

# 月間スケジュールを生成する関数（平日のみ）
def generate_monthly_schedule(year, month):
    start_episode = calculate_episode_start(year, month)
    cal = calendar.monthcalendar(year, month)
    schedule = []
    episode_num = start_episode
    
    for week in cal:
        for day in week:
            if day == 0:
                continue
            date = datetime(year, month, day)
            if date.weekday() < 5:  # 月曜日(0)から金曜日(4)
                schedule.append({
                    "No": f"#{episode_num}",
                    "日付": date.strftime("%Y-%m-%d"),
                    "曜日": ["月", "火", "水", "木", "金"][date.weekday()],
                    "タイトル": "",
                    "台本": "",
                    "ステータス": "未"
                })
                episode_num += 1
    
    return schedule

# スプレッドシートにシートが存在するか確認
def sheet_exists(sheet_name):
    try:
        metadata = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
        sheets = metadata.get('sheets', [])
        return any(s['properties']['title'] == sheet_name for s in sheets)
    except Exception:
        return False

# シートを作成
def create_sheet(sheet_name):
    body = {'requests': [{'addSheet': {'properties': {'title': sheet_name}}}]}
    sheet.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()

# データを読み込む
def load_data(sheet_name):
    try:
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A:F"
        ).execute()
        values = result.get('values', [])
        
        if not values or len(values) < 2:
            return pd.DataFrame()
        
        df = pd.DataFrame(values[1:], columns=values[0])
        return df
    except Exception:
        return pd.DataFrame()

# データを保存する
def save_data(sheet_name, df):
    values = [df.columns.tolist()] + df.values.tolist()
    body = {'values': values}
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A:F",
        valueInputOption="RAW",
        body=body
    ).execute()

# 月を初期化（既存データは保持、新規データは追加）
def initialize_month(year, month):
    sheet_name = get_sheet_name(year, month)
    
    if not sheet_exists(sheet_name):
        create_sheet(sheet_name)
    
    existing_df = load_data(sheet_name)
    new_schedule = generate_monthly_schedule(year, month)
    new_df = pd.DataFrame(new_schedule)
    
    if existing_df.empty:
        save_data(sheet_name, new_df)
        return new_df
    else:
        # 既存データとマージ（Noをキーに）
        merged_df = new_df.merge(
            existing_df[["No", "タイトル", "台本", "ステータス"]],
            on="No",
            how="left",
            suffixes=("", "_existing")
        )
        
        # 既存データがあれば上書き
        for col in ["タイトル", "台本", "ステータス"]:
            if f"{col}_existing" in merged_df.columns:
                merged_df[col] = merged_df[f"{col}_existing"].fillna(merged_df[col])
                merged_df = merged_df.drop(columns=[f"{col}_existing"])
        
        save_data(sheet_name, merged_df)
        return merged_df

# スケジュールの一括ステータス更新（PCのみ）
def bulk_update_status(df, start_ep, end_ep, new_status):
    start_num = int(start_ep.replace("#", ""))
    end_num = int(end_ep.replace("#", ""))
    
    for idx, row in df.iterrows():
        ep_num = int(row["No"].replace("#", ""))
        if start_num <= ep_num <= end_num:
            df.at[idx, "ステータス"] = new_status
    
    return df

# 色付きプレビュー（赤→Tomomi、青→道ゐ、黒→そのまま）
def render_colored_preview(script_text):
    if not script_text:
        st.warning("台本が空です")
        return
    
    lines = script_text.strip().split("\n")
    for line in lines:
        # 赤：「」→ Tomomi：「」 (赤色)
        if re.match(r'^赤：「.+」$', line):
            content = line.replace("赤：", "")
            st.markdown(f"**<span style='color:red;'>Tomomi：{content}</span>**", unsafe_allow_html=True)
        
        # 青：「」→ 道ゐ：「」 (青色)
        elif re.match(r'^青：「.+」$', line):
            content = line.replace("青：", "")
            st.markdown(f"**<span style='color:blue;'>道ゐ：{content}</span>**", unsafe_allow_html=True)
        
        # 黒：「」→ そのまま (黒色)
        elif re.match(r'^黒：「.+」$', line):
            content = line.replace("黒：", "")
            st.markdown(f"<span style='color:black;'>{content}</span>", unsafe_allow_html=True)
        
        # それ以外はそのまま表示
        else:
            st.text(line)

# セッション状態の初期化
if "selected_year" not in st.session_state:
    st.session_state.selected_year = 2025
if "selected_month" not in st.session_state:
    st.session_state.selected_month = 12
if "selected_index" not in st.session_state:
    st.session_state.selected_index = 0
if "script_index" not in st.session_state:
    st.session_state.script_index = 0

# サイドバー：月選択（PCのみ）
mobile_mode = is_mobile()

if not mobile_mode:
    st.sidebar.header("📅 月を選択")
    year = st.sidebar.selectbox("年", [2025, 2026], index=0, key="year_select")
    month = st.sidebar.selectbox("月", list(range(1, 13)), index=11 if year == 2025 else 0, key="month_select")
    
    if st.sidebar.button("月を切り替え"):
        st.session_state.selected_year = year
        st.session_state.selected_month = month
        st.rerun()

# 現在の月のデータを取得
current_year = st.session_state.selected_year
current_month = st.session_state.selected_month
sheet_name = get_sheet_name(current_year, current_month)
df = initialize_month(current_year, current_month)

# ストック状況の計算（編集済 + UP済 のみ）
stock_count = len(df[df["ステータス"].isin(["編集済", "UP済"])])

# メインタイトル
st.title(f"📹 TikTok投稿管理 ({current_year}年{current_month}月)")
st.metric("📦 ストック状況", f"{stock_count}本")

# --- PC版：完全機能 ---
if not mobile_mode:
    st.markdown("---")
    st.subheader("📖 スケジュール帳")
    
    # 一括ステータス更新（折りたたみ式）
    with st.expander("🔄 一括ステータス更新"):
        st.caption("範囲指定でまとめてステータスを変更できます")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            start_ep = st.selectbox("開始エピソード", df["No"].tolist(), key="bulk_start")
        with col2:
            end_ep = st.selectbox("終了エピソード", df["No"].tolist(), key="bulk_end")
        with col3:
            new_status = st.selectbox("変更先ステータス", ["撮影済", "編集済", "UP済", "台本完", "未"], key="bulk_status")
        
        if st.button("一括更新実行"):
            df = bulk_update_status(df, start_ep, end_ep, new_status)
            save_data(sheet_name, df)
            st.success(f"{start_ep} 〜 {end_ep} を「{new_status}」に更新しました！")
            st.rerun()
    
    # ステータス凡例
    st.caption("**ステータス凡例：** ✅ UP済 | ✂️ 編集済 | 🎬 撮影済 | 📝 台本完 | ⏳ 未")
    
    # ラジオボタンでエピソード選択
    status_icons = {"UP済": "✅", "編集済": "✂️", "撮影済": "🎬", "台本完": "📝", "未": "⏳"}
    options = [f"{status_icons.get(row['ステータス'], '⏳')} {row['No']} ({row['日付']} {row['曜日']})" for _, row in df.iterrows()]
    
    selected_option = st.radio(
        "エピソードを選択",
        options,
        index=st.session_state.selected_index,
        key="schedule_radio"
    )
    
    # 選択されたインデックスを更新
    st.session_state.selected_index = options.index(selected_option)
    selected_row = df.iloc[st.session_state.selected_index]
    
    # 編集フォーム
    st.markdown("---")
    st.subheader(f"✏️ {selected_row['No']} の詳細")
    
    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input("タイトル", value=selected_row.get("タイトル", ""), key="title_input")
    with col2:
        status = st.selectbox(
            "ステータス",
            ["未", "台本完", "撮影済", "編集済", "UP済"],
            index=["未", "台本完", "撮影済", "編集済", "UP済"].index(selected_row.get("ステータス", "未")),
            key="status_select"
        )
    
    script = st.text_area("台本", value=selected_row.get("台本", ""), height=200, key="script_input")
    
    if st.button("💾 保存"):
        df.at[st.session_state.selected_index, "タイトル"] = title
        df.at[st.session_state.selected_index, "台本"] = script
        df.at[st.session_state.selected_index, "ステータス"] = status
        save_data(sheet_name, df)
        st.success("保存しました！")
        st.rerun()
    
    # --- 台本を見る・書く ---
    st.markdown("---")
    st.subheader("📝 台本を見る・書く")
    
    # 編集/プレビュー切り替え
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✏️ 編集モード", use_container_width=True):
            st.session_state.preview_mode = False
    with col2:
        if st.button("👁️ プレビューモード", use_container_width=True):
            st.session_state.preview_mode = True
    
    # プレビューモードの初期値
    if "preview_mode" not in st.session_state:
        st.session_state.preview_mode = False
    
    # 前へ・次へナビゲーション
    nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
    
    with nav_col1:
        if st.button("⬅️ 前へ", key="prev_button"):
            if st.session_state.script_index > 0:
                st.session_state.script_index -= 1
                st.rerun()
    
    with nav_col2:
        current_script_row = df.iloc[st.session_state.script_index]
        st.info(f"📌 現在：{current_script_row['No']} - {current_script_row.get('タイトル', 'タイトル未定')}")
    
    with nav_col3:
        if st.button("次へ ➡️", key="next_button"):
            if st.session_state.script_index < len(df) - 1:
                st.session_state.script_index += 1
                st.rerun()
    
    # 編集モード
    if not st.session_state.preview_mode:
        st.caption("**台本フォーマットガイド:**")
        st.code("赤：「Tomomiのセリフ」\n青：「Dowie009のセリフ」\n黒：「【ナレーションや指示】」")
        
        current_script = current_script_row.get("台本", "")
        edited_script = st.text_area(
            "台本を編集",
            value=current_script,
            height=300,
            key=f"script_edit_{st.session_state.script_index}"
        )
        
        if st.button("💾 台本を保存", key="save_script_button"):
            df.at[st.session_state.script_index, "台本"] = edited_script
            save_data(sheet_name, df)
            st.success(f"{current_script_row['No']} の台本を保存しました！")
            st.rerun()
    
    # プレビューモード
    else:
        st.markdown("### 🎬 プレビュー")
        current_script = current_script_row.get("台本", "")
        render_colored_preview(current_script)

# --- モバイル版：シンプル表示 ---
else:
    st.markdown("---")
    st.subheader("📖 スケジュール（閲覧専用）")
    
    # シンプルな表示
    status_icons = {"UP済": "✅", "編集済": "✂️", "撮影済": "🎬", "台本完": "📝", "未": "⏳"}
    
    for _, row in df.iterrows():
        icon = status_icons.get(row["ステータス"], "⏳")
        st.markdown(f"{icon} **{row['No']}** ({row['日付']} {row['曜日']}) - {row.get('タイトル', 'タイトル未定')}")
    
    st.markdown("---")
    st.subheader("📝 台本プレビュー")
    
    # エピソード選択（シンプル）
    selected_ep = st.selectbox("エピソードを選択", df["No"].tolist(), key="mobile_ep_select")
    selected_row = df[df["No"] == selected_ep].iloc[0]
    
    st.markdown(f"### {selected_ep} - {selected_row.get('タイトル', 'タイトル未定')}")
    render_colored_preview(selected_row.get("台本", ""))

# サイドバー：情報表示
if not mobile_mode:
    st.sidebar.markdown("---")
    st.sidebar.info(f"**現在のモード:** {'📱 モバイル' if mobile_mode else '💻 PC'}")
    st.sidebar.caption("📊 [Google Sheets で直接編集](https://docs.google.com/spreadsheets/d/1ZAWJdojWmlkspv0YnxjsVg9secrdKNP2sgbDAclcNpI/edit)")
