import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, timedelta
import time
import re
import calendar

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

# --- 2. デザイン ---
st.markdown("""
    <style>
    .stApp { background-color: #EFEBD6; color: #4A3B2A; }
    h1, h2, h3, h4, h5, h6, p, label, span, div, li {
        color: #4A3B2A !important;
        font-family: "Hiragino Mincho ProN", "Yu Mincho", serif;
    }
    [data-testid="stSidebar"] { background-color: #E6DCCF; border-right: 1px solid #C0B2A0; }
    .stTextInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {
        background-color: #FFFAF0 !important; color: #3E2723 !important; border: 1px solid #A1887F;
    }
    .stButton>button {
        background-color: #D7CCC8; color: #3E2723 !important; border: 1px solid #8D6E63;
        border-radius: 4px; font-size: 1.1em; padding: 12px 20px;
    }
    .red-text { color: #E53935 !important; font-weight: bold; font-size: 1.1em; line-height: 1.8; }
    .blue-text { color: #1E88E5 !important; font-weight: bold; font-size: 1.1em; line-height: 1.8; }
    .black-text { color: #212121 !important; font-size: 1.0em; line-height: 1.8; }
    .preview-box { background-color: #FFFAF0; padding: 20px; border-radius: 8px; border: 2px solid #A1887F; min-height: 300px; }
    .version-badge { background-color: #4CAF50; color: white; padding: 5px 10px; border-radius: 5px; font-size: 0.9em; font-weight: bold; }
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
        return client.open_by_url(st.secrets["SPREADSHEET_URL"]).sheet1
    except Exception as e:
        st.error(f"接続エラー: {e}"); return None

@st.cache_data(ttl=600)
def load_data_from_sheet(_sheet):
    if _sheet is None: return None
    try:
        time.sleep(0.3)
        data = _sheet.get_all_records()
        if not data: return pd.DataFrame(columns=["No", "公開予定日", "曜日", "タイトル", "ステータス", "台本"])
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
        # 保存時は補助用の「年」「月」列を除外
        cols_to_save = [c for c in save_df.columns if c not in ["年", "月"]]
        sheet.update([cols_to_save] + save_df[cols_to_save].values.tolist())
        load_data_from_sheet.clear(); return True
    except: return False

# --- 4. 自動スケジュール生成 (2026年対応版) ---
def generate_monthly_schedule(year, month, start_episode):
    schedules = []
    episode_no = start_episode
    _, last_day = calendar.monthrange(year, month)
    for day in range(1, last_day + 1):
        curr_date = datetime(year, month, day)
        if curr_date.weekday() < 5:  # 平日のみ
            schedules.append({
                "No": f"#{episode_no}", "公開予定日": f"{month}/{day}",
                "曜日": ["月","火","水","木","金"][curr_date.weekday()],
                "タイトル": "", "ステータス": "未", "台本メモ": "", "年": year, "月": month
            })
            episode_no += 1
    return pd.DataFrame(schedules)

def ensure_all_months_data(df):
    # 公開予定日から年・月を推測
    if '年' not in df.columns:
        df['年'] = datetime.now().year # 簡易的に今年のデータとする
    if '月' not in df.columns:
        df['月'] = pd.to_datetime(df['公開予定日'], format='%m/%d', errors='coerce').dt.month
    
    # 今月、来月、再来月の3ヶ月分を保証
    today = datetime.now()
    for i in range(3):
        target_date = today + timedelta(days=31*i)
        y, m = target_date.year, target_date.month
        if df[(df['年'] == y) & (df['月'] == m)].empty:
            last_no = 85 if df.empty else int(re.sub(r'\D', '', str(df['No'].iloc[-1]))) + 1
            new_month_df = generate_monthly_schedule(y, m, last_no)
            df = pd.concat([df, new_month_df], ignore_index=True)
    return df

# --- 5. ロジック関数 ---
def calculate_stock_deadline(df):
    finished = df[df["ステータス"].isin(["編集済", "UP済"])].copy()
    if len(finished) == 0: return 0, "在庫なし", "撮影頑張りましょう！"
    return len(finished), f"{finished['公開予定日'].iloc[-1]} まで", "投稿可能！✨"

def colorize_script(text):
    if not text: return "<p>台本を入力してください</p>"
    lines = text.split('\n')
    res = []
    for l in lines:
        if l.startswith('赤：'): res.append(f'<p class="red-text">Tomomi：{l[2:]}</p>')
        elif l.startswith('青：'): res.append(f'<p class="blue-text">道ゐ：{l[2:]}</p>')
        else: res.append(f'<p class="black-text">{l}</p>')
    return ''.join(res)

# --- 6. メイン処理 ---
st.title("☕️ アニ無理 制作ノート")
st.markdown('<span class="version-badge">🔄 Version 8.5.0 - 完全自動化版</span>', unsafe_allow_html=True)

# データ接続
sheet = connect_to_gsheets()
raw_df = load_data_from_sheet(sheet)

# セッション状態
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
    else:
        st.session_state.current_month = datetime.now().month; st.session_state.current_year = datetime.now().year
    st.session_state.selected_row_index = 0; st.rerun()

# サイドバー
with st.sidebar:
    st.header("⚙️ 設定")
    is_mobile = st.radio("表示モード", ["🖥 PC版", "📱 スマホ版"], index=1 if is_mobile_from_url else 0) == "📱 スマホ版"
    
    if not is_mobile and raw_df is not None:
        with st.expander("🔄 一括更新"):
            df_all = ensure_all_months_data(raw_df)
            m_eps = df_all[(df_all['年']==st.session_state.current_year) & (df_all['月']==st.session_state.current_month)]
            if not m_eps.empty:
                eps = m_eps['No'].tolist()
                s_ep = st.selectbox("開始", eps); e_ep = st.selectbox("終了", eps, index=len(eps)-1)
                stat = st.selectbox("ステータス", ["未", "台本完", "撮影済", "編集済", "UP済"])
                if st.button("一括実行"):
                    targets = eps[eps.index(s_ep):eps.index(e_ep)+1]
                    df_all.loc[df_all['No'].isin(targets), 'ステータス'] = stat
                    if save_data_to_sheet(sheet, df_all): st.success("更新！"); time.sleep(1); st.rerun()

    st.divider(); st.subheader("📅 月移動")
    c1, c2, c3 = st.columns([1,2,1])
    with c1: 
        if st.button("◀", key="s_prev"): move_month("prev")
    with c2: st.write(f"**{st.session_state.current_year}/{st.session_state.current_month}**")
    with c3: 
        if st.button("▶", key="s_next"): move_month("next")

# メイン表示
if raw_df is not None:
    df = ensure_all_months_data(raw_df)
    st.session_state.notebook_df = df
    curr_df = df[(df['年'] == st.session_state.current_year) & (df['月'] == st.session_state.current_month)].copy()

    if is_mobile:
        st.markdown(f"<center><h2>{st.session_state.current_year}年 {st.session_state.current_month}月</h2></center>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns([1,1,1])
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
        options = []
        for i, r in curr_df.iterrows():
            m = {"UP済":"✅","編集済":"✂️","撮影済":"🎬","台本完":"📝"}.get(r['ステータス'], "⏳")
            options.append((f"{m} {r['No']} | {r['公開予定日']} | {r['タイトル'] or '未定'}", i))
        
        if st.session_state.selected_row_index >= len(options): st.session_state.selected_row_index = 0
        
        # 行選択ナビ
        n1, n2, n3 = st.columns([1,3,1])
        with n1: 
            if st.button("⬅", key="row_p", disabled=st.session_state.selected_row_index==0):
                st.session_state.selected_row_index -= 1; st.rerun()
        with n2:
            sel = st.selectbox("選択", [o[0] for o in options], index=st.session_state.selected_row_index, label_visibility="collapsed")
            st.session_state.selected_row_index = [o[0] for o in options].index(sel)
        with n3:
            if st.button("➡", key="row_n", disabled=st.session_state.selected_row_index>=len(options)-1):
                st.session_state.selected_row_index += 1; st.rerun()
        
        row = df.loc[options[st.session_state.selected_row_index][1]]
        st.subheader(f"🎬 {row['No']} 台本")
        
        if not is_mobile:
            # PC版：編集機能
            t = st.text_input("タイトル", value=row['タイトル'])
            s = st.selectbox("状態", ["未","台本完","撮影済","編集済","UP済"], index=["未","台本完","撮影済","編集済","UP済"].index(row['ステータス']))
            if st.button("✏️ 編集" if st.session_state.view_mode=="preview" else "👁 プレビュー"):
                st.session_state.view_mode = "edit" if st.session_state.view_mode=="preview" else "preview"; st.rerun()
            
            if st.session_state.view_mode == "edit":
                txt = st.text_area("内容", value=row['台本メモ'], height=300)
                if st.button("💾 保存"):
                    df.at[options[st.session_state.selected_row_index][1], 'タイトル'] = t
                    df.at[options[st.session_state.selected_row_index][1], 'ステータス'] = s
                    df.at[options[st.session_state.selected_row_index][1], '台本メモ'] = txt
                    if save_data_to_sheet(sheet, df): st.success("保存！")
            else:
                st.markdown(f'<div class="preview-box">{colorize_script(row["台本メモ"])}</div>', unsafe_allow_html=True)
        else:
            # スマホ版：閲覧＆UP済ボタン
            if row['ステータス'] != "UP済":
                if st.button("✅ UP済にする", type="primary", use_container_width=True):
                    df.at[options[st.session_state.selected_row_index][1], 'ステータス'] = "UP済"
                    save_data_to_sheet(sheet, df); st.rerun()
            st.markdown(f'<div class="preview-box">{colorize_script(row["台本メモ"])}</div>', unsafe_allow_html=True)
