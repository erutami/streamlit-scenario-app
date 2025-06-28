import streamlit as st

st.title("📘 シナリオプロット登録フォーム")

chapter_index = st.number_input("章番号（0=プロローグ）", min_value=0, step=1)
chapter_title = st.text_input("章タイトル")
scene_index = st.number_input("シーン番号", min_value=0, step=1)
plot_text = st.text_area("プロット本文")
location = st.text_input("場所")
mood = st.text_input("雰囲気")

related_characters = st.text_input("登場キャラUUID（カンマ区切り）")
related_context_ids = st.text_input("関連設定ID（カンマ区切り）")

if st.button("送信"):
    st.success("✅ シーンを登録しました！（ダミー処理）")
    st.json({
        "chapter_index": chapter_index,
        "chapter_title": chapter_title,
        "scene_index": scene_index,
        "plot_text": plot_text,
        "location": location,
        "mood": mood,
        "related_characters": [s.strip() for s in related_characters.split(",") if s.strip()],
        "related_context_ids": [s.strip() for s in related_context_ids.split(",") if s.strip()]
    })
