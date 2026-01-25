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
# Version: 17.0.0 - Dowie009 & Tomomi 色分け強化版
# ==============================================

# --- 1. 基本設定 ---
st.set_page_config(page_title="アニ無理 制作ノート", layout="wide", page_icon="☕", initial_sidebar_state="expanded")
is_mobile_from_url = st.query_params.get("mobile", "false").lower() == "true"

# デザイン (8.2.0の雰囲気を守りつつ、台本の視認性をアップ)
st.markdown("""
    <style>
    .stApp { background-color: #EFEBD6; color: #4A3B2A; }
    h1, h2, h3, h4, h5, h6, p, label, span, div, li { color: #4A3B2A !important; font-family: "Yu Mincho", serif; }
    [data-testid="stSidebar"] { background-color: #E6DCCF; border-right: 1px solid #C0B2A0; }
    .stTextInput input, .stDateInput input, .stTextArea textarea {
        background-color: #FFFAF0 !important; color: #3E2723 !important; border: 1px solid #A1887F;
    }
    /* ドロップダウン全体のスタイル */
    .stSelectbox div[data-baseweb="select"] { background-color: #FFFAF0 !important; border: 1px solid #A1887F; }
    .stSelectbox div[data-baseweb="select"] span { color: #3E2723 !important; }
    .stSelectbox svg { fill: #3E2723 !important; }
    /* ドロップダウンメニューのオプション */
    [data-baseweb="menu"] { background-color: #FFFAF0 !important; }
    [data-baseweb="menu"] li { background-color: #FFFAF0 !important; color: #3E2723 !important; }
    [data-baseweb="menu"] li:hover { background-color: #E6DCCF !important; }
    [role="listbox"] { background-color: #FFFAF0 !important; }
    [role="option"] { background-color: #FFFAF0 !important; color: #3E2723 !important; }
    [role="option"]:hover { background-color: #E6DCCF !important; }
    /* 選択済みの表示部分 */
    [data-baseweb="select"] > div { background-color: #FFFAF0 !important; }
    [data-baseweb="select"] > div > div { color: #3E2723 !important; }
    /* ラジオボタンのスタイル - 未選択は白+縁+中央に点、選択中は赤 */
    [data-baseweb="radio"] > div:first-child {
        background-color: #FFFAF0 !important;
        border: 2px solid #A1887F !important;
        box-shadow: inset 0 0 0 3px #FFFAF0, inset 0 0 0 6px #C0B2A0 !important;
    }
    [data-baseweb="radio"][aria-checked="true"] > div:first-child {
        background-color: #E53935 !important;
        border-color: #E53935 !important;
        box-shadow: none !important;
    }
    [data-baseweb="radio"] div { background-color: transparent !important; }
    [data-baseweb="radio"][aria-checked="true"] div:first-child div { background-color: #E53935 !important; }
    /* サイドバーのラジオボタンも同様に */
    [data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child {
        background-color: #FFFAF0 !important;
        border: 2px solid #A1887F !important;
        box-shadow: inset 0 0 0 3px #FFFAF0, inset 0 0 0 6px #C0B2A0 !important;
    }
    [data-testid="stSidebar"] [data-baseweb="radio"][aria-checked="true"] > div:first-child {
        background-color: #E53935 !important;
        border-color: #E53935 !important;
        box-shadow: none !important;
    }
    /* 選択中の行を目立たせる（背景色+左に赤いバー+太字） */
    label:has([data-baseweb="radio"][aria-checked="true"]) {
        background-color: #FFF8E1 !important;
        border-left: 4px solid #E53935 !important;
        border-radius: 4px !important;
        padding: 4px 8px !important;
        margin-left: -4px !important;
        display: block !important;
    }
    label:has([data-baseweb="radio"][aria-checked="true"]) p {
        font-weight: bold !important;
        color: #C62828 !important;
    }
    .stButton>button { background-color: #D7CCC8; color: #3E2723 !important; border-radius: 4px; font-weight: bold; width: 100%; }
    
    /* 台本の文字スタイル */
    .red-text { color: #E53935 !important; font-size: 1.15em; line-height: 1.8; margin-bottom: 8px; }
    .blue-text { color: #1E88E5 !important; font-size: 1.15em; line-height: 1.8; margin-bottom: 8px; }
    .black-text { color: #212121 !important; font-size: 1.05em; line-height: 1.8; margin-bottom: 8px; }
    
    .preview-box { background-color: #FFFAF0; padding: 25px; border-radius: 12px; border: 2px solid #A1887F; min-height: 400px; box-shadow: inset 0 0 10px rgba(0,0,0,0.05); }
    .version-badge { background-color: #4CAF50; color: white; padding: 5px 10px; border-radius: 5px; font-size: 0.8em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 接続と保存機能 ---
@st.cache_resource(ttl=3600)
def connect_to_gsheets():
    try:
        key = json.loads(st.secrets["gcp"]["json_key"]) if isinstance(st.secrets["gcp"]["json_key"], str) else dict(st.secrets["gcp"]["json_key"])
        creds = Credentials.from_service_account_info(key, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open_by_url(st.secrets["SPREADSHEET_URL"]).sheet1
    except: return None

def load_data(_sheet):
    if _sheet is None: return None
    try:
        data = _sheet.get_all_records()
        df = pd.DataFrame(data).fillna("").astype(str)
        if "台本" in df.columns: df = df.rename(columns={"台本": "台本メモ"})
        return df
    except: return None

def safe_save(sheet, df):
    if df is None or len(df) == 0:
        st.error("🚨 データが空のため保存を中止しました。")
        return False
    try:
        save_df = df.copy()
        if "台本メモ" in save_df.columns: save_df = save_df.rename(columns={"台本メモ": "台本"})
        final_cols = ["No", "公開予定日", "曜日", "タイトル", "ステータス", "台本", "月"]
        save_df = save_df[final_cols]
        sheet.clear()
        sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
        return True
    except: return False

# --- 【強化版】色分けロジック ---
def colorize_script(text):
    if not isinstance(text, str) or text == "": 
        return "<p class='black-text'>台本を入力してください</p>"
    
    lines = text.split('\n')
    res = []
    for l in lines:
        line_strip = l.strip()
        if not line_strip:
            res.append("<br>")
            continue
        
        # Tomomi（赤色）: 大文字小文字、全角半角、スペースのゆらぎを許容
        if re.match(r'^(Tomomi|赤)\s*[：:]', line_strip, re.IGNORECASE):
            content = re.sub(r'^(Tomomi|赤)\s*[：:]\s*', '', line_strip, flags=re.IGNORECASE)
            res.append(f'<p class="red-text"><strong>Tomomi：</strong>{content}</p>')
        
        # Dowie009（青色）: 同上
        elif re.match(r'^(Dowie009|青)\s*[：:]', line_strip, re.IGNORECASE):
            content = re.sub(r'^(Dowie009|青)\s*[：:]\s*', '', line_strip, flags=re.IGNORECASE)
            res.append(f'<p class="blue-text"><strong>Dowie009：</strong>{content}</p>')
            
        else:
            res.append(f'<p class="black-text">{l}</p>')
    return ''.join(res)

# --- 3. メイン処理 ---
st.title("☕️ アニ無理 制作ノート")
st.markdown('<span class="version-badge">🛡 Version 17.0.0 - 色分け強化版</span>', unsafe_allow_html=True)

sheet = connect_to_gsheets()

if 'notebook_df' not in st.session_state:
    raw = load_data(sheet)
    if raw is not None: st.session_state.notebook_df = raw
    else: st.error("接続失敗"); st.stop()

# ステート
if 'cur_m' not in st.session_state: st.session_state.cur_m = datetime.now().month
if 'cur_y' not in st.session_state: st.session_state.cur_y = datetime.now().year
if 'sel_idx' not in st.session_state: st.session_state.sel_idx = 0
if 'v_mode' not in st.session_state: st.session_state.v_mode = "preview"

# サイドバー
with st.sidebar:
    st.header("⚙️ 設定")
    is_mobile = st.radio("表示モード", ["🖥 PC版", "📱 スマホ版"], index=1 if is_mobile_from_url else 0) == "📱 スマホ版"
    
    st.divider(); st.subheader("📅 月移動")
    c1, c2, c3 = st.columns([1,2,1])
    if c1.button("◀"):
        if st.session_state.cur_m == 1: st.session_state.cur_m = 12; st.session_state.cur_y -= 1
        else: st.session_state.cur_m -= 1
        st.session_state.sel_idx = 0; st.rerun()
    c2.markdown(f"<center><b>{st.session_state.cur_m}月</b></center>", unsafe_allow_html=True)
    if c3.button("▶"):
        if st.session_state.cur_m == 12: st.session_state.cur_m = 1; st.session_state.cur_y += 1
        else: st.session_state.cur_m += 1
        st.session_state.sel_idx = 0; st.rerun()

    st.divider(); st.subheader("📝 台本ルール")
    st.info("行の最初に名前を書くと色が変わります")
    st.markdown("""
    - **Tomomi：** → <span style='color:#E53935; font-weight:bold;'>赤色</span>
    - **Dowie009：** → <span style='color:#1E88E5; font-weight:bold;'>青色</span>
    <br><small>※「Tomomi : 」のようにスペースが入ってもOK！</small>
    """, unsafe_allow_html=True)

    if not is_mobile:
        st.divider()
        with st.expander("🔄 ステータス一括更新"):
            m_eps = st.session_state.notebook_df[st.session_state.notebook_df['月'] == str(st.session_state.cur_m)]
            if not m_eps.empty:
                nos = m_eps['No'].tolist()
                s_n = st.selectbox("開始", nos); e_n = st.selectbox("終了", nos, index=len(nos)-1)
                stt = st.selectbox("状態", ["未","台本完","撮影済","編集済","UP済"])
                if st.button("一括更新"):
                    targets = nos[nos.index(s_n):nos.index(e_n)+1]
                    st.session_state.notebook_df.loc[st.session_state.notebook_df['No'].isin(targets), 'ステータス'] = stt
                    if safe_save(sheet, st.session_state.notebook_df): st.success("更新！"); time.sleep(0.5); st.rerun()

# 描画
df = st.session_state.notebook_df
curr_df = df[df['月'] == str(st.session_state.cur_m)].copy()

if not curr_df.empty:
    fin = curr_df[curr_df["ステータス"].isin(["編集済", "UP済"])]
    st.metric("📊 ストック状況", f"{len(fin)} 本", f"{fin['公開予定日'].iloc[-1]} まで" if not fin.empty else "在庫なし")
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
        sel = n2.selectbox("選択", [o[0] for o in opts], index=st.session_state.sel_idx, label_visibility="collapsed")
        st.session_state.sel_idx = [o[0] for o in opts].index(sel)
        if n3.button("➡") and st.session_state.sel_idx < len(opts)-1: st.session_state.sel_idx += 1; st.rerun()
        
        row_idx = opts[st.session_state.sel_idx][1]
        row = df.loc[row_idx]
        if row['ステータス'] != "UP済" and st.button("✅ UP済にする", type="primary"):
            st.session_state.notebook_df.at[row_idx, 'ステータス'] = "UP済"
            safe_save(sheet, st.session_state.notebook_df); st.balloons(); st.rerun()
        
        st.markdown(f'<div class="preview-box">{colorize_script(row["台本メモ"])}</div>', unsafe_allow_html=True)
    
    else:
        # PC版
        c_l, c_r = st.columns([1.3, 1])
        with c_l:
            st.subheader("🗓 スケジュール帳")
            # 現在選択中を表示
            current_opt = opts[st.session_state.sel_idx][0]
            st.markdown(f'<div style="background-color:#FFF8E1; border-left:4px solid #E53935; padding:8px 12px; margin-bottom:10px; border-radius:4px;"><strong style="color:#C62828;">📍 選択中：</strong> {current_opt}</div>', unsafe_allow_html=True)
            # 選択中の行を目立たせるためにカスタム表示
            for idx, (label, row_i) in enumerate(opts):
                is_selected = idx == st.session_state.sel_idx
                if is_selected:
                    # 選択中: 黄色背景+赤い左バー+太字赤文字
                    if st.button(f"🔴 {label}", key=f"opt_{idx}", use_container_width=True):
                        st.session_state.sel_idx = idx
                        st.rerun()
                else:
                    # 未選択: 通常表示
                    if st.button(f"⚪ {label}", key=f"opt_{idx}", use_container_width=True):
                        st.session_state.sel_idx = idx
                        st.rerun()
        with c_r:
            row_idx = opts[st.session_state.sel_idx][1]
            row = df.loc[row_idx]
            st.subheader("🎬 台本編集")
            tit = st.text_input("タイトル", value=row['タイトル'])
            sta = st.selectbox("状態", ["未","台本完","撮影済","編集済","UP済"], index=["未","台本完","撮影済","編集済","UP済"].index(row['ステータス']))
            if st.button("✏️ 編集" if st.session_state.v_mode=="preview" else "👁 プレビュー"):
                st.session_state.v_mode = "edit" if st.session_state.v_mode=="preview" else "preview"; st.rerun()
            
            if st.session_state.v_mode == "edit":
                tx = st.text_area("内容", value=row['台本メモ'], height=450)
                if st.button("💾 この1件を即時保存", type="primary"):
                    st.session_state.notebook_df.at[row_idx, 'タイトル'], st.session_state.notebook_df.at[row_idx, 'ステータス'], st.session_state.notebook_df.at[row_idx, '台本メモ'] = tit, sta, tx
                    if safe_save(sheet, st.session_state.notebook_df): st.success("保存完了！"); time.sleep(0.5); st.rerun()
            else:
                st.markdown(f'<div class="preview-box">{colorize_script(row["台本メモ"])}</div>', unsafe_allow_html=True)
else:
    st.warning("今月のデータがありません。")
