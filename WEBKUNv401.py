import streamlit as st
from supabase import create_client
from dotenv import load_dotenv
import os
import openai
from openai import OpenAI
from pinecone import Pinecone

# --- 初期設定 ---
load_dotenv()
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
PINECONE_API_KEY = st.secrets["PINECONE_API_KEY"]
PINECONE_INDEX_NAME = st.secrets["PINECONE_INDEX_NAME"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

EMBEDDING_MODEL = "text-embedding-3-small"

# --- 認証 ---
password = st.text_input("パスワードを入力", type="password")
if password != st.secrets["APP_PASSWORD"]:
    st.stop()

# --- モード選択 ---
mode = st.radio("モード選択", ["新規作成", "修正モード"], horizontal=True)

# --- キャラ情報取得 ---
char_data = supabase.table("characters").select("id, name").execute().data
char_dict = {c["name"]: c["id"] for c in char_data}

# --- 章タイトル一覧取得 ---
chapter_titles_data = supabase.table("scenario_plots").select("chapter_title, chapter_index, id, scene_index, plot_text, location, mood, related_characters, related_context_ids").execute().data
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

chapter_title_options = chapter_title_list + ["新規追加"]
chapter_title_default = selected_record["chapter_title"] if selected_record else chapter_title_options[0]
chapter_title = st.selectbox("章タイトル", options=chapter_title_options, index=chapter_title_options.index(chapter_title_default))
if chapter_title == "新規追加":
    chapter_title = st.text_input("新しい章タイトル", value="" if not selected_record else selected_record["chapter_title"])
    chapter_index = st.number_input("新しい章番号 (0=プロローグ)", min_value=0, step=1, value=0 if not selected_record else selected_record["chapter_index"])
else:
    chapter_index = chapter_title_map.get(chapter_title, 0)

scene_data = supabase.table("scenario_plots").select("scene_index").eq("chapter_index", chapter_index).execute().data
scene_index_default = selected_record["scene_index"] if selected_record else max([s["scene_index"] for s in scene_data], default=-1) + 1
scene_index = st.number_input("シーン番号", min_value=0, step=1, value=scene_index_default)

location = st.text_input("場所", value=selected_record["location"] if selected_record else "", key="location")

mood_options = ["切ない", "悲しい", "怒り", "不安", "希望", "緊張感", "熱い", "ほのぼの", "その他"]
stored_moods = selected_record["mood"].split("/") if selected_record else []
default_moods = [m for m in stored_moods if m in mood_options]
unknown_moods = [m for m in stored_moods if m not in mood_options]
selected_moods = st.multiselect("雰囲気（複数選択可）", options=mood_options, default=default_moods, key="selected_moods")
custom_mood = st.text_input("その他の雰囲気（自由記述）", value="/".join(unknown_moods), key="custom_mood")
mood = "/".join(selected_moods + ([custom_mood] if custom_mood else []))

st.markdown("**登場キャラ**（名前をクリックでUUID追加）")
selected_chars = st.multiselect("登場キャラ選択", options=list(char_dict.keys()), key="selected_chars")
related_characters = [char_dict[name] for name in selected_chars]
manual_char_ids = st.text_input("キャラUUID（カンマ区切り手入力）", key="manual_char_ids")
manual_ids = [s.strip() for s in manual_char_ids.split(",") if s.strip()]
related_characters += manual_ids

related_context_ids = st.text_input("関連ID(カンマ区切り)", value=",".join(selected_record["related_context_ids"]) if selected_record else "", key="related_context_ids")
context_ids = [s.strip() for s in related_context_ids.split(",") if s.strip()]

if st.button("保存"):
    record = {
        "chapter_index": chapter_index,
        "chapter_title": chapter_title,
        "scene_index": scene_index,
        "plot_text": plot_text,
        "location": location,
        "mood": mood,
        "related_characters": related_characters,
        "related_context_ids": context_ids,
        "needs_indexing": True
    }
    try:
        if mode == "修正モード" and selected_record:
            supabase.table("scenario_plots").update(record).eq("id", selected_record["id"]).execute()
            st.success("修正が完了しました！")
        else:
            supabase.table("scenario_plots").insert(record).execute()
            st.success("登録成功しました！")
        st.json(record)
    except Exception as e:
        st.error(f"保存エラー: {e}")

if st.button("リセット"):
    for key in ["plot_text", "location", "custom_mood", "related_context_ids", "manual_char_ids", "selected_moods", "selected_chars"]:
        if key in st.session_state:
            st.session_state[key] = [] if isinstance(st.session_state[key], list) else ""

# --- Pinecone同期機能 ---
st.markdown("---")
st.header("\U0001F9E0 Pinecone同期操作")

def build_chunk_text(plot_text, location, mood):
    return f"{plot_text}\n場所: {location}\n雰囲気: {mood}"

def build_context_id(chapter_index, scene_index):
    return f"plot-ch{chapter_index}-{scene_index}"

def embed_text(text):
    response = client.embeddings.create(
        input=[text],
        model=EMBEDDING_MODEL
    )
    return response.data[0].embedding

def save_to_pinecone(records):
    pinecone_vectors = []
    for record in records:
        chunk = build_chunk_text(record["plot_text"], record["location"], record["mood"])
        context_id = build_context_id(record["chapter_index"], record["scene_index"])
        vector = embed_text(chunk)

        metadata = {
            "context_id": context_id,
            "chapter_index": record["chapter_index"],
            "scene_index": record["scene_index"],
            "chunk": chunk,
            "chunk_type": "plot_text",
            "chapter_title": record["chapter_title"],
            "related_characters": record["related_characters"],
            "related_context_ids": record["related_context_ids"]
        }

        pinecone_vectors.append({
            "id": context_id,
            "values": vector,
            "metadata": metadata
        })

    index.upsert(vectors=pinecone_vectors)
    record_ids = [r["id"] for r in records]
    for rid in record_ids:
        supabase.table("scenario_plots").update({"needs_indexing": False}).eq("id", rid).execute()

if st.button("Pineconeに同期"):
    try:
        data_to_index = supabase.table("scenario_plots").select("*").eq("needs_indexing", True).execute().data
        if not data_to_index:
            st.info("同期対象はありません。")
        else:
            save_to_pinecone(data_to_index)
            st.success("Pineconeへの同期が完了しました！")
    except Exception as e:
        st.error(f"同期中にエラーが発生しました: {e}")
