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
# Version: 13.0.0 - 究極安定・データ保護・爆速反映版
# ==============================================

# --- 1. 基本設定 ---
st.set_page_config(page_title="アニ無理 制作ノート", layout="wide", page_icon="☕", initial_sidebar_state="expanded")

# CSS: 8.2.0のデザインを完全復刻
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
    .black-text { color: #212121 !important; }
    .preview-box { background-color: #FFFAF0; padding: 20px; border-radius: 8px; border: 2px solid #A1887F; min-height: 400px; }
    .version-badge { background-color: #4CAF50; color: white; padding: 5px 10px; border-radius: 5px; font-size: 0.8em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 接続とエラー防止機能 ---
@st.cache_resource(ttl=3600)
def connect_to_gsheets():
    try:
        json_key = json.loads(st.secrets["gcp"]["json_key"]) if isinstance(st.secrets["gcp"]["json_key"], str) else dict(st.secrets["gcp"]["json_key"])
        creds = Credentials.from_service_account_info(json_key, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open_by_url(st.secrets["SPREADSHEET_URL"]).sheet1
    except: return None

@st.cache_data(ttl=300)
def load_and_fix_data(_sheet):
    if _sheet is None: return None
    try:
        data = _sheet.get_all_records()
        df = pd.DataFrame(data).fillna("").astype(str)
        # 列名チェックと自動修正（KeyError対策）
        required = {"No": "", "公開予定日": "1/1", "曜日": "月", "タイトル": "未定", "ステータス": "未", "台本": ""}
        for col, default in required.items():
            if col not in df.columns:
                df[col] = default
        if "台本" in df.columns: df = df.rename(columns={"台本": "台本メモ"})
        return df
    except: return pd.DataFrame(columns=["No", "公開予定日", "曜日", "タイトル", "ステータス", "台本メモ"])

def force_save(sheet, df):
    try:
        save_df = df.copy()
        if "台本メモ" in save_df.columns: save_df = save_df.rename(columns={"台本メモ": "台本"})
        # 内部用の一時列を除去
        cols_to_drop = [c for c in ["month_tmp", "m_internal"] if c in save_df.columns]
        save_df = save_df.drop(columns=cols_to_drop)
        sheet.clear()
        sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
        load_and_fix_data.clear() # キャッシュ更新
        return True
    except: return False

# --- 3. 2026年対応・月間スケジュール生成 ---
def build_month(year, month, start_no):
    import calendar
    res = []
    curr_no = start_no
    _, last = calendar.monthrange(year, month)
    for d in range(1, last + 1):
        dt = datetime(year, month, d)
        if dt.weekday() < 5:
            res.append({"No": f"#{curr_no}", "公開予定日": f"{month}/{d}", "曜日": ["月","火","水","木","金"][dt.weekday()], "タイトル": "", "ステータス": "未", "台本メモ": ""})
            curr_no += 1
    return pd.DataFrame(res)

def sync_all_months(df):
    # 公開予定日から月を数値化（エラーに強い変換）
    def get_month(date_str):
        try: return int(str(date_str).split('/')[0])
        except: return datetime.now().month
    
    df['m_internal'] = df['公開予定日'].apply(get_month)
    existing = df['m_internal'].unique().tolist()
    today = datetime.now()
    all_data = [df]
    
    # 向こう3ヶ月を保証
    for i in range(3):
        target = today + timedelta(days=31*i)
        if target.month not in existing:
            last_no = 85 if df.empty else int(re.sub(r'\D', '', str(df['No'].iloc[-1]))) + 1
            all_data.append(build_month(target.year, target.month, last_no))
    
    return pd.concat(all_data, ignore_index=True)

# --- 4. メイン ---
st.title("☕️ アニ無理 制作ノート")
st.markdown('<span class="version-badge">🛡 Version 13.0.0 - 究極安定版</span>', unsafe_allow_html=True)

sheet = connect_to_gsheets()
if 'notebook_df' not in st.session_state:
    raw = load_and_fix_data(sheet)
    if raw is not None:
        st.session_state.notebook_df = sync_all_months(raw)
    else:
        st.error("スプレッドシートが見つかりません。URLとSecretsを確認してください。"); st.stop()

# ステート初期化
if 'cur_m' not in st.session_state: st.session_state.cur_m = datetime.now().month
if 'sel_idx' not in st.session_state: st.session_state.sel_idx = 0
if 'view_m' not in st.session_state: st.session_state.view_m = "preview"

# サイドバー
with st.sidebar:
    st.header("⚙️ 設定")
    is_mobile = st.radio("モード", ["🖥 PC版", "📱 スマホ版"], index=1 if st.query_params.get("mobile")=="true" else 0) == "📱 スマホ版"
    st.divider(); st.subheader("📅 月移動")
    c1, c2, c3 = st.columns([1,2,1])
    if c1.button("◀"):
        st.session_state.cur_m = 12 if st.session_state.cur_m == 1 else st.session_state.cur_m - 1
        st.session_state.sel_idx = 0; st.rerun()
    c2.markdown(f"<center><b>{st.session_state.cur_m}月</b></center>", unsafe_allow_html=True)
    if c3.button("▶"):
        st.session_state.cur_m = 1 if st.session_state.cur_m == 12 else st.session_state.cur_m + 1
        st.session_state.sel_idx = 0; st.rerun()

    if not is_mobile:
        st.divider()
        with st.expander("🔄 一括更新"):
            df_all = st.session_state.notebook_df
            df_all['m_internal'] = df_all['公開予定日'].apply(lambda x: int(str(x).split('/')[0]) if '/' in str(x) else 0)
            m_eps = df_all[df_all['m_internal'] == st.session_state.cur_m]
            if not m_eps.empty:
                nos = m_eps['No'].tolist()
                s_n = st.selectbox("開始", nos); e_n = st.selectbox("終了", nos, index=len(nos)-1)
                stt = st.selectbox("新状態", ["未","台本完","撮影済","編集済","UP済"])
                if st.button("一括実行", type="primary"):
                    targets = nos[nos.index(s_n):nos.index(e_n)+1]
                    st.session_state.notebook_df.loc[st.session_state.notebook_df['No'].isin(targets), 'ステータス'] = stt
                    force_save(sheet, st.session_state.notebook_df)
                    st.success("更新しました！"); st.rerun()

# フィルタリング
df = st.session_state.notebook_df
df['m_internal'] = df['公開予定日'].apply(lambda x: int(str(x).split('/')[0]) if '/' in str(x) else 0)
curr_df = df[df['m_internal'] == st.session_state.cur_m].copy()

if not curr_df.empty:
    # ダッシュボード
    fin = curr_df[curr_df["ステータス"].isin(["編集済", "UP済"])]
    st.markdown("### 📊 ストック状況")
    d1, d2 = st.columns(2)
    d1.metric("完成本数", f"{len(fin)} 本")
    d2.metric("投稿可能", f"{fin['公開予定日'].iloc[-1]} まで" if not fin.empty else "在庫なし")
    st.divider()

    # セレクター作成
    opts = []
    for i, r in curr_df.iterrows():
        m = {"UP済":"✅","編集済":"✂️","撮影済":"🎬","台本完":"📝"}.get(r['ステータス'], "⏳")
        opts.append((f"{m} {r['No']} | {r['公開予定日']} | {r['タイトル'] or '未定'}", i))
    
    if st.session_state.sel_idx >= len(opts): st.session_state.sel_idx = 0

    if is_mobile:
        # --- スマホ版 ---
        n1, n2, n3 = st.columns([1, 3, 1])
        if n1.button("⬅") and st.session_state.sel_idx > 0: st.session_state.sel_idx -= 1; st.rerun()
        sel = n2.selectbox("選", [o[0] for o in opts], index=st.session_state.sel_idx, label_visibility="collapsed")
        st.session_state.sel_idx = [o[0] for o in opts].index(sel)
        if n3.button("➡") and st.session_state.sel_idx < len(opts)-1: st.session_state.sel_idx += 1; st.rerun()
        
        row_idx = opts[st.session_state.sel_idx][1]
        row = df.loc[row_idx]
        if row['ステータス'] != "UP済" and st.button("✅ UP済にする", type="primary", use_container_width=True):
            st.session_state.notebook_df.at[row_idx, 'ステータス'] = "UP済"
            force_save(sheet, st.session_state.notebook_df); st.balloons(); st.rerun()
        
        # 台本描画
        lines = str(row['台本メモ']).split("\n")
        html = "".join([f'<p class="{"red-text" if l.startswith("赤：") else "blue-text" if l.startswith("青：") else "black-text"}">{l[2:] if (l.startswith("赤：") or l.startswith("青：")) else l}</p>' for l in lines])
        st.markdown(f'<div class="preview-box">{html if row["台本メモ"] else "台本なし"}</div>', unsafe_allow_html=True)
    
    else:
        # --- PC版 (8.2.0レイアウト) ---
        cl, cr = st.columns([1.3, 1])
        with cl:
            st.subheader("🗓 スケジュール帳")
            sel_l = st.radio("選択", [o[0] for o in opts], index=st.session_state.sel_idx, label_visibility="collapsed")
            st.session_state.sel_idx = [o[0] for o in opts].index(sel_l)
        with cr:
            row_idx = opts[st.session_state.sel_idx][1]
            row = df.loc[row_idx]
            st.subheader("🎬 台本編集")
            tit = st.text_input("タイトル", value=str(row['タイトル']))
            sta = st.selectbox("状態", ["未","台本完","撮影済","編集済","UP済"], index=["未","台本完","撮影済","編集済","UP済"].index(row['ステータス']))
            
            b1, b2 = st.columns(2)
            if b1.button("✏️ 編集モード", type="primary" if st.session_state.view_m=="edit" else "secondary", use_container_width=True):
                st.session_state.view_m = "edit"; st.rerun()
            if b2.button("👁 プレビュー", type="primary" if st.session_state.view_m=="preview" else "secondary", use_container_width=True):
                st.session_state.view_m = "preview"; st.rerun()
            
            if st.session_state.view_m == "edit":
                tx = st.text_area("内容", value=str(row['台本メモ']), height=400)
                if st.button("💾 全ての変更を保存", type="primary", use_container_width=True):
                    st.session_state.notebook_df.at[row_idx, 'タイトル'], st.session_state.notebook_df.at[row_idx, 'ステータス'], st.session_state.notebook_df.at[row_idx, '台本メモ'] = tit, sta, tx
                    force_save(sheet, st.session_state.notebook_df); st.success("保存！"); st.rerun()
            else:
                lines = str(row['台本メモ']).split("\n")
                html = "".join([f'<p class="{"red-text" if l.startswith("赤：") else "blue-text" if l.startswith("青：") else "black-text"}">{l[2:] if (l.startswith("赤：") or l.startswith("青：")) else l}</p>' for l in lines])
                st.markdown(f'<div class="preview-box">{html if row["台本メモ"] else "台本なし"}</div>', unsafe_allow_html=True)
else:
    st.warning("この月のデータがありません。")
