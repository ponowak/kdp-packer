import streamlit as st
import re
from openai import OpenAI

# Ustawienia strony
st.set_page_config(page_title="KDP Keyword Packer", page_icon="📚", layout="centered")

st.title("📚 KDP 7-Backend Keyword Packer")
st.markdown("Automatyczny generator i paker słów kluczowych dla Amazon KDP. Zero duplikatów, maksimum optymalizacji.")

# Pobieranie klucza API bezpiecznie z "Sekretów" serwera
try:
    API_KEY = st.secrets["OPENAI_API_KEY"]
except KeyError:
    st.error("⚠️ Błąd konfiguracji: Brak klucza API OpenAI na serwerze. Skontaktuj się z administratorem.")
    st.stop()

# Główny interfejs (brak paska bocznego z kluczem API!)
title_input = st.text_input("Wpisz Tytuł i Podtytuł swojej książki:", placeholder="np. Ink tracing Seasons Coloring book")

def clean_words(text):
    text = text.lower()
    words = re.findall(r'\b[a-z]{2,}\b', text)
    return set(words)

def pack_keywords(title, raw_keywords_text):
    title_words = clean_words(title)
    stop_words = {"for", "and", "the", "with", "from", "into", "your", "this", "that", "book", "coloring", "notebook"}
    
    generated_words = clean_words(raw_keywords_text)
    
    # Deduplikacja
    valid_words = generated_words - title_words - stop_words
    sorted_words = sorted(list(valid_words))
    
    lines = []
    current_line = []
    current_length = 0
    
    for word in sorted_words:
        word_len = len(word)
        space_needed = 1 if current_line else 0
        
        if current_length + space_needed + word_len <= 50:
            current_line.append(word)
            current_length += space_needed + word_len
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_length = word_len
            
        if len(lines) == 7:
            break
            
    if current_line and len(lines) < 7:
        lines.append(" ".join(current_line))
        
    while len(lines) < 7:
        lines.append("")
        
    return lines

# Przycisk akcji
if st.button("Generuj i Pakuj (AI)", type="primary"):
    if not title_input:
        st.warning("⚠️ Proszę wpisać tytuł książki.")
    else:
        with st.spinner('AI generuje i pakuje słowa kluczowe...'):
            try:
                client = OpenAI(api_key=API_KEY)
                
                prompt = f"""Jesteś ekspertem Amazon KDP SEO. 
Dla książki o tytule: "{title_input}"
Wygeneruj 100 powiązanych tematycznie, pojedynczych słów kluczowych.
IMPORTANT: ALL KEYWORDS MUST BE STRICTLY IN ENGLISH.
Skup się na synonimach, materiałach, niszach, odbiorcach (kto to kupuje), zastosowaniach i emocjach.
Zwróć TYLKO słowa oddzielone przecinkami, bez żadnego tekstu wstępnego.
Używaj tylko małych liter. Wyklucz słowa, które są już w tytule."""

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                
                raw_keywords = response.choices[0].message.content
                lines = pack_keywords(title_input, raw_keywords)
                
                st.success("✅ Gotowe! Skopiuj poniższe pola na Amazon KDP.")
                
                st.subheader("Twoje 7 Pól Backend:")
                for i, line in enumerate(lines):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.code(line, language="text")
                    with col2:
                        st.caption(f"{len(line)}/50 znaków")
                
                with st.expander("Zobacz surowe słowa wygenerowane przez AI"):
                    st.write(raw_keywords)

            except Exception as e:
                st.error(f"Wystąpił błąd: {str(e)}")
