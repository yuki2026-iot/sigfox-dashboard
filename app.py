import boto3
import pandas as pd
import streamlit as st

st.title("Sigfox センサーデータ リアルタイム監視")

# AWS DynamoDBからデータを取得する設定
@st.cache_data(ttl=10)  # 10秒ごとにキャッシュを更新
def load_data():
    dynamodb = boto3.resource(
        "dynamodb",
        region_name="ap-northeast-1",
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
    )
    table = dynamodb.Table("sigfox_messages")

    # テーブルからデータをスキャンして取得
    response = table.scan()
    items = response.get("Items", [])

    if not items:
        return pd.DataFrame()

    df = pd.DataFrame(items)
    # タイムスタンプや数値データを適切な型に変換
    if "time" in df.columns:
        df["time"] = pd.to_numeric(df["time"])
        df["datetime"] = pd.to_datetime(df["time"], unit="s")
        df = df.sort_values("datetime")

    return df

# データの読み込みと表示
try:
    df = load_data()

    if df.empty:
        st.warning("DynamoDBにデータがまだありません。")
    else:
        st.subheader("受信データ一覧")
        st.dataframe(df)

        if "datetime" in df.columns and "data" in df.columns:
            st.subheader("センサー値の推移グラフ")
            # data列の値を数値に変換できる場合はグラフ化
            df["data_num"] = pd.to_numeric(df["data"], errors="coerce")
            st.line_chart(df.set_index("datetime")["data_num"])
except Exception as e:
    st.error(
        f"データの取得に失敗しました。AWS認証情報やテーブル名を確認してください。エラー: {e}"
    )
