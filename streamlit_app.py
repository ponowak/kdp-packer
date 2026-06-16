import streamlit as st
import re
from openai import OpenAI
from supabase import create_client, Client

st.set_page_config(page_title="KDP Keyword Packer", page_icon="📚", layout="centered")

# Inicjalizacja klientów API z "Sekretów"
try:
    API_KEY = st.secrets["OPENAI_API_KEY"]
    SUPA_URL = st.secrets["SUPABASE_URL"]
    SUPA_KEY = st.secrets["SUPABASE_KEY"]
except KeyError:
    st.error("⚠️ Błąd konfiguracji serwera (brak kluczy w st.secrets).")
    st.stop()

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPA_URL, SUPA_KEY)

supabase = init_supabase()
openai_client = OpenAI(api_key=API_KEY)

# Autoryzacja i Sesja
if "user" not in st.session_state:
    st.session_state.user = None

def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.success("Zalogowano pomyślnie!")
        st.rerun()
    except Exception as e:
        st.error("Błąd logowania: Błędny email lub hasło.")

def signup(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        st.success("Konto utworzone! Możesz się teraz zalogować w zakładce Logowanie.")
    except Exception as e:
        st.error(f"Błąd rejestracji: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# ---------------------------------------------------------------------
# EKRAN LOGOWANIA (Gdy użytkownik nie jest zalogowany)
# ---------------------------------------------------------------------
if st.session_state.user is None:
    st.title("📚 KDP 7-Backend Packer")
    st.markdown("Zaloguj się, aby uzyskać dostęp do narzędzia. Na start otrzymujesz **3 darmowe użycia**!")
    
    tab1, tab2 = st.tabs(["Logowanie", "Rejestracja"])
    
    with tab1:
        log_email = st.text_input("Email", key="log_email")
        log_pass = st.text_input("Hasło", type="password", key="log_pass")
        if st.button("Zaloguj się"):
            if log_email and log_pass:
                login(log_email, log_pass)
            else:
                st.warning("Podaj email i hasło.")
                
    with tab2:
        reg_email = st.text_input("Email", key="reg_email")
        reg_pass = st.text_input("Hasło (min. 6 znaków)", type="password", key="reg_pass")
        if st.button("Zarejestruj się"):
            if reg_email and reg_pass:
                signup(reg_email, reg_pass)
            else:
                st.warning("Wypełnij oba pola.")
                
    st.stop() # Niezalogowani nie widzą tego co jest poniżej tej linii!

# ---------------------------------------------------------------------
# GŁÓWNA APLIKACJA (Dla zalogowanych)
# ---------------------------------------------------------------------

# Pobieranie aktualnych kredytów z bazy
try:
    profile_data = supabase.table('profiles').select('credits').eq('id', st.session_state.user.id).execute()
    current_credits = profile_data.data[0]['credits']
except:
    current_credits = 0

# Pasek użytkownika u góry
col_user, col_cred, col_logout = st.columns([3, 2, 1])
with col_user:
    st.write(f"👤 Zalogowany: **{st.session_state.user.email}**")
with col_cred:
    if current_credits > 0:
        st.success(f"🎟️ Pozostałe tokeny: **{current_credits}**")
    else:
        st.error("🎟️ Brak tokenów!")
with col_logout:
    if st.button("Wyloguj"):
        logout()

st.divider()

# Górny pasek z tytułem i flagami po prawej
col1, col2 = st.columns([2, 1])
with col1:
    st.title("📚 KDP Keyword Packer")
with col2:
    st.write("") 
    lang_choice = st.radio(
        "Język:",
        ["🇺🇸 EN", "🇩🇪 DE", "🇫🇷 FR", "🇪🇸 ES", "🇮🇹 IT"],
        horizontal=True,
        label_visibility="collapsed"
    )

lang_map = {"🇺🇸 EN": "English", "🇩🇪 DE": "German", "🇫🇷 FR": "French", "🇪🇸 ES": "Spanish", "🇮🇹 IT": "Italian"}
target_language = lang_map[lang_choice]

title_input = st.text_input("Wpisz Tytuł i Podtytuł swojej książki:", placeholder="np. Ink tracing Seasons Coloring book")

def clean_words(text):
    text = text.lower()
    words = re.findall(r'\b[a-zà-ÿß]{2,}\b', text)
    return set(words)

def pack_keywords(title, raw_keywords_text):
    title_words = clean_words(title)
    stop_words = {
        "for", "and", "the", "with", "from", "into", "your", "this", "that", "book", "coloring", "notebook",
        "und", "für", "mit", "von", "das", "der", "die", "ein", "eine", 
        "et", "pour", "le", "la", "les", "un", "une", "avec", "dans",
        "con", "para", "el", "los", "las", "una",
        "per", "il", "lo", "gli"
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
    if current_credits <= 0:
        st.error("🚫 Wykorzystałeś wszystkie darmowe tokeny. Za chwilę w tym miejscu pojawi się przycisk dokupienia pakietu!")
    elif not title_input:
        st.warning("⚠️ Proszę wpisać tytuł książki.")
    else:
        with st.spinner(f'AI generuje słowa w języku: {target_language}...'):
            try:
                prompt = f"Jesteś ekspertem Amazon KDP SEO.\nDla książki o tytule: \"{title_input}\"\nWygeneruj 100 powiązanych tematycznie, pojedynczych słów kluczowych.\nIMPORTANT: ALL KEYWORDS MUST BE STRICTLY IN {target_language.upper()}.\nSkup się na synonimach, materiałach, niszach, odbiorcach (kto to kupuje), zastosowaniach i emocjach.\nZwróć TYLKO słowa oddzielone przecinkami, bez żadnego tekstu wstępnego.\nUżywaj tylko małych liter. Wyklucz słowa, które są już w tytule."

                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                
                raw_keywords = response.choices[0].message.content
                lines = pack_keywords(title_input, raw_keywords)
                
                # ODEJMOWANIE KREDYTU W BAZIE!
                new_credits = current_credits - 1
                supabase.table('profiles').update({'credits': new_credits}).eq('id', st.session_state.user.id).execute()
                
                st.success(f"✅ Gotowe! Pobrany 1 token. Skopiuj pola poniżej.")
                
                export_text = f"Tytuł: {title_input}\nJęzyk: {target_language}\n\n--- 7 Backend Keywords ---\n"
                
                for i, line in enumerate(lines):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.code(line, language="text")
                    with col2:
                        st.caption(f"{len(line)}/50 znaków")
                    export_text += f"Pole {i+1}: {line}\n"
                
                st.download_button(
                    label="📥 Pobierz wyniki (.TXT)",
                    data=export_text.encode('utf-8'),
                    file_name="kdp_keywords.txt",
                    mime="text/plain"
                )
                
                with st.expander("Zobacz surowe słowa (AI)"):
                    st.write(raw_keywords)

            except Exception as e:
                st.error(f"Wystąpił błąd: {str(e)}")