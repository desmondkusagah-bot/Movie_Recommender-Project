import streamlit as st
import pickle
import pandas as pd
import requests
import random
import firebase_admin
from firebase_admin import credentials, auth, firestore
from streamlit_lottie import st_lottie
import json 

# --- 1. FIREBASE INITIALIZATION ---
if not firebase_admin._apps:
    if "firebase" in st.secrets:
        secret_dict = json.loads(st.secrets["firebase"]["service_account"])
        cred = credentials.Certificate(secret_dict)
    else:
        cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- 2. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="CineMatch AI | Group 6",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 3. SESSION STATE MANAGEMENT ---
if 'user_auth' not in st.session_state:
    st.session_state.user_auth = False
if 'recs' not in st.session_state:
    st.session_state.recs = []
if 'last_choice' not in st.session_state:
    st.session_state.last_choice = ""

# --- 4. ASSET & API HELPERS ---
def load_lottieurl(url):
    try:
        r = requests.get(url)
        return r.json() if r.status_code == 200 else None
    except: return None

lottie_movie = load_lottieurl("https://lottie.host/8287340b-715d-4f11-9257-2e2197170a49/X9XjNfG3W3.json")

def get_movie_details(movie_id):
    api_key = "9a17b2be2c5c6caeba84998a102f7cde"
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}&append_to_response=watch/providers"
    try:
        res = requests.get(url).json()
        poster_path = res.get('poster_path')
        poster = "https://image.tmdb.org/t/p/w500" + poster_path if poster_path else "https://via.placeholder.com/500x750"
        providers = res.get('watch/providers', {}).get('results', {}).get('GH', {}).get('flatrate', [])
        p_names = [p['provider_name'] for p in providers] if providers else ["Rental/Cinema Only"]
        return poster, p_names
    except:
        return "https://via.placeholder.com/500x750", ["Data Unavailable"]

def convert_recs_to_csv(recs_list):
    df = pd.DataFrame(recs_list)
    df.columns = ['Movie ID', 'Movie Title']
    return df.to_csv(index=False).encode('utf-8')

# --- 5. AUTHENTICATION UI ---
def apply_login_style():
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)), 
                        url('https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=1350&q=80');
            background-size: cover; background-attachment: fixed;
        }
        [data-testid="stVerticalBlock"] > div:has(div.login-card) {
            background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(15px);
            border-radius: 20px; padding: 40px; border: 1px solid rgba(255,255,255,0.1);
        }
        h1 { color: #E50914 !important; font-weight: 800 !important; }
        </style>
    """, unsafe_allow_html=True)

def login_screen():
    apply_login_style()
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>🎬 CineMatch AI</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #ccc;'>GROUP 6 PREMIUM SOLUTION</p>", unsafe_allow_html=True)
        if lottie_movie: st_lottie(lottie_movie, height=200)
        t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
        
        with t1:
            e = st.text_input("Email", placeholder="your@email.com", key="l_e")
            p = st.text_input("Password", type="password", key="l_p")
            if st.button("SIGN IN", use_container_width=True):
                # --- UPDATED LOGIN FIX ---
                # Using Firebase Auth REST API to verify password
                firebase_web_api_key = "AIzaSyCyZ9aCtchLZyejKzTRjbSDnNp8uu9o1RI" # Ensure this is your FIREBASE Web API Key
                auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_web_api_key}"
                
                try:
                    payload = {"email": e, "password": p, "returnSecureToken": True}
                    res = requests.post(auth_url, json=payload)
                    
                    if res.status_code == 200:
                        user_data = res.json()
                        user_info = auth.get_user(user_data['localId'])
                        st.session_state.user_auth = True
                        st.session_state.u_id = user_data['localId']
                        st.session_state.u_name = user_info.display_name if user_info.display_name else e.split('@')[0]
                        st.rerun()
                    else:
                        st.error("Login Failed. Please check your email and password.")
                except Exception as ex:
                    st.error("An error occurred during login. Please try again.")
        
        with t2:
            ne, nu, np = st.text_input("Email", key="s_e"), st.text_input("Username", key="s_u"), st.text_input("Password", type="password", key="s_p")
            if st.button("CREATE ACCOUNT", use_container_width=True):
                try:
                    auth.create_user(email=ne, password=np, display_name=nu)
                    st.success("Account Created! Please Login.")
                except Exception as ex: st.error(ex)
        st.markdown('</div>', unsafe_allow_html=True)

# --- 6. DATA LOADING ---
@st.cache_resource(show_spinner=False)
def load_data():
    movies = pd.DataFrame(pickle.load(open('movie_dict.pkl', 'rb')))
    similarity = pickle.load(open('similarity.pkl', 'rb'))
    return movies, similarity

movies, similarity = load_data()

# --- 7. MAIN APP LOGIC ---
if not st.session_state.user_auth:
    login_screen()
else:
    # --- SIDEBAR ---
    with st.sidebar:
        try: st.image("logo.jpg", width=250)
        except: pass
        st.markdown("<h1 style='text-align: center; color: #E50914;'>GROUP 6 SOLUTION</h1>", unsafe_allow_html=True)
        st.write(f"Logged in as: **{st.session_state.u_name}**")
        if st.button("🚪 Sign Out", use_container_width=True):
            st.session_state.user_auth = False
            st.rerun()
        st.markdown("---")
        theme = st.select_slider("App Vibe:", options=["Classic Light", "Netflix Dark"], value="Netflix Dark")
        st.subheader("📜 Recent Favorites")
        try:
            hist = db.collection('favorites').document(st.session_state.u_id).collection('movies').limit(5).stream()
            for d in hist: st.caption(f"⭐ {d.to_dict()['title']}")
        except: st.caption("No favorites yet.")
        
        st.markdown("---")
        st.info("Engine: Cosine Similarity")
        st.write("Developed by: **ML26_JAN_GROUP_6**")

    # --- THEME ENGINE ---
    bg, txt, btn = ("#111", "white", "#E50914") if theme == "Netflix Dark" else ("white", "black", "#0078ff")
    st.markdown(f"<style>.stApp {{ background: {bg}; color: {txt}; }} .stButton>button {{ background: {btn}; color: white; border-radius: 20px; }}</style>", unsafe_allow_html=True)

    # --- TOP SECTION: PERSISTENT RECOMMENDATIONS ---
    st.title("🎬 AI Movie Recommender")
    if st.session_state.recs:
        st.subheader(f"Recommendations based on '{st.session_state.last_choice}'")
        for r in range(2):
            cols = st.columns(3)
            for i in range(3):
                item = st.session_state.recs[r*3 + i]
                with cols[i]:
                    poster, platforms = get_movie_details(item['id'])
                    st.image(poster, use_container_width=True)
                    st.markdown(f"<div style='text-align:center;'><b>{item['title']}</b></div>", unsafe_allow_html=True)
                    with st.expander("ℹ️ Details & Watch"):
                        st.caption(f"📺 Watch on: {', '.join(platforms)}")
                        st.link_button("🎥 View on TMDB", f"https://www.themoviedb.org/movie/{item['id']}", use_container_width=True)
        st.markdown("---")

    # --- BOTTOM SECTION: SELECTION & EXPORT ---
    st.subheader("🔍 Find Your Next Movie")
    col_in, col_luck = st.columns([3, 1])
    with col_in:
        selected_movie = st.selectbox('Select a movie you liked:', movies['title'].values)
    with col_luck:
        st.write("") 
        if st.button('🎲 Surprise Me', use_container_width=True):
            selected_movie = random.choice(movies['title'].values)
            st.toast(f"Picked: {selected_movie}")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button('❤️ Save to Favorites', use_container_width=True):
            m = movies[movies['title'] == selected_movie].iloc[0]
            db.collection('favorites').document(st.session_state.u_id).collection('movies').document(str(m.movie_id)).set({'title': selected_movie, 'id': int(m.movie_id)})
            st.toast("Saved!")
    with c2:
        if st.button('✨ Generate Recommendations', use_container_width=True):
            idx = movies[movies['title'] == selected_movie].index[0]
            dist = sorted(list(enumerate(similarity[idx])), reverse=True, key=lambda x: x[1])
            st.session_state.recs = [{'id': int(movies.iloc[dist[i][0]].movie_id), 'title': movies.iloc[dist[i][0]].title} for i in range(1, 7)]
            st.session_state.last_choice = selected_movie
            st.rerun()
    with c3:
        if st.session_state.recs:
            csv = convert_recs_to_csv(st.session_state.recs)
            st.download_button("📥 Export List (CSV)", csv, f"Recs_{st.session_state.last_choice}.csv", "text/csv", use_container_width=True)
        else:
            st.button("📥 Export List", disabled=True, use_container_width=True)