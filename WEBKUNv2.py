import streamlit as st
from supabase import create_client
from dotenv import load_dotenv
import os

# --- 初期設定 ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- キャラ情報取得 ---
char_data = supabase.table("characters").select("id, name").execute().data
char_dict = {c["name"]: c["id"] for c in char_data}

# --- 章タイトル一覧取得 ---
chapter_titles_data = supabase.table("scenario_plots").select("chapter_title, chapter_index").execute().data
chapter_title_map = {c["chapter_title"]: c["chapter_index"] for c in chapter_titles_data if c["chapter_title"]}
chapter_title_list = list(chapter_title_map.keys())

# --- UI表示 ---
st.title("\U0001F4D8 シナリオプロット登録")

plot_text = st.text_area("プロット本文")

# --- 章タイトル＆番号入力 ---
chapter_title_options = chapter_title_list + ["新規追加"]
chapter_title = st.selectbox("章タイトル", options=chapter_title_options)
if chapter_title == "新規追加":
    chapter_title = st.text_input("新しい章タイトル")
    chapter_index = st.number_input("新しい章番号 (0=プロローグ)", min_value=0, step=1)
else:
    chapter_index = chapter_title_map.get(chapter_title, 0)

# --- シーン番号入力（自動＋修正可） ---
scene_data = supabase.table("scenario_plots").select("scene_index").eq("chapter_index", chapter_index).execute().data
scene_index_default = max([s["scene_index"] for s in scene_data], default=-1) + 1
scene_index = st.number_input("シーン番号", min_value=0, step=1, value=scene_index_default)

location = st.text_input("場所")

# --- 雰囲気（複数選択＋自由記述） ---
mood_options = ["切ない", "悲しい", "怒り", "不安", "希望", "緊張感", "熱い", "ほのぼの", "その他"]
selected_moods = st.multiselect("雰囲気（複数選択可）", options=mood_options)
custom_mood = st.text_input("その他の雰囲気（自由記述）")
mood = "/".join(selected_moods + ([custom_mood] if custom_mood else []))

# --- キャラ選択UI（複数選択＋UUID） ---
st.markdown("**登場キャラ**（名前をクリックでUUID追加）")
selected_chars = st.multiselect("登場キャラ選択", options=list(char_dict.keys()))
related_characters = [char_dict[name] for name in selected_chars]

manual_char_ids = st.text_input("キャラUUID（カンマ区切り手入力）")
manual_ids = [s.strip() for s in manual_char_ids.split(",") if s.strip()]
related_characters += manual_ids

# --- 関連ID入力 ---
related_context_ids = st.text_input("関連ID(カンマ区切り)")
context_ids = [s.strip() for s in related_context_ids.split(",") if s.strip()]

if st.button("登録"):
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
        supabase.table("scenario_plots").insert(record).execute()
        st.success("登録成功しました！")
        st.json(record)
    except Exception as e:
        st.error(f"登録エラー: {e}")
