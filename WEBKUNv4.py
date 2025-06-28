import streamlit as st
from supabase import create_client
import openai
import pinecone
import os

# --- 環境変数読み込み ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
PINECONE_API_KEY = st.secrets["PINECONE_API_KEY"]
PINECONE_ENV = st.secrets["PINECONE_ENVIRONMENT"]
PINECONE_INDEX = st.secrets["PINECONE_INDEX_NAME"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]

# --- 認証チェック ---
password = st.text_input("パスワードを入力", type="password")
if password != APP_PASSWORD:
    st.stop()

# --- クライアント初期化 ---
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai.api_key = OPENAI_API_KEY
pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
if PINECONE_INDEX not in pinecone.list_indexes():
    pinecone.create_index(name=PINECONE_INDEX, dimension=1536)
index = pinecone.Index(PINECONE_INDEX)

# --- モード選択 ---
mode = st.radio("モード選択", ["新規作成", "修正モード"], horizontal=True)

# --- キャラ情報取得 ---
char_resp = supabase.table("characters").select("id, name").execute()
if char_resp.error:
    st.error(f"キャラ取得エラー: {char_resp.error.message}")
    st.stop()
char_data = char_resp.data
char_dict = {c["name"]: c["id"] for c in char_data}

# --- 章タイトル一覧取得 ---
chapter_resp = supabase.table("scenario_plots").select("chapter_title, chapter_index, id, scene_index, plot_text, location, mood, related_characters, related_context_ids").execute()
if chapter_resp.error:
    st.error(f"章情報取得エラー: {chapter_resp.error.message}")
    st.stop()
chapter_titles_data = chapter_resp.data
chapter_title_map = {c["chapter_title"]: c["chapter_index"] for c in chapter_titles_data if c["chapter_title"]}
chapter_title_list = list(chapter_title_map.keys())

selected_record = None
if mode == "修正モード":
    record_options = {f"{r['chapter_title']} - {r['scene_index']}": r for r in chapter_titles_data}
    selected_label = st.selectbox("修正対象を選択", options=[""] + list(record_options.keys()))
    selected_record = record_options.get(selected_label)

# --- UI表示 ---
st.title("\U0001F4D8 シナリオプロット登録")

plot_text = st.text_area("プロット本文", value=selected_record["plot_text"] if selected_record else "", key="plot_text")

# --- Pinecone同期ボタン ---
st.markdown("---")
if st.button("\U0001F9E0 Pineconeに同期"):
    data_resp = supabase.table("scenario_plots").select("id, plot_text, chapter_title, scene_index").eq("needs_indexing", True).execute()
    if data_resp.error:
        st.error(f"同期データ取得エラー: {data_resp.error.message}")
    else:
        data = data_resp.data
        if not data:
            st.info("同期対象の新しいデータはありません。")
        else:
            for rec in data:
                text = rec["plot_text"]
                vec = openai.Embedding.create(model="text-embedding-3-small", input=text)["data"][0]["embedding"]
                index.upsert([(rec["id"], vec, {"chapter_title": rec["chapter_title"], "scene_index": rec["scene_index"]})])
            ids = [rec["id"] for rec in data]
            supabase.table("scenario_plots").update({"needs_indexing": False}).in_("id", ids).execute()
            st.success(f"{len(data)} 件を Pinecone に同期しました！")
