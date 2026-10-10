import altair as alt
import boto3
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# 60秒（60000ミリ秒）ごとに自動リロードを実行
st_autorefresh(interval=60000, limit=None, key="datarefresh")

st.title("センサーデータ")


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
    # タイムスタンプを数値化し、UTCから日本時間（JST = Asia/Tokyo）に変換
    if "time" in df.columns:
        df["time"] = pd.to_numeric(df["time"])
        df["datetime"] = (
            pd.to_datetime(df["time"], unit="s", utc=True)
            .dt.tz_convert("Asia/Tokyo")
            .dt.tz_localize(None)
        )
        df = df.sort_values("datetime", ascending=False)

    return df


# 16進数のASCIIペイロードをデコードしてカンマ区切りの数値リストに変換する関数
def parse_hex_data(hex_str):
    try:
        if not isinstance(hex_str, str):
            return [None, None, None]
        # 1. 16進数を文字列にデコード
        ascii_str = bytes.fromhex(hex_str).decode("utf-8")
        # 2. カンマで分割して数値に変換
        values = [float(v.strip()) for v in ascii_str.split(",")]
        return values
    except Exception:
        return [None, None, None]


# データの読み込みと表示
try:
    df = load_data()

    if df.empty:
        st.warning("DynamoDBにデータがまだありません。")
    else:
        # データの `data` 列をパースして個別のセンサー値列を作成
        if "data" in df.columns:
            parsed_values = df["data"].apply(parse_hex_data)
            df["val1"] = [v[0] for v in parsed_values]
            df["val2"] = [v[1] / 10.0 if len(v) > 1 and v[1] is not None else None for v in parsed_values]
            df["val3"] = [v[2] / 10.0 if len(v) > 2 and v[2] is not None else None for v in parsed_values]

        # 【上部にグラフを表示 (軸の文字色を黒に設定)】
        if "datetime" in df.columns and "val1" in df.columns:
            st.subheader("二酸化炭素濃度（ppm）")
            chart_df = df[["datetime", "val1"]].dropna(subset=["val1"])

            chart = (
                alt.Chart(chart_df)
                .mark_line(point=True)
                .encode(
                    x=alt.X(
                        "datetime:T",
                        sort="descending",
                        title="時刻",
                        axis=alt.Axis(
                            grid=True,
                            tickCount="hour",
                            format="%H:%M",
                            gridColor="#888888",
                        ),
                    ),
                    y=alt.Y(
                        "val1:Q",
                        title="ppm",
                        axis=alt.Axis(grid=True, gridColor="#888888"),
                    ),
                )
                .interactive()
                .configure_view(fill="#FFFFCC")
                .configure_axis(
                    labelColor="black",  # 目盛りの文字色を黒に指定
                    titleColor="black",  # 軸タイトルの文字色を黒に指定
                )
            )
            st.altair_chart(chart, use_container_width=True)

        # 【下部に受信データ一覧を表示】
        st.subheader("受信データ一覧")
        
        if not df.empty:
            table_df = pd.DataFrame()
            table_df["デバイス"] = df.get("device", "")
            table_df["時刻"] = df.get("datetime", "")
            table_df["val1 (ppm)"] = df.get("val1", pd.Series())
            table_df["val2 (℃)"] = df["val2"].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "")
            table_df["val3 (%)"] = df["val3"].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "")

            st.dataframe(table_df, use_container_width=True, height=400)

except Exception as e:
    st.error(
        f"データの取得に失敗しました。AWS認証情報やテーブル名を確認してください。エラー: {e}"
    )
