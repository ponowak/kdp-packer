import streamlit as st
import re
from openai import OpenAI

st.set_page_config(page_title="KDP Keyword Packer", page_icon="📚", layout="centered")

# Górny pasek z tytułem i flagami po prawej
col1, col2 = st.columns([2, 1])
with col1:
    st.title("📚 KDP 7-Backend Packer")
with col2:
    st.write("") # Odstęp, żeby wyrównać w pionie
    lang_choice = st.radio(
        "Język:",
        ["🇺🇸 EN", "🇩🇪 DE", "🇫🇷 FR", "🇪🇸 ES", "🇮🇹 IT"],
        horizontal=True,
        label_visibility="collapsed"
    )

lang_map = {
    "🇺🇸 EN": "English",
    "🇩🇪 DE": "German",
    "🇫🇷 FR": "French",
    "🇪🇸 ES": "Spanish",
    "🇮🇹 IT": "Italian"
}
target_language = lang_map[lang_choice]

st.markdown("Automatyczny generator i paker słów kluczowych dla Amazon KDP. Zero duplikatów.")

try:
    API_KEY = st.secrets["OPENAI_API_KEY"]
except KeyError:
    st.error("⚠️ Błąd konfiguracji: Brak klucza API OpenAI na serwerze.")
    st.stop()

title_input = st.text_input("Wpisz Tytuł i Podtytuł swojej książki:", placeholder="np. Ink tracing Seasons Coloring book")

def clean_words(text):
    text = text.lower()
    # Zmiana z [a-z] na [a-zà-ÿ] żeby obsługiwało niemieckie umlauty i francuskie akcenty
    words = re.findall(r'\b[a-zà-ÿß]{2,}\b', text)
    return set(words)

def pack_keywords(title, raw_keywords_text):
    title_words = clean_words(title)
    
    # Podstawowe Stop Words dla wybranych języków, żeby nie marnować znaków
    stop_words = {
        "for", "and", "the", "with", "from", "into", "your", "this", "that", "book", "coloring", "notebook",
        "und", "für", "mit", "von", "das", "der", "die", "ein", "eine", # DE
        "et", "pour", "le", "la", "les", "un", "une", "avec", "dans", # FR
        "con", "para", "el", "los", "las", "una", # ES
        "per", "il", "lo", "gli" # IT
    }
    
    generated_words = clean_words(raw_keywords_text)
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

if st.button(f"Generuj i Pakuj ({target_language})", type="primary"):
    if not title_input:
        st.warning("⚠️ Proszę wpisać tytuł książki.")
    else:
        with st.spinner(f'AI generuje słowa w języku: {target_language}...'):
            try:
                client = OpenAI(api_key=API_KEY)
                prompt = f"""Jesteś ekspertem Amazon KDP SEO. 
Dla książki o tytule: "{title_input}"
Wygeneruj 100 powiązanych tematycznie, pojedynczych słów kluczowych.
IMPORTANT: ALL KEYWORDS MUST BE STRICTLY IN {target_language.upper()}.
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
                
                # Przygotowanie tekstu do pliku TXT
                export_text = f"Tytuł: {title_input}\nJęzyk: {target_language}\n\n--- 7 Backend Keywords ---\n"
                
                for i, line in enumerate(lines):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.code(line, language="text")
                    with col2:
                        st.caption(f"{len(line)}/50 znaków")
                    export_text += f"Pole {i+1}: {line}\n"
                
                st.download_button(
                    label="📥 Pobierz wyniki jako plik .TXT",
                    data=export_text.encode('utf-8'),
                    file_name="kdp_keywords.txt",
                    mime="text/plain"
                )
                
                with st.expander("Zobacz surowe słowa wygenerowane przez AI"):
                    st.write(raw_keywords)

            except Exception as e:
                st.error(f"Wystąpił błąd: {str(e)}")