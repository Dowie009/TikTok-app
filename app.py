import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, timedelta
import time
import re
import calendar

# ==============================================
# 🔥 強制リロード設定（キャッシュバスター）
# Version: 8.6.0 - 2025-12-30 完全版
# ==============================================
# この文字列を変えるだけでスマホに「更新」を強制するよ
LAST_UPDATE = "20251230_2100"

st.set_page_config(
    page_title="アニ無理 制作ノート", 
    layout="wide", 
    page_icon="☕",
    initial_sidebar_state="expanded"
)

# URLパラメータからモード判定
query_params = st.query_params
is_mobile_from_url = query_params.get("mobile", "false").lower() == "true"

# デザイン（モバイル対応強化）
st.markdown(f"""
    <style>
    /* キャッシュ識別子: {LAST_UPDATE} */
    .stApp {{ background-color: #EFEBD6; color: #4A3B2A; }}
    h1, h2, h3, h4, h5, h6, p, label, span, div, li {{
        color: #4A3B2A !important;
        font-family: "Hiragino Mincho ProN", "Yu Mincho", serif;
    }}
    /* モバイルでボタンを押しやすく大きくする */
    .stButton>button {{
        width: 100%;
        min-height: 50px;
        margin: 5px 0;
        background-color: #D7CCC8;
        font-weight: bold;
    }}
    .version-badge {{ background-color: #FF7043; color: white; padding: 5px 10px; border-radius: 5px; font-size: 0.8em; }}
    </style>
    """, unsafe_allow_html=True)

# --- スプレッドシート接続 ---
@st.cache_resource(ttl=600)
def connect_to_gsheets():
    try:
        json_key_data = st.secrets["gcp"]["json_key"]
        key_dict = json.loads(json_key_data) if isinstance(json_key_data, str) else dict(json_key_data)
        creds = Credentials.from_service_account_info(key_dict, scopes=[
            "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)
        return client.open_by_url(st.secrets["SPREADSHEET_URL"]).sheet1
    except Exception as e:
        st.error(f"接続エラー: {e}"); return None

@st.cache_data(ttl=300)
def load_data_from_sheet(_sheet):
    if _sheet is None: return None
    try:
        data = _sheet.get_all_records()
        if not data: return pd.DataFrame(columns=["No", "公開予定日", "曜日", "タイトル", "ステータス", "台本"])
        df = pd.DataFrame(data)
        if "台本" in df.columns: df = df.rename(columns={"台本": "台本メモ"})
        return df
    except: return None

def save_data_to_sheet(sheet, df):
    if sheet is None: return False
    try:
        sheet.clear()
        save_df = df.copy()
        if "台本メモ" in save_df.columns: save_df = save_df.rename(columns={"台本メモ": "台本"})
        cols_to_save = [c for c in save_df.columns if c not in ["年", "月"]]
        sheet.update([cols_to_save] + save_df[cols_to_save].values.tolist())
        load_data_from_sheet.clear(); return True
    except: return False

# --- スケジュール生成 ---
def generate_monthly_schedule(year, month, start_episode):
    schedules = []
    episode_no = start_episode
    _, last_day = calendar.monthrange(year, month)
    for day in range(1, last_day + 1):
        curr_date = datetime(year, month, day)
        if curr_date.weekday() < 5:
            schedules.append({
                "No": f"#{episode_no}", "公開予定日": f"{month}/{day}",
                "曜日": ["月","火","水","木","金"][curr_date.weekday()],
                "タイトル": "", "ステータス": "未", "台本メモ": "", "年": year, "月": month
            })
            episode_no += 1
    return pd.DataFrame(schedules)

def ensure_all_months_data(df):
    if '年' not in df.columns: df['年'] = 2025
    if '月' not in df.columns: df['月'] = pd.to_datetime(df['公開予定日'], format='%m/%d', errors='coerce').dt.month
    
    today = datetime.now()
    # 12月、1月、2月のデータを確実に作る
    for i in range(3):
        target_date = today + timedelta(days=31*i)
        y, m = target_date.year, target_date.month
        if df[(df['年'] == y) & (df['月'] == m)].empty:
            last_no = 85 if df.empty else int(re.sub(r'\D', '', str(df['No'].iloc[-1]))) + 1
            df = pd.concat([df, generate_monthly_schedule(y, m, last_no)], ignore_index=True)
    return df

# --- メイン処理 ---
st.title("☕️ アニ無理 制作ノート")
st.markdown(f'<span class="version-badge">最新更新: {LAST_UPDATE} (Version 8.6.0)</span>', unsafe_allow_html=True)

sheet = connect_to_gsheets()
raw_df = load_data_from_sheet(sheet)

if 'current_month' not in st.session_state: st.session_state.current_month = datetime.now().month
if 'current_year' not in st.session_state: st.session_state.current_year = datetime.now().year
if 'selected_row_index' not in st.session_state: st.session_state.selected_row_index = 0

def move_month(dir):
    if dir == "next":
        if st.session_state.current_month == 12: st.session_state.current_month = 1; st.session_state.current_year += 1
        else: st.session_state.current_month += 1
    elif dir == "prev":
        if st.session_state.current_month == 1: st.session_state.current_month = 12; st.session_state.current_year -= 1
        else: st.session_state.current_month -= 1
    else:
        st.session_state.current_month = datetime.now().month; st.session_state.current_year = datetime.now().year
    st.session_state.selected_row_index = 0; st.rerun()

# サイドバー
with st.sidebar:
    st.header("⚙️ 設定")
    # モバイルならデフォルトをスマホ版にする
    device_options = ["🖥 PC版", "📱 スマホ版"]
    default_idx = 1 if (is_mobile_from_url or st.session_state.get('is_mobile', False)) else 0
    device_mode = st.radio("表示モード", device_options, index=default_idx)
    is_mobile = device_mode == "📱 スマホ版"
    st.session_state.is_mobile = is_mobile

# 描画
if raw_df is not None:
    df = ensure_all_months_data(raw_df)
    st.session_state.notebook_df = df
    curr_df = df[(df['年'] == st.session_state.current_year) & (df['月'] == st.session_state.current_month)].copy()

    # 月移動ナビ (PC/スマホ共通で見やすく配置)
    st.markdown(f"### <center>{st.session_state.current_year}年 {st.session_state.current_month}月</center>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.button("◀ 前月", on_click=move_month, args=("prev",))
    with c2: st.button("📍 今月", on_click=move_month, args=("today",))
    with c3: st.button("次月 ▶", on_click=move_month, args=("next",))

    if not curr_df.empty:
        options = []
        for i, r in curr_df.iterrows():
            m = {"UP済":"✅","編集済":"✂️","撮影済":"🎬","台本完":"📝"}.get(r['ステータス'], "⏳")
            options.append((f"{m} {r['No']} | {r['公開予定日']} | {r['タイトル'] or '未定'}", i))
        
        st.divider()
        sel = st.selectbox("エピソード選択", [o[0] for o in options], index=st.session_state.selected_row_index)
        st.session_state.selected_row_index = [o[0] for o in options].index(sel)
        
        row_idx = options[st.session_state.selected_row_index][1]
        row = df.loc[row_idx]
        
        # PC版ならタイトル・ステータス編集、スマホ版ならUPボタン
        if not is_mobile:
            t = st.text_input("タイトル", value=row['タイトル'])
            s = st.selectbox("状態", ["未","台本完","撮影済","編集済","UP済"], index=["未","台本完","撮影済","編集済","UP済"].index(row['ステータス']))
            txt = st.text_area("台本", value=row['台本メモ'], height=300)
            if st.button("💾 この内容を保存"):
                df.at[row_idx, 'タイトル'], df.at[row_idx, 'ステータス'], df.at[row_idx, '台本メモ'] = t, s, txt
                if save_data_to_sheet(sheet, df): st.success("保存しました！")
        else:
            if row['ステータス'] != "UP済":
                if st.button("✅ このエピソードを【UP済】にする"):
                    df.at[row_idx, 'ステータス'] = "UP済"
                    if save_data_to_sheet(sheet, df): st.balloons(); st.rerun()
            
            # 台本プレビュー
            st.markdown(f'<div style="background-color:#FFFAF0; padding:15px; border:1px solid #A1887F;">{row["台本メモ"]}</div>', unsafe_allow_html=True)
    else:
        st.warning("データがありません。「次月」ボタンで生成してみてください。")
