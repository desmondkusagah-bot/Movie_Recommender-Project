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
if 'filter_results' not in st.session_state:
    st.session_state.filter_results = []

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
                with st.spinner("Authenticating..."):
                    firebase_web_api_key = "AIzaSyCyZ9aCtchLZyejKzTRjbSDnNp8uu9o1RI"
                    auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_web_api_key}"
                    try:
                        payload = {"email": e, "password": p, "returnSecureToken": True}
                        res = requests.post(auth_url, json=payload, timeout=10)
                        if res.status_code == 200:
                            user_data = res.json()
                            user_info = auth.get_user(user_data['localId'])
                            st.session_state.user_auth = True
                            st.session_state.u_id = user_data['localId']
                            st.session_state.u_name = user_info.display_name if user_info.display_name else e.split('@')[0]
                            st.rerun()
                        else: st.error("Login failed. Please try again.")
                    except: st.warning("Network lag. Please click Sign In again.")

# --- 6. DATA LOADING & COLUMN CLEANING ---
@st.cache_resource(show_spinner=False)
def load_data():
    movies_raw = pd.DataFrame(pickle.load(open('movie_dict.pkl', 'rb')))
    similarity = pickle.load(open('similarity.pkl', 'rb'))
    
    # Force clean column names to lowercase and strip spaces
    movies_raw.columns = [c.lower().strip() for c in movies_raw.columns]
    
    # Mapping fix for 'genres' and 'country'
    mapping = {}
    for c in movies_raw.columns:
        if c in ['genre', 'movie_genres', 'tags']: mapping[c] = 'genres'
        if c in ['origin_country', 'countries', 'location']: mapping[c] = 'country'
    movies_raw.rename(columns=mapping, inplace=True)
    
    # Ensure they exist
    if 'genres' not in movies_raw.columns: movies_raw['genres'] = "Unknown"
    if 'country' not in movies_raw.columns: movies_raw['country'] = "Global"
    
    return movies_raw, similarity

movies, similarity = load_data()

# --- 7. MAIN APP LOGIC ---
if not st.session_state.user_auth:
    login_screen()
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("<h1 style='text-align: center; color: #E50914;'>GROUP 6 SOLUTION</h1>", unsafe_allow_html=True)
        st.write(f"User: **{st.session_state.u_name}**")
        st.markdown("---")
        theme = st.select_slider("App Vibe:", options=["Classic Light", "Netflix Dark"], value="Netflix Dark")
        
        st.markdown("---")
        st.subheader("🎯 Dataset Explorer")

        # FIX: Extracting actual genres for the list
        all_genres = movies['genres'].explode().unique() if isinstance(movies['genres'].iloc[0], list) else movies['genres'].unique()
        genre_list = sorted([str(g) for g in all_genres if str(g) != 'nan'])
        sel_genre = st.selectbox("Select Genre:", ["All"] + genre_list)

        # FIX: Extracting actual countries for the list
        country_list = sorted([str(c) for c in movies['country'].unique() if str(c) != 'nan'])
        sel_country = st.selectbox("Select Country:", ["All"] + country_list)
        
        if st.button("Filter Dataset", use_container_width=True):
            filtered = movies.copy()
            if sel_genre != "All":
                filtered = filtered[filtered['genres'].apply(lambda x: sel_genre in x if isinstance(x, list) else sel_genre in str(x))]
            if sel_country != "All":
                filtered = filtered[filtered['country'].astype(str) == sel_country]
            st.session_state.filter_results = filtered.head(12).to_dict('records')

        st.markdown("---")
        if st.button("Sign Out", use_container_width=True):
            st.session_state.user_auth = False
            st.rerun()

    # --- THEME & TABS ---
    bg, txt, btn = ("#111", "white", "#E50914") if theme == "Netflix Dark" else ("white", "black", "#0078ff")
    st.markdown(f"<style>.stApp {{ background: {bg}; color: {txt}; }} .stButton>button {{ background: {btn}; color: white; border-radius: 20px; }}</style>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🔥 Discovery", "🔍 AI Search", "🔖 Watchlist"])

    with tab1:
        if st.session_state.filter_results:
            st.subheader("Explorer Results")
            cols = st.columns(4)
            for i, m in enumerate(st.session_state.filter_results):
                with cols[i % 4]:
                    # Use the cleaned details helper
                    img = get_movie_details(m.get('movie_id') or m.get('id'))
                    st.image(img, use_container_width=True)
                    st.caption(m['title'])
                    if st.button("Analyze", key=f"f_{i}"):
                        st.session_state.last_choice = m['title']
                        st.rerun()
        
        st.subheader("Popular in Ghana 🇬🇭")
        p_movies = get_popular_ghana()
        cols_p = st.columns(6)
        for i, m in enumerate(p_movies):
            with cols_p[i]:
                st.image(f"https://image.tmdb.org/t/p/w500{m['poster_path']}")
                st.caption(m['title'])

    with tab2:
        st.title("AI Search Engine")
        selected_movie = st.selectbox('Select a movie you liked:', movies['title'].values)
        if st.button('✨ Generate Recommendations', use_container_width=True):
            idx = movies[movies['title'] == selected_movie].index[0]
            dist = sorted(list(enumerate(similarity[idx])), reverse=True, key=lambda x: x[1])
            st.session_state.recs = [{'id': int(movies.iloc[dist[i][0]].get('movie_id', 0)), 'title': movies.iloc[dist[i][0]].title} for i in range(1, 7)]
            st.session_state.last_choice = selected_movie
            st.rerun()

        if st.session_state.recs:
            st.markdown("---")
            cols_r = st.columns(3)
            for i, item in enumerate(st.session_state.recs[:6]):
                with cols_r[i % 3]:
                    img = get_movie_details(item['id'])
                    st.image(img)
                    st.markdown(f"**{item['title']}**")

    with tab3:
        st.title("My Watchlist")
        # Watchlist logic...

    st.markdown("---")
    st.caption("Developed by: ML26_JAN_GROUP_6")