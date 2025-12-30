import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, timedelta
import time
import re

# ==============================================
# 🔥 アニ無理 制作ノート 
# Version: 8.9.0 - 安定性強化・8.2.0レイアウト完全準拠
# ==============================================

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
        if not data: return None
        df = pd.DataFrame(data)
        # floatエラー対策：すべての空欄を空文字にする
        df = df.fillna("")
        if "台本" in df.columns: df = df.rename(columns={"台本": "台本メモ"})
        return df
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        return None

def save_data_to_sheet(sheet, df):
    if sheet is None: return False
    try:
        sheet.clear()
        save_df = df.copy()
        if "台本メモ" in save_df.columns: save_df = save_df.rename(columns={"台本メモ": "台本"})
        # 補助列を除去
        final_cols = [c for c in save_df.columns if c not in ["月_internal", "年_internal"]]
        sheet.update([final_cols] + save_df[final_cols].values.tolist())
        load_data_from_sheet.clear(); return True
    except Exception as e:
        st.error(f"保存失敗: {e}"); return False

# --- 4. ロジック関数 ---
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
                "曜日": ["月","火","水","木","金"][curr_date.weekday()],
                "タイトル": "", "ステータス": "未", "台本メモ": ""
            })
            episode_no += 1
    return pd.DataFrame(schedules)

def ensure_all_months_data(df):
    # すべての列を文字列として扱う準備
    df = df.astype(str).replace("nan", "")
    df['月_internal'] = pd.to_datetime(df['公開予定日'], format='%m/%d', errors='coerce').dt.month
    existing = df['月_internal'].dropna().unique().tolist()
    all_data = [df]
    today = datetime.now()
    # 常に今月・来月・再来月の枠があるかチェック
    for i in range(3):
        target = today + timedelta(days=31*i)
        if float(target.month) not in [float(m) for m in existing]:
            last_no = 85 if df.empty else int(re.sub(r'\D', '', str(df['No'].iloc[-1]))) + 1
            all_data.append(generate_monthly_schedule(target.year, target.month, last_no))
    return pd.concat(all_data, ignore_index=True)

def calculate_stock_deadline(df):
    fin = df[df["ステータス"].isin(["編集済", "UP済"])].copy()
    if len(fin) == 0: return 0, "在庫なし", "撮影頑張りましょう！"
    return len(fin), f"{fin['公開予定日'].iloc[-1]} まで", "投稿可能！✨"

def colorize_script(text):
    if not isinstance(text, str) or not text or text == "": 
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
st.markdown('<span class="version-badge">🔄 Version 8.9.0 - 安定・復旧版</span>', unsafe_allow_html=True)

# セッション状態の初期化
if 'current_month' not in st.session_state: st.session_state.current_month = datetime.now().month
if 'current_year' not in st.session_state: st.session_state.current_year = datetime.now().year
if 'selected_row_index' not in st.session_state: st.session_state.selected_row_index = 0
if 'view_mode' not in st.session_state: st.session_state.view_mode = "preview"

# 接続とデータ取得を確実に実行
sheet = connect_to_gsheets()
sheet_df = load_data_from_sheet(sheet)

def move_month(direction):
    if direction == "next":
        if st.session_state.current_month == 12: st.session_state.current_month = 1; st.session_state.current_year += 1
        else: st.session_state.current_month += 1
    elif direction == "prev":
        if st.session_state.current_month == 1: st.session_state.current_month = 12; st.session_state.current_year -= 1
        else: st.session_state.current_month -= 1
    st.session_state.selected_row_index = 0; st.rerun()

# サイドバー設定
with st.sidebar:
    st.header("⚙️ 設定")
    is_mobile = st.radio("表示モード", ["🖥 PC版（フル機能）", "📱 スマホ版（閲覧のみ）"], 
                         index=1 if is_mobile_from_url else 0) == "📱 スマホ版（閲覧のみ）"
    
    if not is_mobile and sheet_df is not None:
        st.divider()
        with st.expander("🔄 ステータス一括更新"):
            try:
                full_df = ensure_all_months_data(sheet_df)
                m_eps = full_df[pd.to_datetime(full_df['公開予定日'], format='%m/%d', errors='coerce').dt.month == st.session_state.current_month]
                if not m_eps.empty:
                    eps = m_eps['No'].tolist()
                    s_ep = st.selectbox("開始", eps, key="bulk_s"); e_ep = st.selectbox("終了", eps, index=len(eps)-1, key="bulk_e")
                    stat = st.selectbox("新ステータス", ["未", "台本完", "撮影済", "編集済", "UP済"], key="bulk_v")
                    if st.button("一括更新を実行", type="primary"):
                        targets = eps[eps.index(s_ep):eps.index(e_ep)+1]
                        st.session_state.notebook_df.loc[st.session_state.notebook_df['No'].isin(targets), 'ステータス'] = stat
                        if save_data_to_sheet(sheet, st.session_state.notebook_df):
                            st.success("更新しました！"); time.sleep(1); st.rerun()
            except: st.caption("データ読み込み中...")

    st.divider(); st.subheader("📅 月の切り替え")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: 
        if st.button("◀", key="s_prev"): move_month("prev")
    with c2: st.write(f"<center><b>{st.session_state.current_year}/{st.session_state.current_month}</b></center>", unsafe_allow_html=True)
    with c3: 
        if st.button("▶", key="s_next"): move_month("next")

# メイン描画エリア
if sheet_df is not None:
    # データの整合性を整える
    df = ensure_all_months_data(sheet_df)
    st.session_state.notebook_df = df
    df['月_internal'] = pd.to_datetime(df['公開予定日'], format='%m/%d', errors='coerce').dt.month
    curr_df = df[df['月_internal'] == st.session_state.current_month].copy()

    # ストックダッシュボード
    count, deadline, sub = calculate_stock_deadline(curr_df)
    st.markdown("### 📊 ストック状況")
    d1, d2 = st.columns(2)
    with d1: st.metric("出来上がっている本数！", f"{count} 本", "編集済 + UP済")
    with d2: st.metric("何月何日まで投稿可能！", deadline, sub)
    
    # スマホ版専用：月移動ボタン
    if is_mobile:
        st.divider()
        m1, m2, m3 = st.columns([1, 2, 1])
        with m1: 
            if st.button("◀ 前月", key="m_nav_p"): move_month("prev")
        with m2: st.write(f"<center><b>{st.session_state.current_month}月を表示中</b></center>", unsafe_allow_html=True)
        with m3: 
            if st.button("次月 ▶", key="m_nav_n"): move_month("next")

    st.divider()

    if not curr_df.empty:
        opts = []
        for i, r in curr_df.iterrows():
            mark = {"UP済":"✅","編集済":"✂️","撮影済":"🎬","台本完":"📝"}.get(r['ステータス'], "⏳")
            opts.append((f"{mark} {r['No']} | {r['公開予定日']} | {r['タイトル'] or '未定'}", i))
        
        if st.session_state.selected_row_index >= len(opts): st.session_state.selected_row_index = 0
        
        if is_mobile:
            # モバイル表示
            n1, n2, n3 = st.columns([1, 3, 1])
            with n1: 
                if st.button("⬅", key="row_p", disabled=st.session_state.selected_row_index==0):
                    st.session_state.selected_row_index -= 1; st.rerun()
            with n2:
                sel = st.selectbox("選択", [o[0] for o in opts], index=st.session_state.selected_row_index, label_visibility="collapsed")
                st.session_state.selected_row_index = [o[0] for o in opts].index(sel)
            with n3:
                if st.button("➡", key="row_n", disabled=st.session_state.selected_row_index>=len(opts)-1):
                    st.session_state.selected_row_index += 1; st.rerun()
            
            row = df.loc[opts[st.session_state.selected_row_index][1]]
            st.subheader(f"🎬 {row['No']} 台本")
            if row['ステータス'] != "UP済":
                if st.button("✅ UP済にする", type="primary", use_container_width=True):
                    df.at[opts[st.session_state.selected_row_index][1], 'ステータス'] = "UP済"
                    save_data_to_sheet(sheet, df); st.balloons(); st.rerun()
            st.markdown(f'<div class="preview-box">{colorize_script(row["台本メモ"])}</div>', unsafe_allow_html=True)
        else:
            # PC表示：8.2.0のラジオボタン形式
            col1, col2 = st.columns([1.3, 1])
            with col1:
                st.subheader("🗓 スケジュール帳")
                sel_label = st.radio("選択", [o[0] for o in opts], index=st.session_state.selected_row_index, label_visibility="collapsed")
                st.session_state.selected_row_index = [o[0] for o in opts].index(sel_label)
            with col2:
                row = df.loc[opts[st.session_state.selected_row_index][1]]
                st.subheader("🎬 台本編集")
                st.info(f"📅 {row['公開予定日']} {row['曜日']} | {row['No']}")
                t = st.text_input("タイトル", value=str(row['タイトル']))
                s = st.selectbox("状態", ["未","台本完","撮影済","編集済","UP済"], index=["未","台本完","撮影済","編集済","UP済"].index(row['ステータス']))
                
                m1, m2 = st.columns(2)
                with m1:
                    if st.button("✏️ 編集", type="primary" if st.session_state.view_mode=="edit" else "secondary", use_container_width=True):
                        st.session_state.view_mode = "edit"; st.rerun()
                with m2:
                    if st.button("👁 プレビュー", type="primary" if st.session_state.view_mode=="preview" else "secondary", use_container_width=True):
                        st.session_state.view_mode = "preview"; st.rerun()
                
                if st.session_state.view_mode == "edit":
                    txt = st.text_area("内容", value=str(row['台本メモ']), height=350)
                    if st.button("💾 全ての変更を保存", type="primary", use_container_width=True):
                        df.at[opts[st.session_state.selected_row_index][1], 'タイトル'] = t
                        df.at[opts[st.session_state.selected_row_index][1], 'ステータス'] = s
                        df.at[opts[st.session_state.selected_row_index][1], '台本メモ'] = txt
                        if save_data_to_sheet(sheet, df): st.success("保存完了！"); st.balloons()
                else:
                    st.markdown(f'<div class="preview-box">{colorize_script(row["台本メモ"])}</div>', unsafe_allow_html=True)
else:
    st.warning("スプレッドシートのデータを読み込んでいます...")
    if st.button("強制リロード"): st.rerun()
