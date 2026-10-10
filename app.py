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
  # タイムスタンプを数値化し、UTCから日本時間（JST = Asia/Tokyo）に変換
  if "time" in df.columns:
    df["time"] = pd.to_numeric(df["time"])
    df["datetime"] = (
        pd.to_datetime(df["time"], unit="s", utc=True)
        .dt.tz_convert("Asia/Tokyo")
        .dt.tz_localize(None)
    )
    df = df.sort_values("datetime")

  return df


# 16進数のASCIIペイロードをデコードしてカンマ区切りの数値リストに変換する関数
def parse_hex_data(hex_str):
  try:
    if not isinstance(hex_str, str):
      return [None, None, None]
    # 1. 16進数を文字列にデコード (例: "30363431..." -> "0641,278,526")
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
      df["val2"] = [v[1] if len(v) > 1 else None for v in parsed_values]
      df["val3"] = [v[2] if len(v) > 2 else None for v in parsed_values]

    # 【上部にグラフを表示 (val1のみ)】
    if "datetime" in df.columns and "val1" in df.columns:
      st.subheader("センサー値の推移グラフ (val1)")
      chart_df = df.set_index("datetime")[["val1"]].dropna(how="all")
      st.line_chart(chart_df)

    # 【下部に受信データ一覧を表示】
    st.subheader("受信データ一覧")
    st.dataframe(df)

except Exception as e:
  st.error(
      f"データの取得に失敗しました。AWS認証情報やテーブル名を確認してください。エラー: {e}"
  )