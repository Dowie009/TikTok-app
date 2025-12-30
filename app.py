import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, timedelta
import time
import re

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

# --- 2. デザイン (ミルクティー・クラフト紙風) ---
st.markdown(f"""
    <style>
    .stApp {{ background-color: #EFEBD6; color: #4A3B2A; }}
    h1, h2, h3, h4, h5, h6, p, label, span, div, li {{
        color: #4A3B2A !important;
        font-family: "Hiragino Mincho ProN", "Yu Mincho", serif;
    }}
    [data-testid="stSidebar"] {{ background-color: #E6DCCF; border-right: 1px solid #C0B2A0; }}
    .stTextInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {{
        background-color: #FFFAF0 !important; color: #3E2723 !important; border: 1px solid #A1887F;
    }}
    .stButton>button {{
        background-color: #D7CCC8; color: #3E2723 !important; border: 1px solid #8D6E63;
        border-radius: 4px; font-size: 1.1em; padding: 12px 20px;
    }}
    .red-text {{ color: #E53935 !important; font-weight: bold; font-size: 1.1em; line-height: 1.8; }}
    .blue-text {{ color: #1E88E5 !important; font-weight: bold; font-size: 1.1em; line-height: 1.8; }}
    .black-text {{ color: #212121 !important; font-size: 1.0em; line-height: 1.8; }}
    .preview-box {{ background-color: #FFFAF0; padding: 20px; border-radius: 8px; border: 2px solid #A1887F; min-height: 300px; }}
    .version-badge {{ background-color: #4CAF50; color: white; padding: 5px 10px; border-radius: 5px; font-size: 0.9em; font-weight: bold; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. スプレッドシート接続機能 ---
@st.cache_resource(ttl=3600)
def connect_to_gsheets():
    try:
        json_key_data = st.secrets["gcp"]["json_key"]
        key_dict = json.loads(json_key_data) if isinstance(json_key_data, str) else dict(json_key_data)
        creds = Credentials.from_service_account_info(key_dict, scopes=[
            "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)
        sheet_url = st.secrets["SPREADSHEET_URL"]
        return client.open_by_url(sheet_url).sheet1
    except Exception as e:
        st.error(f"Google Sheets接続エラー: {e}"); return None

@st.cache_data(ttl=600)
def load_data_from_sheet(_sheet):
    if _sheet is None: return None
    try:
        time.sleep(0.3)
        data = _sheet.get_all_records()
        if not data: return None
        df = pd.DataFrame(data)
        if "台本" in df.columns: df = df.rename(columns={"台本": "台本メモ"})
        return df
    except: return None

def save_data_to_sheet(sheet, df):
    if sheet is None: return False
    try:
        time.sleep(0.3); sheet.clear()
        save_df = df.copy()
        if "台本メモ" in save_df.columns: save_df = save_df.rename(columns={"台本メモ": "台本"})
        # 補助列を除外
        cols = [c for c in save_df.columns if c not in ["月", "年"]]
        sheet.update([cols] + save_df[cols].values.tolist())
        load_data_from_sheet.clear(); return True
    except: return False

# --- 4. スケジュール生成 & 番号更新 ---
def generate_monthly_schedule(year, month, start_episode):
    import calendar
    schedules = []
    episode_no = start_episode
    _, last_day = calendar.monthrange(year, month)
    for day in range(1, last_day + 1):
        curr_date = datetime(year, month, day)
        if curr_date.weekday() < 5:
            schedules.append({
                "No": f"#{episode_no}", "公開予定日": f"{month}/{day}",
                "曜日": ["月","火","水","木","金","土","日"][curr_date.weekday()],
                "タイトル": "", "ステータス": "未", "台本メモ": ""
            })
            episode_no += 1
    return pd.DataFrame(schedules)

def ensure_all_months_data(df):
    df['月'] = pd.to_datetime(df['公開予定日'], format='%m/%d', errors='coerce').dt.month
    existing = df['月'].unique().tolist()
    all_data = [df]
    if 12 not in existing: all_data.append(generate_monthly_schedule(2025, 12, 48))
    if 1 not in existing: all_data.append(generate_monthly_schedule(2026, 1, 62))
    return pd.concat(all_data, ignore_index=True)

def update_episode_numbers(df, start_episode=48):
    for idx, row in df.iterrows():
        curr = str(row['No'])
        if curr.isdigit(): df.at[idx, 'No'] = f"#{start_episode + int(curr) - 1}"
    return df

def calculate_stock_deadline(df):
    fin = df[df["ステータス"].isin(["編集済", "UP済"])].copy()
    if len(fin) == 0: return None, "在庫なし", "撮影頑張りましょう！"
    return len(fin), f"{fin['公開予定日'].iloc[-1]} まで", "投稿可能！✨"

def colorize_script(text):
    if not text: return "<p>台本未入力</p>"
    lines = text.split('\n')
    res = []
    for l in lines:
        if l.startswith('赤：'): res.append(f'<p class="red-text">Tomomi：{l[2:]}</p>')
        elif l.startswith('青：'): res.append(f'<p class="blue-text">道ゐ：{l[2:]}</p>')
        else: res.append(f'<p class="black-text">{l}</p>')
    return ''.join(res)

# --- 5. メイン処理 ---
st.title("☕️ アニ無理 制作ノート")
st.markdown('<span class="version-badge">🔄 Version 8.4.0 - 自動・年またぎ完全対応版</span>', unsafe_allow_html=True)

sheet = connect_to_gsheets()
sheet_df = load_data_from_sheet(sheet)

if 'current_month' not in st.session_state: st.session_state.current_month = datetime.now().month
if 'current_year' not in st.session_state: st.session_state.current_year = datetime.now().year
if 'selected_row_index' not in st.session_state: st.session_state.selected_row_index = 0
if 'view_mode' not in st.session_state: st.session_state.view_mode = "preview"

def move_month(dir):
    if dir == "next":
        if st.session_state.current_month == 12: st.session_state.current_month = 1; st.session_state.current_year += 1
        else: st.session_state.current_month += 1
    elif dir == "prev":
        if st.session_state.current_month == 1: st.session_state.current_month = 12; st.session_state.current_year -= 1
        else: st.session_state.current_month -= 1
    elif dir == "today":
        st.session_state.current_month = datetime.now().month; st.session_state.current_year = datetime.now().year
    st.session_state.selected_row_index = 0; st.rerun()

# サイドバー
with st.sidebar:
    st.header("⚙️ 設定")
    is_mobile = st.radio("表示モード", ["🖥 PC版", "📱 スマホ版"], index=1 if is_mobile_from_url else 0) == "📱 スマホ版"
    st.divider(); st.subheader("📅 カレンダー切り替え")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: 
        if st.button("◀", key="s_prev"): move_month("prev")
    with c2: st.write(f"**{st.session_state.current_year}/{st.session_state.current_month}**")
    with c3: 
        if st.button("▶", key="s_next"): move_month("next")
    if st.button("📍 今月に戻る", use_container_width=True): move_month("today")

# 描画
if sheet_df is not None:
    df = ensure_all_months_data(sheet_df)
    st.session_state.notebook_df = df
    df['月_tmp'] = pd.to_datetime(df['公開予定日'], format='%m/%d', errors='coerce').dt.month
    curr_df = df[df['月_tmp'] == st.session_state.current_month].copy()

    if is_mobile:
        st.markdown(f"<center><h2>{st.session_state.current_year}年 {st.session_state.current_month}月</h2></center>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        with m1: 
            if st.button("◀ 前月", key="m_p"): move_month("prev")
        with m2: 
            if st.button("📍 今月", key="m_t"): move_month("today")
        with m3: 
            if st.button("次月 ▶", key="m_n"): move_month("next")
        st.divider()

    count, deadline, sub = calculate_stock_deadline(curr_df)
    st.metric("ストック", f"{count} 本", deadline)
    
    if not curr_df.empty:
        opts = []
        for i, r in curr_df.iterrows():
            m = {"UP済":"✅","編集済":"✂️","撮影済":"🎬","台本完":"📝"}.get(r['ステータス'], "⏳")
            opts.append((f"{m} {r['No']} | {r['公開予定日']} | {r['タイトル'] or '未定'}", i))
        
        if st.session_state.selected_row_index >= len(opts): st.session_state.selected_row_index = 0
        n1, n2, n3 = st.columns([1,3,1])
        with n1: 
            if st.button("⬅", key="r_p", disabled=st.session_state.selected_row_index==0):
                st.session_state.selected_row_index -= 1; st.rerun()
        with n2:
            sel = st.selectbox("選択", [o[0] for o in opts], index=st.session_state.selected_row_index, label_visibility="collapsed")
            st.session_state.selected_row_index = [o[0] for o in opts].index(sel)
        with n3:
            if st.button("➡", key="r_n", disabled=st.session_state.selected_row_index>=len(opts)-1):
                st.session_state.selected_row_index += 1; st.rerun()
        
        row = df.loc[opts[st.session_state.selected_row_index][1]]
        st.subheader(f"🎬 {row['No']} 台本")
        
        if not is_mobile:
            t = st.text_input("タイトル", value=row['タイトル'])
            s = st.selectbox("状態", ["未","台本完","撮影済","編集済","UP済"], index=["未","台本完","撮影済","編集済","UP済"].index(row['ステータス']))
            if st.button("✏️ 編集" if st.session_state.view_mode=="preview" else "👁 プレビュー"):
                st.session_state.view_mode = "edit" if st.session_state.view_mode=="preview" else "preview"; st.rerun()
            if st.session_state.view_mode == "edit":
                txt = st.text_area("内容", value=row['台本メモ'], height=300)
                if st.button("💾 保存"):
                    df.at[opts[st.session_state.selected_row_index][1], 'タイトル'] = t
                    df.at[opts[st.session_state.selected_row_index][1], 'ステータス'] = s
                    df.at[opts[st.session_state.selected_row_index][1], '台本メモ'] = txt
                    if save_data_to_sheet(sheet, df): st.success("保存！"); st.balloons()
            else:
                st.markdown(f'<div class="preview-box">{colorize_script(row["台本メモ"])}</div>', unsafe_allow_html=True)
        else:
            if row['ステータス'] != "UP済":
                if st.button("✅ UP済にする", type="primary", use_container_width=True):
                    df.at[opts[st.session_state.selected_row_index][1], 'ステータス'] = "UP済"
                    if save_data_to_sheet(sheet, df): st.balloons(); st.rerun()
            st.markdown(f'<div class="preview-box">{colorize_script(row["台本メモ"])}</div>', unsafe_allow_html=True)
