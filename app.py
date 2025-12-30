import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, timedelta
import time
import re

# ==============================================
# ☕️ アニ無理 制作ノート 
# Version: 12.0.0 - 超爆速・2026対応・擬似即時反映版
# ==============================================

# --- 1. 基本設定 (最優先) ---
st.set_page_config(page_title="アニ無理 制作ノート", layout="wide", page_icon="☕", initial_sidebar_state="expanded")

# CSS: 8.2.0のデザインを100%継承
st.markdown("""
    <style>
    .stApp { background-color: #EFEBD6; color: #4A3B2A; }
    h1, h2, h3, h4, h5, h6, p, label, span, div, li { color: #4A3B2A !important; font-family: "Yu Mincho", serif; }
    [data-testid="stSidebar"] { background-color: #E6DCCF; border-right: 1px solid #C0B2A0; }
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {
        background-color: #FFFAF0 !important; color: #3E2723 !important; border: 1px solid #A1887F;
    }
    .stButton>button { background-color: #D7CCC8; color: #3E2723 !important; border-radius: 4px; padding: 10px 20px; font-weight: bold; }
    .red-text { color: #E53935 !important; font-weight: bold; }
    .blue-text { color: #1E88E5 !important; font-weight: bold; }
    .preview-box { background-color: #FFFAF0; padding: 20px; border-radius: 8px; border: 2px solid #A1887F; min-height: 350px; }
    .version-badge { background-color: #4CAF50; color: white; padding: 5px 10px; border-radius: 5px; font-size: 0.8em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 接続とキャッシュ管理 ---
@st.cache_resource(ttl=3600)
def connect_to_gsheets():
    try:
        json_key = json.loads(st.secrets["gcp"]["json_key"]) if isinstance(st.secrets["gcp"]["json_key"], str) else dict(st.secrets["gcp"]["json_key"])
        creds = Credentials.from_service_account_info(json_key, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open_by_url(st.secrets["SPREADSHEET_URL"]).sheet1
    except: return None

@st.cache_data(ttl=600)
def load_data(_sheet):
    if _sheet is None: return None
    try:
        data = _sheet.get_all_records()
        df = pd.DataFrame(data).fillna("").astype(str)
        if "台本" in df.columns: df = df.rename(columns={"台本": "台本メモ"})
        return df
    except: return None

# 即時保存 (session_stateを先に書き換えるための関数)
def instant_save(sheet, df):
    try:
        save_df = df.copy()
        if "台本メモ" in save_df.columns: save_df = save_df.rename(columns={"台本メモ": "台本"})
        if "month_tmp" in save_df.columns: save_df = save_df.drop(columns=["month_tmp"])
        sheet.clear()
        sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
        return True
    except: return False

# --- 3. 2026年対応・自動カレンダー生成 ---
def generate_schedule(year, month, start_no):
    import calendar
    days = []
    curr_no = start_no
    _, last_day = calendar.monthrange(year, month)
    for day in range(1, last_day + 1):
        dt = datetime(year, month, day)
        if dt.weekday() < 5:
            days.append({"No": f"#{curr_no}", "公開予定日": f"{month}/{day}", "曜日": ["月","火","水","木","金"][dt.weekday()], "タイトル": "", "ステータス": "未", "台本メモ": ""})
            curr_no += 1
    return pd.DataFrame(days)

def sync_data(df):
    df['month_tmp'] = pd.to_datetime(df['公開予定日'], format='%m/%d', errors='coerce').dt.month
    existing = df['month_tmp'].unique().tolist()
    today = datetime.now()
    all_dfs = [df]
    # 今月〜再来月まで保証
    for i in range(3):
        target = today + timedelta(days=31*i)
        if target.month not in existing:
            last_no = 85 if df.empty else int(re.sub(r'\D', '', str(df['No'].iloc[-1]))) + 1
            all_dfs.append(generate_schedule(target.year, target.month, last_no))
    return pd.concat(all_dfs, ignore_index=True)

# --- 4. メイン処理 ---
st.title("☕️ アニ無理 制作ノート")
st.markdown('<span class="version-badge">🚀 Version 12.0.0 - 爆速・2026対応</span>', unsafe_allow_html=True)

sheet = connect_to_gsheets()
if 'notebook_df' not in st.session_state:
    raw = load_data(sheet)
    if raw is not None:
        st.session_state.notebook_df = sync_data(raw)
    else:
        st.error("接続失敗"); st.stop()

# ステート初期化
if 'cur_m' not in st.session_state: st.session_state.cur_m = datetime.now().month
if 'sel_idx' not in st.session_state: st.session_state.sel_idx = 0
if 'v_mode' not in st.session_state: st.session_state.v_mode = "preview"

# サイドバー
with st.sidebar:
    st.header("⚙️ 設定")
    is_mobile = st.radio("モード", ["🖥 PC版", "📱 スマホ版"], index=1 if st.query_params.get("mobile")=="true" else 0) == "📱 スマホ版"
    st.divider(); st.subheader("📅 月の切り替え")
    c1, c2, c3 = st.columns([1,2,1])
    if c1.button("◀"):
        st.session_state.cur_m = 12 if st.session_state.cur_m == 1 else st.session_state.cur_m - 1
        st.session_state.sel_idx = 0; st.rerun()
    c2.markdown(f"<center><b>{st.session_state.cur_m}月</b></center>", unsafe_allow_html=True)
    if c3.button("▶"):
        st.session_state.cur_m = 1 if st.session_state.cur_m == 12 else st.session_state.cur_m + 1
        st.session_state.sel_idx = 0; st.rerun()
    
    # 【PC版】一括更新
    if not is_mobile:
        st.divider()
        with st.expander("🔄 一括更新"):
            m_eps = st.session_state.notebook_df[pd.to_datetime(st.session_state.notebook_df['公開予定日'], format='%m/%d', errors='coerce').dt.month == st.session_state.cur_m]
            if not m_eps.empty:
                nos = m_eps['No'].tolist()
                s_n = st.selectbox("開始", nos); e_n = st.selectbox("終了", nos, index=len(nos)-1)
                stt = st.selectbox("新状態", ["未","台本完","撮影済","編集済","UP済"])
                if st.button("一括実行"):
                    targets = nos[nos.index(s_n):nos.index(e_n)+1]
                    st.session_state.notebook_df.loc[st.session_state.notebook_df['No'].isin(targets), 'ステータス'] = stt
                    instant_save(sheet, st.session_state.notebook_df)
                    st.success("更新しました！"); st.rerun()

# データ描画
df = st.session_state.notebook_df
df['month_tmp'] = pd.to_datetime(df['公開予定日'], format='%m/%d', errors='coerce').dt.month
curr_df = df[df['month_tmp'] == st.session_state.cur_m].copy()

if not curr_df.empty:
    fin = curr_df[curr_df["ステータス"].isin(["編集済", "UP済"])]
    st.metric("ストック状況", f"{len(fin)} 本", f"{fin['公開予定日'].iloc[-1]} まで" if not fin.empty else "在庫なし")
    st.divider()

    opts = []
    for i, r in curr_df.iterrows():
        m = {"UP済":"✅","編集済":"✂️","撮影済":"🎬","台本完":"📝"}.get(r['ステータス'], "⏳")
        opts.append((f"{m} {r['No']} | {r['公開予定日']} | {r['タイトル'] or '未定'}", i))
    
    if st.session_state.sel_idx >= len(opts): st.session_state.sel_idx = 0

    if is_mobile:
        # スマホ版
        n1, n2, n3 = st.columns([1, 3, 1])
        if n1.button("⬅") and st.session_state.sel_idx > 0: st.session_state.sel_idx -= 1; st.rerun()
        sel = n2.selectbox("選", [o[0] for o in opts], index=st.session_state.sel_idx, label_visibility="collapsed")
        st.session_state.sel_idx = [o[0] for o in opts].index(sel)
        if n3.button("➡") and st.session_state.sel_idx < len(opts)-1: st.session_state.sel_idx += 1; st.rerun()
        
        row_idx = opts[st.session_state.sel_idx][1]
        row = df.loc[row_idx]
        if row['ステータス'] != "UP済" and st.button("✅ UP済にする", type="primary", use_container_width=True):
            st.session_state.notebook_df.at[row_idx, 'ステータス'] = "UP済"
            instant_save(sheet, st.session_state.notebook_df); st.balloons(); st.rerun()
        
        # 台本表示 (ここを関数化せず直接描画してエラー回避)
        txt = str(row['台本メモ'])
        html = "".join([f'<p class="{"red-text" if l.startswith("赤：") else "blue-text" if l.startswith("青：") else "black-text"}">{l[2:] if (l.startswith("赤：") or l.startswith("青：")) else l}</p>' for l in txt.split("\n")])
        st.markdown(f'<div class="preview-box">{html if txt else "台本なし"}</div>', unsafe_allow_html=True)
    
    else:
        # PC版 (8.2.0レイアウト)
        c_l, c_r = st.columns([1.3, 1])
        with c_l:
            st.subheader("🗓 スケジュール帳")
            sel_l = st.radio("選択", [o[0] for o in opts], index=st.session_state.sel_idx, label_visibility="collapsed")
            st.session_state.sel_idx = [o[0] for o in opts].index(sel_l)
        with c_r:
            row_idx = opts[st.session_state.sel_idx][1]
            row = df.loc[row_idx]
            st.subheader("🎬 台本編集")
            tit = st.text_input("タイトル", value=row['タイトル'])
            sta = st.selectbox("状態", ["未","台本完","撮影済","編集済","UP済"], index=["未","台本完","撮影済","編集済","UP済"].index(row['ステータス']))
            if st.button("✏️ 編集" if st.session_state.v_mode=="preview" else "👁 プレビュー"):
                st.session_state.v_mode = "edit" if st.session_state.v_mode=="preview" else "preview"; st.rerun()
            
            if st.session_state.v_mode == "edit":
                tx = st.text_area("内容", value=row['台本メモ'], height=350)
                if st.button("💾 保存", type="primary"):
                    st.session_state.notebook_df.at[row_idx, 'タイトル'], st.session_state.notebook_df.at[row_idx, 'ステータス'], st.session_state.notebook_df.at[row_idx, '台本メモ'] = tit, sta, tx
                    instant_save(sheet, st.session_state.notebook_df); st.success("保存完了！"); st.rerun()
            else:
                txt = str(row['台本メモ'])
                html = "".join([f'<p class="{"red-text" if l.startswith("赤：") else "blue-text" if l.startswith("青：") else "black-text"}">{l[2:] if (l.startswith("赤：") or l.startswith("青：")) else l}</p>' for l in txt.split("\n")])
                st.markdown(f'<div class="preview-box">{html if txt else "台本なし"}</div>', unsafe_allow_html=True)
else:
    st.warning("データなし")
