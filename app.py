import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, timedelta
import time
import re

# --- 1. アプリの設定 ---
st.set_page_config(page_title="アニ無理 制作ノート", layout="wide", page_icon="☕")

# --- 2. デザイン (ミルクティー・クラフト紙風 + 水色バー) ---
st.markdown("""
    <style>
    /* 全体の背景：濃いめの生成り */
    .stApp {
        background-color: #EFEBD6; 
        color: #4A3B2A;
    }
    
    /* 文字色統一：焦げ茶 */
    h1, h2, h3, h4, h5, h6, p, label, span, div, li {
        color: #4A3B2A !important;
        font-family: "Hiragino Mincho ProN", "Yu Mincho", serif;
    }

    /* サイドバー：少し濃い茶色 */
    [data-testid="stSidebar"] {
        background-color: #E6DCCF;
        border-right: 1px solid #C0B2A0;
    }

    /* 入力フォーム等の黒背景対策（念入りに） */
    .stTextInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {
        background-color: #FFFAF0 !important;
        color: #3E2723 !important;
        border: 1px solid #A1887F;
    }
    
    /* 表（データエディタ）の強制白背景化 */
    [data-testid="stDataFrame"] {
        background-color: #FFFAF0 !important;
        border: 1px solid #A1887F;
    }
    
    /* プログレスバー */
    .stProgress > div > div > div {
        background-color: #FFFFFF !important;
    }
    .stProgress > div > div > div > div {
        background-color: #81D4FA !important;
    }

    /* ボタンのデザイン */
    .stButton>button {
        background-color: #D7CCC8;
        color: #3E2723 !important;
        border: 1px solid #8D6E63;
        border-radius: 4px;
    }
    
    /* 色付きセリフのスタイル */
    .red-text {
        color: #E53935 !important;
        font-weight: bold;
        font-size: 1.1em;
        line-height: 1.8;
    }
    .blue-text {
        color: #1E88E5 !important;
        font-weight: bold;
        font-size: 1.1em;
        line-height: 1.8;
    }
    .black-text {
        color: #212121 !important;
        font-size: 1.0em;
        line-height: 1.8;
    }
    
    /* プレビューエリアの背景 */
    .preview-box {
        background-color: #FFFAF0;
        padding: 20px;
        border-radius: 8px;
        border: 2px solid #A1887F;
        min-height: 300px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. スプレッドシート接続機能（キャッシュ付き） ---
@st.cache_resource
def connect_to_gsheets():
    """Google Sheetsに接続（キャッシュで再利用）"""
    try:
        key_dict = json.loads(st.secrets["gcp"]["json_key"])
        creds = Credentials.from_service_account_info(key_dict, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)
        sheet_url = st.secrets["SPREADSHEET_URL"]
        return client.open_by_url(sheet_url).sheet1
    except Exception as e:
        st.error(f"Google Sheets接続エラー: {e}")
        return None

def load_data_from_sheet(sheet):
    """シートからデータを読み込み"""
    if sheet is None:
        return None
    try:
        time.sleep(0.5)
        data = sheet.get_all_records()
        if not data:
            return None
        df = pd.DataFrame(data)
        
        if "台本" in df.columns and "台本メモ" not in df.columns:
            df = df.rename(columns={"台本": "台本メモ"})
        
        return df
    except Exception as e:
        st.warning(f"データ読み込みエラー: {e}")
        return None

def save_data_to_sheet(sheet, df):
    """データをシートに保存"""
    if sheet is None:
        st.error("シート接続がありません")
        return False
    try:
        time.sleep(0.5)
        sheet.clear()
        save_df = df.copy()
        if "台本メモ" in save_df.columns:
            save_df = save_df.rename(columns={"台本メモ": "台本"})
        sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"保存エラー: {e}")
        return False

def update_episode_numbers(df, start_episode=48):
    """エピソード番号を更新（#48から開始）"""
    # Noが数字のみの場合、#48形式に変換
    for idx, row in df.iterrows():
        current_no = str(row['No'])
        if current_no.isdigit():
            # 数字のみの場合、#を付けて48から開始
            new_no = f"#{start_episode + int(current_no) - 1}"
            df.at[idx, 'No'] = new_no
        elif not current_no.startswith('#'):
            # #がない場合、#を付ける
            if current_no.isdigit():
                df.at[idx, 'No'] = f"#{current_no}"
    
    return df

# --- 4. ロジック関数 ---
def calculate_stock_deadline(df):
    """在庫状況から投稿可能日を計算"""
    finished_df = df[df["ステータス"].isin(["撮影済", "編集済", "UP済"])].copy()
    
    if len(finished_df) == 0:
        return None, "在庫なし", "撮影頑張りましょう！"
    
    finished_df["日付"] = pd.to_datetime(finished_df["公開予定日"], format="%m/%d", errors='coerce')
    finished_df["日付"] = finished_df["日付"].apply(lambda x: x.replace(year=datetime.now().year) if pd.notna(x) else None)
    
    max_date = finished_df["日付"].max()
    max_row = finished_df[finished_df["日付"] == max_date].iloc[0]
    
    deadline_text = f"{max_row['公開予定日']} {max_row['曜日']} まで"
    sub_text = "投稿可能！✨"
    
    return len(finished_df), deadline_text, sub_text

def colorize_script(script_text):
    """台本テキストを色付きHTMLに変換（名前表示版）"""
    if not script_text:
        return "<p class='black-text'>台本を入力してください</p>"
    
    lines = script_text.split('\n')
    html_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            html_lines.append("<br>")
            continue
            
        # 赤：「」パターン → Tomomi：「」に変換
        if line.startswith('赤：'):
            content = re.sub(r'^赤：', '', line)
            html_lines.append(f'<p class="red-text">Tomomi：{content}</p>')
        # 青：「」パターン → 道ゐ：「」に変換
        elif line.startswith('青：'):
            content = re.sub(r'^青：', '', line)
            html_lines.append(f'<p class="blue-text">道ゐ：{content}</p>')
        # 黒：「」パターン → そのまま表示
        elif line.startswith('黒：'):
            content = re.sub(r'^黒：', '', line)
            html_lines.append(f'<p class="black-text">{content}</p>')
        # その他の行（通常表示）
        else:
            html_lines.append(f'<p class="black-text">{line}</p>')
    
    return ''.join(html_lines)

# --- 5. メイン処理 ---
st.title("☕️ アニ無理 制作ノート")

# セッションステート初期化
if 'selected_row_index' not in st.session_state:
    st.session_state.selected_row_index = 0
if 'current_month' not in st.session_state:
    st.session_state.current_month = 12  # 12月から開始
if 'current_year' not in st.session_state:
    st.session_state.current_year = 2025
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "edit"  # "edit" or "preview"

with st.sidebar:
    st.header("⚙️ 設定")
    
    # 月切り替えボタン
    st.subheader("📅 月の切り替え")
    col_prev, col_current, col_next = st.columns([1, 2, 1])
    
    with col_prev:
        if st.button("◀ 前月"):
            if st.session_state.current_month == 1:
                st.session_state.current_month = 12
                st.session_state.current_year -= 1
            else:
                st.session_state.current_month -= 1
            st.session_state.selected_row_index = 0
            st.rerun()
    
    with col_current:
        st.markdown(f"### {st.session_state.current_year}年 {st.session_state.current_month}月")
    
    with col_next:
        if st.button("次月 ▶"):
            if st.session_state.current_month == 12:
                st.session_state.current_month = 1
                st.session_state.current_year += 1
            else:
                st.session_state.current_month += 1
            st.session_state.selected_row_index = 0
            st.rerun()
    
    st.divider()
    
    # 台本フォーマットガイド
    st.subheader("📝 台本フォーマット")
    st.markdown("""
    **正しい書き方：**
    - `赤：「Tomomiのセリフ」`
    - `青：「道ゐのセリフ」`
    - `黒：「ナレーション」`
    
    **プレビュー表示：**
    - 赤 → **Tomomi：** （赤色）
    - 青 → **道ゐ：** （青色）
    - 黒 → そのまま（黒色）
    """)

# --- 6. データ初期化・読み込み ---
sheet = connect_to_gsheets()

if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False

if sheet is not None and not st.session_state.data_loaded:
    sheet_df = load_data_from_sheet(sheet)
    
    if sheet_df is not None and not sheet_df.empty:
        # エピソード番号を更新（#48から開始）
        sheet_df = update_episode_numbers(sheet_df, start_episode=48)
        st.session_state.notebook_df = sheet_df
        st.session_state.data_loaded = True
        
        # 更新したエピソード番号を保存
        save_data_to_sheet(sheet, st.session_state.notebook_df)
    else:
        st.error("⚠️ Google Sheetsにデータがありません")
        st.info("先にGoogle Sheetsにデータを入力してください")

if 'notebook_df' in st.session_state:
    df = st.session_state.notebook_df

    # 現在の月のデータをフィルタリング
    df['月'] = pd.to_datetime(df['公開予定日'], format='%m/%d', errors='coerce').dt.month
    current_month_df = df[df['月'] == st.session_state.current_month].copy()
    
    if current_month_df.empty:
        st.warning(f"{st.session_state.current_year}年{st.session_state.current_month}月のデータがありません")
    else:
        # --- 7. 管理指標ダッシュボード ---
        finished_count, deadline_text, sub_text = calculate_stock_deadline(current_month_df)
        
        if finished_count is None:
            finished_count = 0
            deadline_text = "在庫なし"
            sub_text = "撮影頑張りましょう！"

        st.markdown("### 📊 ストック状況")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("出来上がっている本数！", f"{finished_count} 本", "撮影済 + 編集済 + UP済")
        with c2:
            st.metric("何月何日まで投稿可能！", deadline_text, sub_text)
        with c3:
            total = len(current_month_df)
            st.write(f"**全体の進行率 ({finished_count}/{total})**")
            prog_rate = finished_count / total if total > 0 else 0
            st.progress(prog_rate)

        st.divider()

        # --- 8. スケジュール一覧 & 台本機能 ---
        col1, col2 = st.columns([1.3, 1])

        with col1:
            st.subheader("🗓 スケジュール帳")
            
            # --- 一括ステータス更新機能 ---
            with st.expander("📌 一括ステータス更新", expanded=False):
                st.caption("範囲を指定して、複数のエピソードのステータスを一度に変更できます")
                
                bulk_col1, bulk_col2, bulk_col3 = st.columns(3)
                
                # エピソード番号のリストを作成
                episode_list = current_month_df['No'].tolist()
                
                with bulk_col1:
                    start_episode = st.selectbox(
                        "開始エピソード",
                        options=episode_list,
                        key="bulk_start"
                    )
                
                with bulk_col2:
                    end_episode = st.selectbox(
                        "終了エピソード",
                        options=episode_list,
                        index=len(episode_list)-1 if len(episode_list) > 0 else 0,
                        key="bulk_end"
                    )
                
                with bulk_col3:
                    bulk_status = st.selectbox(
                        "変更先ステータス",
                        options=["未", "台本完", "撮影済", "編集済", "UP済"],
                        key="bulk_status"
                    )
                
                if st.button("✅ 一括更新を実行", type="primary", use_container_width=True):
                    # 開始と終了のインデックスを取得
                    try:
                        start_idx = episode_list.index(start_episode)
                        end_idx = episode_list.index(end_episode)
                        
                        if start_idx > end_idx:
                            st.error("⚠️ 開始エピソードは終了エピソードより前にしてください")
                        else:
                            # 範囲内のエピソードを更新
                            update_count = 0
                            for i in range(start_idx, end_idx + 1):
                                episode_no = episode_list[i]
                                # DataFrameの該当行を更新
                                mask = st.session_state.notebook_df['No'] == episode_no
                                st.session_state.notebook_df.loc[mask, 'ステータス'] = bulk_status
                                update_count += 1
                            
                            st.success(f"✅ {start_episode} 〜 {end_episode} の {update_count}件を「{bulk_status}」に更新しました！")
                            st.balloons()
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"エラーが発生しました: {e}")
            
            st.caption("👇 ラジオボタンで行を選択すると、右側の台本が切り替わります")
            
            # ステータス凡例を表示
            st.markdown("""
            **ステータス表示：**
            - ✅ UP済
            - ✂️ 編集済
            - 🎬 撮影済
            - 📝 台本完
            - ⏳ 未
            """)
            
            st.divider()
            
            # ラジオボタンによる行選択（ステータスマーク付き）
            options = []
            for idx, row in current_month_df.iterrows():
                display_title = row['タイトル'] if row['タイトル'] else "（タイトル未定）"
                
                # ステータスに応じたマーク（5種類）
                if row['ステータス'] == "UP済":
                    status_mark = "✅"
                elif row['ステータス'] == "編集済":
                    status_mark = "✂️"
                elif row['ステータス'] == "撮影済":
                    status_mark = "🎬"
                elif row['ステータス'] == "台本完":
                    status_mark = "📝"
                else:
                    status_mark = "⏳"
                
                label = f"{status_mark} {row['No']} | {row['公開予定日']} {row['曜日']} | {display_title}"
                options.append((label, idx))
            
            # 選択インデックスが範囲外の場合は0にリセット
            if st.session_state.selected_row_index >= len(options):
                st.session_state.selected_row_index = 0
            
            selected_label = st.radio(
                "台本を選択",
                [opt[0] for opt in options],
                index=st.session_state.selected_row_index,
                key="row_selector",
                label_visibility="collapsed"
            )
            
            # 選択された行のインデックスを更新
            if selected_label:
                new_index = [opt[0] for opt in options].index(selected_label)
                if new_index != st.session_state.selected_row_index:
                    st.session_state.selected_row_index = new_index

        with col2:
            st.subheader("🎬 台本を見る・書く")
            
            # 前へ・次へボタン
            nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
            
            with nav_col1:
                if st.button("⬅ 前へ", use_container_width=True, key="prev_button"):
                    if st.session_state.selected_row_index > 0:
                        st.session_state.selected_row_index -= 1
                        st.rerun()
            
            with nav_col2:
                actual_index = options[st.session_state.selected_row_index][1]
                selected_row = st.session_state.notebook_df.loc[actual_index]
                st.info(f"📅 {selected_row['公開予定日']} {selected_row['曜日']}")
            
            with nav_col3:
                if st.button("次へ ➡", use_container_width=True, key="next_button"):
                    if st.session_state.selected_row_index < len(options) - 1:
                        st.session_state.selected_row_index += 1
                        st.rerun()
            
            st.markdown("---")
            
            # タイトル入力
            st.write("**📝 タイトル**")
            new_title = st.text_input(
                "タイトルを入力",
                value=selected_row['タイトル'],
                key=f"title_{actual_index}",
                label_visibility="collapsed"
            )
            
            if new_title != selected_row['タイトル']:
                st.session_state.notebook_df.at[actual_index, 'タイトル'] = new_title
                st.toast(f"{selected_row['No']} のタイトルを更新しました！", icon="💾")
            
            # ステータス選択
            st.write("**🎬 ステータス**")
            new_status = st.selectbox(
                "ステータスを選択",
                options=["未", "台本完", "撮影済", "編集済", "UP済"],
                index=["未", "台本完", "撮影済", "編集済", "UP済"].index(selected_row['ステータス']),
                key=f"status_{actual_index}",
                label_visibility="collapsed"
            )
            
            if new_status != selected_row['ステータス']:
                st.session_state.notebook_df.at[actual_index, 'ステータス'] = new_status
                st.toast(f"{selected_row['No']} のステータスを更新しました！", icon="📊")
                st.rerun()
            
            st.markdown("---")
            
            # 編集/プレビュー切り替えボタン
            mode_col1, mode_col2 = st.columns(2)
            
            with mode_col1:
                if st.button("✏️ 編集モード", use_container_width=True, 
                            type="primary" if st.session_state.view_mode == "edit" else "secondary"):
                    st.session_state.view_mode = "edit"
                    st.rerun()
            
            with mode_col2:
                if st.button("👁 プレビューモード", use_container_width=True,
                            type="primary" if st.session_state.view_mode == "preview" else "secondary"):
                    st.session_state.view_mode = "preview"
                    st.rerun()
            
            st.write(f"**【 {selected_row['No']} 】** の台本")
            
            current_text = selected_row["台本メモ"]
            
            # モードに応じた表示切り替え
            if st.session_state.view_mode == "edit":
                # 編集モード
                new_text = st.text_area(
                    "台本エディタ（編集モード）",
                    value=current_text,
                    height=300,
                    placeholder="ここに台本を記入...\n\n例：\n赤：「こんにちは！」\n青：「よろしく！」\n黒：「【ナレーション】」",
                    key=f"script_{actual_index}"
                )
                
                if new_text != current_text:
                    st.session_state.notebook_df.at[actual_index, "台本メモ"] = new_text
                    st.toast(f"{selected_row['No']} の台本を更新しました！", icon="💾")
            
            else:
                # プレビューモード
                colored_html = colorize_script(current_text)
                
                st.markdown('<div class="preview-box">' + colored_html + '</div>', unsafe_allow_html=True)

        # --- 9. 保存ボタン ---
        st.divider()
        if st.button("💾 変更をスプレッドシートに保存する", type="primary", use_container_width=True):
            with st.spinner("保存中..."):
                if save_data_to_sheet(sheet, st.session_state.notebook_df):
                    st.success("✅ 保存しました！Tomomiさんにも共有されました✨")
                    st.balloons()
else:
    st.error("⚠️ データの初期化に失敗しました")
    st.info("Secrets設定を確認してください")
