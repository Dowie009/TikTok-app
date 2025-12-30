import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import time
import re

# ==============================================
# 🔥 アニ無理 制作ノート 
# Version: 9.0.0 - 完全復旧・安定性第一
# ==============================================

# --- 1. アプリの設定 ---
st.set_page_config(
    page_title="アニ無理 制作ノート", 
    layout="wide", 
    page_icon="☕",
    initial_sidebar_state="expanded"
)

# --- 2. デザイン (8.2.0の完璧なデザイン) ---
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

# --- 3. スプレッドシート接続機能 (確実に一番上で定義) ---
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
        data = _sheet.get_all_records()
        if not data: return None
        df = pd.DataFrame(data)
        # floatエラー(NaN)をここで完全に封殺！すべて文字列にする
        df = df.fillna("").astype(str)
        if "台本" in df.columns: df = df.rename(columns={"台本": "台本メモ"})
        return df
    except Exception as e:
        st.error(f"データ読み込み失敗: {e}"); return None

def save_data_to_sheet(sheet, df):
    if sheet is None: return False
    try:
        sheet.clear()
        save_df = df.copy()
        if "台本メモ" in save_df.columns: save_df = save_df.rename(columns={"台本メモ": "台本"})
        # 補助用の列は除去して保存
        final_cols = [c for c in save_df.columns if c not in ["month_num"]]
        sheet.update([final_cols] + save_df[final_cols].values.tolist())
        load_data_from_sheet.clear(); return True
    except: return False

# --- 4. ロジック関数 ---
def colorize_script(text):
    if not text or text == "": 
        return "<p class='black-text'>台本を入力してください</p>"
    lines = text.split('\n')
    res = []
    for l in lines:
        l = l.strip()
        if not l: res.append("<br>")
        elif l.startswith('赤：'): res.append(f'<p class="red-text">Tomomi：{l[2:]}</p>')
        elif l.startswith('青：'): res.append(f'<p class="blue-text">道ゐ：{l[2:]}</p>')
        else: res.append(f'<p class="black-text">{l}</p>')
    return ''.join(res)

# --- 5. メイン処理 ---
st.title("☕️ アニ無理 制作ノート")
st.markdown('<span class="version-badge">🔄 Version 9.0.0 - 完全復旧版</span>', unsafe_allow_html=True)

# 最初に接続！
sheet = connect_to_gsheets()
raw_df = load_data_from_sheet(sheet)

# セッション状態
if 'current_month' not in st.session_state: st.session_state.current_month = datetime.now().month
if 'current_year' not in st.session_state: st.session_state.current_year = datetime.now().year
if 'selected_row_index' not in st.session_state: st.session_state.selected_row_index = 0
if 'view_mode' not in st.session_state: st.session_state.view_mode = "preview"

# サイドバー設定
with st.sidebar:
    st.header("⚙️ 設定")
    # モバイル判定
    is_mobile = st.radio("表示モード", ["🖥 PC版", "📱 スマホ版"], 
                         index=1 if is_mobile_from_url else 0) == "📱 スマホ版"
    
    st.divider(); st.subheader("📅 月の切り替え")
    # シンプルなセレクトボックスで月移動（ボタンより安定します）
    m_list = [10, 11, 12, 1, 2, 3] # 必要そうな月を固定
    st.session_state.current_month = st.selectbox("表示する月を選択", m_list, index=m_list.index(st.session_state.current_month))
    if st.button("今月に戻る"):
        st.session_state.current_month = datetime.now().month
        st.rerun()

    # PC版：一括更新（サイドバーに配置）
    if not is_mobile and raw_df is not None:
        st.divider()
        with st.expander("🔄 ステータス一括更新"):
            # 現在の月のNoリストを取得
            df_tmp = raw_df.copy()
            df_tmp['month_num'] = pd.to_datetime(df_tmp['公開予定日'], format='%m/%d', errors='coerce').dt.month
            m_eps = df_tmp[df_tmp['month_num'] == st.session_state.current_month]
            if not m_eps.empty:
                nos = m_eps['No'].tolist()
                s_no = st.selectbox("開始", nos, key="b1"); e_no = st.selectbox("終了", nos, index=len(nos)-1, key="b2")
                new_s = st.selectbox("新ステータス", ["未","台本完","撮影済","編集済","UP済"], key="b3")
                if st.button("一括実行", type="primary"):
                    targets = nos[nos.index(s_no):nos.index(e_no)+1]
                    raw_df.loc[raw_df['No'].isin(targets), 'ステータス'] = new_s
                    if save_data_to_sheet(sheet, raw_df): st.success("更新！"); time.sleep(1); st.rerun()

# メイン描画
if raw_df is not None:
    df = raw_df.copy()
    df['month_num'] = pd.to_datetime(df['公開予定日'], format='%m/%d', errors='coerce').dt.month
    curr_df = df[df['month_num'] == st.session_state.current_month].copy()

    if curr_df.empty:
        st.warning(f"{st.session_state.current_month}月のデータがスプレッドシートにありません。")
    else:
        # ストック状況
        finished = curr_df[curr_df["ステータス"].isin(["編集済", "UP済"])]
        st.markdown("### 📊 ストック状況")
        c1, c2 = st.columns(2)
        c1.metric("完成本数", f"{len(finished)} 本")
        if not finished.empty:
            c2.metric("投稿可能", f"{finished['公開予定日'].iloc[-1]} まで")

        st.divider()

        # エピソード選択用の選択肢作成
        opts = []
        for i, r in curr_df.iterrows():
            mark = {"UP済":"✅","編集済":"✂️","撮影済":"🎬","台本完":"📝"}.get(r['ステータス'], "⏳")
            opts.append((f"{mark} {r['No']} | {r['公開予定日']} | {r['タイトル'] or '未定'}", i))
        
        if st.session_state.selected_row_index >= len(opts): st.session_state.selected_row_index = 0

        if not is_mobile:
            # PC版：ラジオボタン形式 (8.2.0のレイアウト)
            col1, col2 = st.columns([1.3, 1])
            with col1:
                st.subheader("🗓 スケジュール帳")
                sel_label = st.radio("選択", [o[0] for o in opts], index=st.session_state.selected_row_index, label_visibility="collapsed")
                st.session_state.selected_row_index = [o[0] for o in opts].index(sel_label)
            with col2:
                row_idx = opts[st.session_state.selected_row_index][1]
                row = df.loc[row_idx]
                st.subheader("🎬 台本編集")
                t = st.text_input("タイトル", value=row['タイトル'])
                s = st.selectbox("状態", ["未","台本完","撮影済","編集済","UP済"], index=["未","台本完","撮影済","編集済","UP済"].index(row['ステータス']))
                
                m1, m2 = st.columns(2)
                if m1.button("✏️ 編集"): st.session_state.view_mode = "edit"; st.rerun()
                if m2.button("👁 プレビュー"): st.session_state.view_mode = "preview"; st.rerun()

                if st.session_state.view_mode == "edit":
                    txt = st.text_area("内容", value=row['台本メモ'], height=350)
                    if st.button("💾 全ての変更を保存", type="primary"):
                        df.at[row_idx, 'タイトル'] = t
                        df.at[row_idx, 'ステータス'] = s
                        df.at[row_idx, '台本メモ'] = txt
                        if save_data_to_sheet(sheet, df): st.success("保存完了！"); st.balloons()
                else:
                    st.markdown(f'<div class="preview-box">{colorize_script(row["台本メモ"])}</div>', unsafe_allow_html=True)
        else:
            # スマホ版
            n1, n2, n3 = st.columns([1, 3, 1])
            if n1.button("⬅") and st.session_state.selected_row_index > 0:
                st.session_state.selected_row_index -= 1; st.rerun()
            sel = n2.selectbox("選択", [o[0] for o in opts], index=st.session_state.selected_row_index, label_visibility="collapsed")
            st.session_state.selected_row_index = [o[0] for o in opts].index(sel)
            if n3.button("➡") and st.session_state.selected_row_index < len(opts)-1:
                st.session_state.selected_row_index += 1; st.rerun()
            
            row_idx = opts[st.session_state.selected_row_index][1]
            row = df.loc[row_idx]
            if row['ステータス'] != "UP済":
                if st.button("✅ UP済にする", type="primary", use_container_width=True):
                    df.at[row_idx, 'ステータス'] = "UP済"
                    save_data_to_sheet(sheet, df); st.rerun()
            st.markdown(f'<div class="preview-box">{colorize_script(row["台本メモ"])}</div>', unsafe_allow_html=True)
else:
    st.info("スプレッドシートのデータを読み込んでいます...")
