import streamlit as st
import pickle
import pandas as pd
import requests
import firebase_admin
from firebase_admin import credentials, auth, firestore
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
if 'u_name' not in st.session_state:
    st.session_state.u_name = "User"

# --- 4. ASSET & API HELPERS ---
TMDB_API_KEY = "9a17b2be2c5c6caeba84998a102f7cde"

def get_movie_details(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}"
    try:
        res = requests.get(url, timeout=10).json()
        poster_path = res.get('poster_path')
        if poster_path:
            return "https://image.tmdb.org/t/p/w500" + poster_path
        return "https://via.placeholder.com/500x750?text=No+Poster"
    except:
        return "https://via.placeholder.com/500x750?text=Error"

def get_trending_movies():
    url = f"https://api.themoviedb.org/3/trending/movie/week?api_key={TMDB_API_KEY}"
    return requests.get(url).json().get('results', [])[:6]

def get_popular_ghana():
    url = f"https://api.themoviedb.org/3/movie/popular?api_key={TMDB_API_KEY}&region=GH"
    return requests.get(url).json().get('results', [])[:6]

# --- 5. AUTHENTICATION UI (UPDATED FOR FIRST-CLICK FIX) ---
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
            status_container = st.empty()
            
            if st.button("SIGN IN", use_container_width=True):
                with st.spinner("Authenticating..."):
                    firebase_web_api_key = "AIzaSyCyZ9aCtchLZyejKzTRjbSDnNp8uu9o1RI"
                    auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_web_api_key}"
                    try:
                        res = requests.post(auth_url, json={"email": e, "password": p, "returnSecureToken": True}, timeout=20)
                        if res.status_code == 200:
                            user_data = res.json()
                            # Immediate retrieval of correct display name
                            user_record = auth.get_user(user_data['localId'])
                            st.session_state.user_auth = True
                            st.session_state.u_id = user_data['localId']
                            st.session_state.u_name = user_record.display_name if user_record.display_name else e.split('@')[0]
                            st.rerun()
                        else:
                            status_container.error("Invalid credentials. Please try again.")
                    except:
                        status_container.warning("Connection lag. Streamlining login...")
                        st.rerun()

        with t2:
            ne, nu, np = st.text_input("Email", key="s_e"), st.text_input("Username", key="s_u"), st.text_input("Password", type="password", key="s_p")
            if st.button("CREATE ACCOUNT", use_container_width=True):
                try:
                    auth.create_user(email=ne, password=np, display_name=nu)
                    st.success(f"Account Created for {nu}! Please Login.")
                except Exception as ex: st.error(ex)

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
        except: st.markdown("<h1 style='text-align: center;'>🎬</h1>", unsafe_allow_html=True)
        
        st.markdown("<h2 style='text-align: center; color: #E50914;'>GROUP 6 SOLUTION</h2>", unsafe_allow_html=True)
        st.write(f"Welcome back, **{st.session_state.u_name}**")
        st.markdown("---")
        
        theme = st.selectbox("App Theme:", ["Netflix Dark", "Classic Light", "Ocean Blue"])
        rec_mode = st.radio("AI Engine Mode:", ["Content-Based", "Collaborative"])
        
        st.markdown("---")
        if st.button("🚪 Sign Out", use_container_width=True):
            st.session_state.user_auth = False
            st.rerun()

    # --- THEME ENGINE ---
    themes = {"Netflix Dark": ("#111", "white", "#E50914"), "Classic Light": ("white", "black", "#0078ff"), "Ocean Blue": ("#001f3f", "white", "#0074D9")}
    bg, txt, btn = themes[theme]
    st.markdown(f"<style>.stApp {{ background: {bg}; color: {txt}; }} .stButton>button {{ background: {btn}; color: white; border-radius: 20px; }}</style>", unsafe_allow_html=True)

    # --- MAIN CONTENT TABS (5 TABS) ---
    tab_discovery, tab_genres, tab_countries, tab_ai, tab_watchlist = st.tabs([
        "🔥 Discovery", "🎭 Genres", "🌍 Countries", "🔍 AI Recommender", "🔖 Watchlist"
    ])

    with tab_discovery:
        st.title("Top Global Picks")
        st.subheader("Popular in Ghana 🇬🇭")
        gh_movies = get_popular_ghana()
        cols_gh = st.columns(6)
        for i, m in enumerate(gh_movies):
            with cols_gh[i]:
                st.image(f"https://image.tmdb.org/t/p/w500{m['poster_path']}")
                st.caption(f"**{m['title']}**")
        
        st.markdown("---")
        st.subheader("Trending This Week")
        tr_movies = get_trending_movies()
        cols_tr = st.columns(6)
        for i, m in enumerate(tr_movies):
            with cols_tr[i]:
                st.image(f"https://image.tmdb.org/t/p/w500{m['poster_path']}")
                st.caption(f"**{m['title']}**")

    with tab_genres:
        st.title("Browse by Genre")
        g_list = sorted(movies['genre_label'].unique().tolist())
        sel_g = st.selectbox("Select Genre:", g_list)
        
        filtered_g = movies[movies['genre_label'] == sel_g].head(24)
        cols_g = st.columns(4)
        for i, m in enumerate(filtered_g.to_dict('records')):
            with cols_g[i % 4]:
                poster = get_movie_details(m['movie_id'])
                st.image(poster, use_container_width=True)
                st.caption(f"**{m['title']}**")
                if st.button("Analyze", key=f"gen_{m['movie_id']}"):
                    st.session_state.last_choice = m['title']
                    st.toast(f"Locked on: {m['title']}")

    with tab_countries:
        st.title("World Cinema")
        c_list = sorted(movies['country_label'].unique().tolist())
        sel_c = st.selectbox("Select Origin Country:", c_list)
        
        filtered_c = movies[movies['country_label'] == sel_c].head(24)
        cols_c = st.columns(4)
        for i, m in enumerate(filtered_c.to_dict('records')):
            with cols_c[i % 4]:
                poster = get_movie_details(m['movie_id'])
                st.image(poster, use_container_width=True)
                st.caption(f"**{m['title']}**")
                if st.button("Analyze", key=f"con_{m['movie_id']}"):
                    st.session_state.last_choice = m['title']
                    st.toast(f"Locked on: {m['title']}")

    with tab_ai:
        st.title("AI Search & Recommendations")
        movie_list = movies['title'].values
        default_ix = 0
        if st.session_state.last_choice in movie_list:
            default_ix = int(movies[movies['title'] == st.session_state.last_choice].index[0])
            
        selected_movie = st.selectbox('Pick a movie:', movie_list, index=default_ix)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button('✨ Generate Match', use_container_width=True):
                if rec_mode == "Content-Based":
                    idx = movies[movies['title'] == selected_movie].index[0]
                    dist = sorted(list(enumerate(similarity[idx])), reverse=True, key=lambda x: x[1])
                    st.session_state.recs = [{'id': int(movies.iloc[dist[i][0]].movie_id), 'title': movies.iloc[dist[i][0]].title} for i in range(1, 7)]
                else:
                    st.session_state.recs = [{'id': int(movies.sample().movie_id.iloc[0]), 'title': movies.sample().title.iloc[0]} for _ in range(6)]
                st.session_state.last_choice = selected_movie
                st.rerun()
        
        with c2:
            if st.button('❤️ Save to Favorites', use_container_width=True):
                m_data = movies[movies['title'] == selected_movie].iloc[0]
                db.collection('favorites').document(st.session_state.u_id).collection('movies').document(str(m_data.movie_id)).set({'title': selected_movie, 'id': int(m_data.movie_id)})
                st.toast("Saved!")

        with c3:
            if st.session_state.recs:
                csv = pd.DataFrame(st.session_state.recs).to_csv(index=False).encode('utf-8')
                st.download_button("📥 Export Recommendations", csv, "cine_recs.csv", "text/csv", use_container_width=True)

        if st.session_state.recs:
            st.markdown(f"### Results for '{st.session_state.last_choice}'")
            cols_ai = st.columns(3)
            for i, item in enumerate(st.session_state.recs):
                with cols_ai[i % 3]:
                    poster = get_movie_details(item['id'])
                    st.image(poster)
                    st.markdown(f"**{item['title']}**")
                    if st.button("Add to Watchlist", key=f"ai_{item['id']}"):
                        db.collection('watchlists').document(st.session_state.u_id).collection('movies').document(str(item['id'])).set({'title': item['title'], 'id': item['id']})
                        st.toast("Added!")

    with tab_watchlist:
        st.title("Your Personal Watchlist")
        w_list = db.collection('watchlists').document(st.session_state.u_id).collection('movies').stream()
        for movie in w_list:
            m = movie.to_dict()
            col_w1, col_w2 = st.columns([5, 1])
            with col_w1: st.write(f"🎬 **{m['title']}**")
            with col_w2:
                if st.button("🗑️", key=f"del_{m['id']}"):
                    db.collection('watchlists').document(st.session_state.u_id).collection('movies').document(str(m['id'])).delete()
                    st.rerun()

    st.markdown("---")
    st.caption("Developed by: ML26_JAN_GROUP_6")