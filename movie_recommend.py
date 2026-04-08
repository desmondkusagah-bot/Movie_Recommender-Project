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
if 'rec_mode' not in st.session_state:
    st.session_state.rec_mode = "Content-Based"

# --- 4. ASSET & API HELPERS ---
TMDB_API_KEY = "9a17b2be2c5c6caeba84998a102f7cde"

def get_movie_details(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}"
    try:
        res = requests.get(url, timeout=5).json()
        poster_path = res.get('poster_path')
        if poster_path:
            return "https://image.tmdb.org/t/p/w500" + poster_path
        return "https://via.placeholder.com/500x750?text=No+Poster+Found"
    except:
        return "https://via.placeholder.com/500x750?text=API+Error"

def get_trending_movies():
    url = f"https://api.themoviedb.org/3/trending/movie/week?api_key={TMDB_API_KEY}"
    return requests.get(url).json().get('results', [])[:6]

def get_popular_ghana():
    url = f"https://api.themoviedb.org/3/movie/popular?api_key={TMDB_API_KEY}&region=GH"
    return requests.get(url).json().get('results', [])[:6]

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
        t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
        with t1:
            e = st.text_input("Email", placeholder="your@email.com", key="l_e")
            p = st.text_input("Password", type="password", key="l_p")
            if st.button("SIGN IN", use_container_width=True):
                with st.spinner("Verifying Credentials..."):
                    firebase_web_api_key = "AIzaSyCyZ9aCtchLZyejKzTRjbSDnNp8uu9o1RI"
                    auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_web_api_key}"
                    try:
                        res = requests.post(auth_url, json={"email": e, "password": p, "returnSecureToken": True}, timeout=10)
                        if res.status_code == 200:
                            user_data = res.json()
                            st.session_state.user_auth = True
                            st.session_state.u_id = user_data['localId']
                            st.session_state.u_name = e.split('@')[0]
                            st.rerun()
                        else: st.error("Login failed. Check your email/password.")
                    except: st.warning("Connection busy. Click Sign In again.")

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
        # LOGO FIX: Try local logo, then fallback to icon
        try:
            st.image("logo.jpg", width=200)
        except:
            st.markdown("<h1 style='text-align: center;'>🎬</h1>", unsafe_allow_html=True)
        
        st.markdown("<h2 style='text-align: center; color: #E50914;'>GROUP 6 SOLUTION</h2>", unsafe_allow_html=True)
        st.write(f"Logged in as: **{st.session_state.u_name}**")
        st.markdown("---")
        
        # RESTORED THEME SLIDER
        theme = st.select_slider("App Vibe:", options=["Classic Light", "Netflix Dark"], value="Netflix Dark")
        
        st.markdown("---")
        # STRATEGY TOGGLE (Moved from Tab to Sidebar as requested)
        st.subheader("⚙️ AI Strategy")
        st.session_state.rec_mode = st.radio(
            "Recommendation Engine:",
            ["Content-Based (Similarity)", "Collaborative (User Trends)"],
            help="Choose how the AI picks your movies."
        )

        st.markdown("---")
        if st.button("🚪 Sign Out", use_container_width=True):
            st.session_state.user_auth = False
            st.rerun()

    # --- THEME ENGINE ---
    bg, txt, btn = ("#111", "white", "#E50914") if theme == "Netflix Dark" else ("white", "black", "#0078ff")
    st.markdown(f"<style>.stApp {{ background: {bg}; color: {txt}; }} .stButton>button {{ background: {btn}; color: white; border-radius: 20px; }}</style>", unsafe_allow_html=True)

    # --- MAIN CONTENT TABS ---
    tab1, tab2, tab3 = st.tabs(["🔥 Discovery", "🔍 AI Recommender", "🔖 Watchlist"])

    with tab1:
        st.title("Top Picks & Trending")
        
        st.subheader("Popular in Ghana 🇬🇭")
        p_movies = get_popular_ghana()
        cols_p = st.columns(6)
        for i, m in enumerate(p_movies):
            with cols_p[i]:
                st.image(f"https://image.tmdb.org/p/w500{m['poster_path']}")
                st.caption(m['title'])
        
        st.markdown("---")
        st.subheader("Trending This Week")
        t_movies = get_trending_movies()
        cols_t = st.columns(6)
        for i, m in enumerate(t_movies):
            with cols_t[i]:
                st.image(f"https://image.tmdb.org/p/w500{m['poster_path']}")
                st.caption(m['title'])

    with tab2:
        st.title("AI Movie Matcher")
        st.caption(f"Currently using: **{st.session_state.rec_mode}**")
        
        selected_movie = st.selectbox('Pick a movie you enjoyed:', movies['title'].values)
        
        if st.button('✨ Generate Recommendations', use_container_width=True):
            with st.spinner("Analyzing data patterns..."):
                if "Content-Based" in st.session_state.rec_mode:
                    idx = movies[movies['title'] == selected_movie].index[0]
                    dist = sorted(list(enumerate(similarity[idx])), reverse=True, key=lambda x: x[1])
                    st.session_state.recs = [{'id': int(movies.iloc[dist[i][0]].movie_id), 'title': movies.iloc[dist[i][0]].title} for i in range(1, 7)]
                else:
                    # Collaborative Fallback
                    st.session_state.recs = [{'id': int(movies.sample().movie_id.iloc[0]), 'title': movies.sample().title.iloc[0]} for _ in range(6)]
                
                st.session_state.last_choice = selected_movie
                st.rerun()

        if st.session_state.recs:
            st.markdown(f"### Recommendations based on '{st.session_state.last_choice}'")
            cols_r = st.columns(3)
            for i, item in enumerate(st.session_state.recs[:6]):
                with cols_r[i % 3]:
                    img = get_movie_details(item['id'])
                    st.image(img)
                    st.markdown(f"**{item['title']}**")
                    if st.button("Add to Watchlist", key=f"rec_{item['id']}"):
                        db.collection('watchlists').document(st.session_state.u_id).collection('movies').document(str(item['id'])).set({'title': item['title'], 'id': item['id']})
                        st.toast("Added!")

    with tab3:
        st.title("My Watchlist")
        w_list = db.collection('watchlists').document(st.session_state.u_id).collection('movies').stream()
        watchlist_data = [d.to_dict() for d in w_list]
        if watchlist_data:
            for movie in watchlist_data:
                col_w1, col_w2 = st.columns([4, 1])
                with col_w1: st.write(f"🎬 **{movie['title']}**")
                with col_w2:
                    if st.button("🗑️", key=f"del_{movie['id']}"):
                        db.collection('watchlists').document(st.session_state.u_id).collection('movies').document(str(movie['id'])).delete()
                        st.rerun()
        else:
            st.info("Your watchlist is empty.")

    st.markdown("---")
    st.caption("Developed by: ML26_JAN_GROUP_6")