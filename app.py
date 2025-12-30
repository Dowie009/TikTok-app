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
# Version: 14.0.0 - 爆速反映・完全データ保護版
# ==============================================

# --- 1. 基本設定とモバイル判定 ---
st.set_page_config(page_title="アニ無理 制作ノート", layout="wide", page_icon="☕", initial_sidebar_state="expanded")
is_mobile_from_url = st.query_params.get("mobile", "false").lower() == "true"

# デザイン (8.2.0継承)
st.markdown("""
    <style>
    .stApp { background-color: #EFEBD6; color: #4A3B2A; }
    h1, h2, h3, h4, h5, h6, p, label, span, div, li { color: #4A3B2A !important; font-family: "Yu Mincho", serif; }
    [data-testid="stSidebar"] { background-color: #E6DCCF; border-right: 1px solid #C0B2A0; }
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {
        background-color: #FFFAF0 !important; color: #3E2723 !important; border: 1px solid #A1887F;
    }
    .stButton>button { background-color: #D7CCC8; color: #3E2723 !important; border-radius: 4px; font-weight: bold; width: 100%; }
    .red-text { color: #E53935 !important; font-weight: bold; }
    .blue-text { color: #1E88E5 !important; font-weight: bold; }
    .preview-box { background-color: #FFFAF0; padding: 20px; border-radius: 8px; border: 2px solid #A1887F; min-height: 350px; }
    .version-badge { background-color: #4CAF50; color: white; padding: 5px 10px; border-radius: 5px; font-size: 0.8em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 接続と保存機能 (安全ガード付き) ---
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
        # カラム名の正規化 (スプレッドシートの「台本」を内部で「台本メモ」として扱う)
        if "台本" in df.columns: df = df.rename(columns={"台本": "台本メモ"})
        return df
    except: return None

# 【安全ガード付き】保存関数
def safe_save(sheet, df):
    if df is None or len(df) == 0:
        st.error("🚨 エラー：データが空です。白紙保存を防止するため中止しました。")
        return False
    try:
        save_df = df.copy()
        # カラムを元に戻す
        if "台本メモ" in save_df.columns: save_df = save_df.rename(columns={"台本メモ": "台本"})
        # 補助用の列を削除
        final_cols = ["No", "公開予定日", "曜日", "タイトル", "ステータス", "台本", "月"]
        save_df = save_df[final_cols]
        
        sheet.clear()
        sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"🚨 保存失敗: {e}")
        return False

# --- 3. メイン処理 ---
st.title("☕️ アニ無理 制作ノート")
st.markdown('<span class="version-badge">🛡 Version 14.0.0 - データ保護・爆速反映版</span>', unsafe_allow_html=True)

sheet = connect_to_gsheets()

# データ初期化
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
    is_mobile = st.radio("表示", ["🖥 PC版", "📱 スマホ版"], index=1 if is_mobile_from_url else 0) == "📱 スマホ版"
    
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

    # 【PC版】一括更新
    if not is_mobile:
        st.divider()
        with st.expander("🔄 ステータス一括更新"):
            m_eps = st.session_state.notebook_df[st.session_state.notebook_df['月'] == str(st.session_state.cur_m)]
            if not m_eps.empty:
                nos = m_eps['No'].tolist()
                s_n = st.selectbox("開始", nos); e_n = st.selectbox("終了", nos, index=len(nos)-1)
                stt = st.selectbox("新状態", ["未","台本完","撮影済","編集済","UP済"])
                if st.button("一括実行"):
                    targets = nos[nos.index(s_n):nos.index(e_n)+1]
                    st.session_state.notebook_df.loc[st.session_state.notebook_df['No'].isin(targets), 'ステータス'] = stt
                    if safe_save(sheet, st.session_state.notebook_df): st.success("更新！"); time.sleep(0.5); st.rerun()

# 描画
df = st.session_state.notebook_df
curr_df = df[df['月'] == str(st.session_state.cur_m)].copy()

if not curr_df.empty:
    # メトリクス
    fin = curr_df[curr_df["ステータス"].isin(["編集済", "UP済"])]
    st.metric("ストック状況", f"{len(fin)} 本", f"{fin['公開予定日'].iloc[-1]} まで" if not fin.empty else "在庫なし")
    st.divider()

    opts = []
    for i, r in curr_df.iterrows():
        m = {"UP済":"✅","編集済":"✂️","撮影済":"🎬","台本完":"📝"}.get(r['ステータス'], "⏳")
        opts.append((f"{m} {r['No']} | {r['公開予定日']} | {r['タイトル'] or '未定'}", i))
    
    if st.session_state.sel_idx >= len(opts): st.session_state.sel_idx = 0

    if is_mobile:
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
        
        txt = str(row['台本メモ'])
        html = "".join([f'<p class="{"red-text" if l.startswith("赤：") else "blue-text" if l.startswith("青：") else "black-text"}">{l[2:] if (l.startswith("赤：") or l.startswith("青：")) else l}</p>' for l in txt.split("\n")])
        st.markdown(f'<div class="preview-box">{html if txt else "台本なし"}</div>', unsafe_allow_html=True)
    
    else:
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
                tx = st.text_area("内容", value=row['台本メモ'], height=400)
                if st.button("💾 この1件を即時保存", type="primary"):
                    st.session_state.notebook_df.at[row_idx, 'タイトル'], st.session_state.notebook_df.at[row_idx, 'ステータス'], st.session_state.notebook_df.at[row_idx, '台本メモ'] = tit, sta, tx
                    if safe_save(sheet, st.session_state.notebook_df): st.success("保存完了！"); time.sleep(0.5); st.rerun()
            else:
                txt = str(row['台本メモ'])
                html = "".join([f'<p class="{"red-text" if l.startswith("赤：") else "blue-text" if l.startswith("青：") else "black-text"}">{l[2:] if (l.startswith("赤：") or l.startswith("青：")) else l}</p>' for l in txt.split("\n")])
                st.markdown(f'<div class="preview-box">{html if txt else "台本なし"}</div>', unsafe_allow_html=True)
else:
    st.warning(f"{st.session_state.cur_m}月のデータがスプレッドシートに見つかりません。")
