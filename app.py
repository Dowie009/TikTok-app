import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

# --- 設定 ---
st.set_page_config(page_title="アニ無理 制作ノート", page_icon="☕")

# スプレッドシート接続機能
def connect_to_gsheets():
    # Secretsから鍵を取り出す
    key_dict = json.loads(st.secrets["gcp"]["json_key"])
    creds = Credentials.from_service_account_info(key_dict, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    client = gspread.authorize(creds)
    
    # シートを開く
    sheet_url = st.secrets["SPREADSHEET_URL"]
    return client.open_by_url(sheet_url).sheet1

# データの読み込み
def load_data(sheet):
    try:
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["No", "公開予定日", "曜日", "タイトル", "ステータス", "台本"])
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame(columns=["No", "公開予定日", "曜日", "タイトル", "ステータス", "台本"])

# データの保存
def save_data(sheet, df):
    sheet.clear() # 一度クリア
    # ヘッダーとデータを書き込む
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

# --- アプリ画面 ---
st.title("☕ アニ無理 制作ノート")

try:
    # シートに接続
    sheet = connect_to_gsheets()
    df = load_data(sheet)

    # データが空っぽ（初期状態）なら、初期データを作る
    if df.empty:
        initial_data = []
        dates = pd.date_range(start="2025-12-11", periods=20) # 日付を生成
        weekdays = ["(月)", "(火)", "(水)", "(木)", "(金)", "(土)", "(日)"]
        
        for i, date in enumerate(dates):
            initial_data.append({
                "No": i + 1,
                "公開予定日": date.strftime("%m/%d"),
                "曜日": weekdays[date.weekday()],
                "タイトル": "",
                "ステータス": "未",
                "台本": ""
            })
        df = pd.DataFrame(initial_data)
        # 最初に一度保存しておく
        save_data(sheet, df)

    # --- ストック状況 ---
    completed_count = len(df[df["ステータス"] == "撮影済+UP済"])
    st.header("📊 ストック状況")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("出来上がっている本数", f"{completed_count} 本")
    with col2:
        if completed_count == 0:
            st.warning("在庫なし！撮影頑張りましょう！")
        else:
            st.success(f"現在 {completed_count} 本のストックがあります！")
            
    st.divider()

    # --- スケジュール帳（編集モード） ---
    st.header("🗓 スケジュール帳")
    st.caption("👇 直接書き換えて、右下の「変更を保存」を押してください")

    # データ編集用テーブル
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        column_config={
            "No": st.column_config.NumberColumn(disabled=True),
            "公開予定日": st.column_config.TextColumn(disabled=True),
            "曜日": st.column_config.TextColumn(disabled=True),
            "ステータス": st.column_config.SelectboxColumn(
                options=["未", "台本作成中", "撮影可", "撮影済+UP済"],
                required=True
            ),
            "台本": st.column_config.TextColumn(width="large")
        },
        height=400,
        hide_index=True
    )

    # --- 保存ボタン ---
    if st.button("💾 変更をスプレッドシートに保存する", type="primary"):
        with st.spinner("保存中..."):
            save_data(sheet, edited_df)
        st.success("保存しました！ともみさんにも共有されました✨")
        st.balloons()

except Exception as e:
    st.error(f"エラーが発生しました: {e}")
    st.info("設定（Secrets）が間違っているか、共有設定がうまくいっていない可能性があります。")