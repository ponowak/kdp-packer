import os
import re
import hmac
import hashlib
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from supabase import create_client, Client
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-key-change-in-prod")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
LEMONSQUEEZY_WEBHOOK_SECRET = os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = None

def generate_and_clean_keywords(title, subtitle, language):
    if not client:
        raise Exception("OpenAI API key not configured")
        
    prompt = f"""
    Generate highly profitable Amazon KDP backend keywords for a book with:
    Title: {title}
    Subtitle: {subtitle}
    Target language: {language}
    
    Rules:
    - Return ONLY comma-separated keywords.
    - Do not use quotes or list numbers.
    - Focus on low-competition, high-search-volume long-tail keywords.
    - Exclude the exact words already used in the Title and Subtitle.
    - Provide at least 50 unique single words.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=300
    )
    
    raw_text = response.choices[0].message.content
    
    # Cleaning and packing logic
    words = re.split(r'[,;\n]+', raw_text)
    cleaned = []
    for w in words:
        w = w.strip().lower()
        if w:
            cleaned.extend(w.split())
    
    unique_words = []
    for w in cleaned:
        if w not in unique_words:
            unique_words.append(w)
            
    boxes = []
    current_box = []
    current_length = 0
    
    for word in unique_words:
        if current_length + len(word) + (1 if current_box else 0) <= 50:
            current_box.append(word)
            current_length += len(word) + (1 if current_box else 0)
        else:
            boxes.append(" ".join(current_box))
            current_box = [word]
            current_length = len(word)
            
        if len(boxes) == 7:
            break
            
    if current_box and len(boxes) < 7:
        boxes.append(" ".join(current_box))
        
    return boxes, raw_text

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    response = supabase.table("profiles").select("credits").eq("id", session['user_id']).execute()
    credits = response.data[0]['credits'] if response.data else 0
    
    return render_template('app.html', credits=credits, email=session.get('email'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        action = request.form.get('action')
        
        try:
            if action == 'register':
                res = supabase.auth.sign_up({"email": email, "password": password})
            else:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                
            if res.user:
                session['user_id'] = res.user.id
                session['email'] = email
                
                # Proste obejście dla braku triggera - sprawdzamy czy to pierwsze logowanie (rejestracja)
                if action == 'register':
                    try:
                        # Próbujemy dodać rekord do profiles. Jeśli baza pluje błędem (bo jest trigger RLS), 
                        # to zignoruje.
                        supabase.table("profiles").insert({"id": res.user.id, "email": email, "credits": 3}).execute()
                    except Exception as inner_e:
                        print("Profile init error (might be expected if trigger exists):", inner_e)
                        pass
                
                return redirect(url_for('index'))
        except Exception as e:
            return render_template('login.html', error=str(e))
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/process', methods=['POST'])
def process():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    response = supabase.table("profiles").select("credits").eq("id", session['user_id']).execute()
    credits = response.data[0]['credits'] if response.data else 0
    
    if credits <= 0:
        return jsonify({"error": "Brak tokenów! Kup pakiet, aby kontynuować."}), 402
        
    data = request.json
    title = data.get('title', '')
    subtitle = data.get('subtitle', '')
    language = data.get('language', 'en-US')
    
    if not title:
        return jsonify({"error": "Puste pole tytułu"}), 400
        
    # Deduct credit
    supabase.table("profiles").update({"credits": credits - 1}).eq("id", session['user_id']).execute()
    
    try:
        boxes, raw_text = generate_and_clean_keywords(title, subtitle, language)
        return jsonify({
            "boxes": boxes,
            "raw_text": raw_text,
            "remaining_credits": credits - 1
        })
    except Exception as e:
        # Zwrot tokenu w przypadku awarii OpenAI
        supabase.table("profiles").update({"credits": credits}).eq("id", session['user_id']).execute()
        return jsonify({"error": f"Błąd generatora: {str(e)}"}), 500

@app.route('/webhook/lemonsqueezy', methods=['POST'])
def webhook():
    signature = request.headers.get('X-Signature')
    if not signature or not LEMONSQUEEZY_WEBHOOK_SECRET:
        return "Missing signature or secret", 400

    payload = request.get_data()
    digest = hmac.new(
        LEMONSQUEEZY_WEBHOOK_SECRET.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(digest, signature):
        return "Invalid signature", 401

    data = request.json
    event_name = data.get('meta', {}).get('event_name')

    if event_name == 'order_created':
        customer_email = data.get('data', {}).get('attributes', {}).get('user_email')
        
        if customer_email:
            res = supabase.table("profiles").select("id, credits").eq("email", customer_email).execute()
            if res.data:
                user_id = res.data[0]['id']
                current_credits = res.data[0]['credits']
                supabase.table("profiles").update({"credits": current_credits + 10}).eq("id", user_id).execute()

    return "OK", 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
