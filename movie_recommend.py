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

def load_lottieurl(url):
    try:
        r = requests.get(url)
        return r.json() if r.status_code == 200 else None
    except: return None

lottie_movie = load_lottieurl("https://lottie.host/8287340b-715d-4f11-9257-2e2197170a49/X9XjNfG3W3.json")

def get_movie_details(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&append_to_response=watch/providers"
    try:
        res = requests.get(url).json()
        poster_path = res.get('poster_path')
        poster = "https://image.tmdb.org/t/p/w500" + poster_path if poster_path else "https://via.placeholder.com/500x750"
        providers = res.get('watch/providers', {}).get('results', {}).get('GH', {}).get('flatrate', [])
        p_names = [p['provider_name'] for p in providers] if providers else ["Rental/Cinema Only"]
        return poster, p_names
    except:
        return "https://via.placeholder.com/500x750", ["Data Unavailable"]

def get_trending_movies():
    url = f"https://api.themoviedb.org/3/trending/movie/week?api_key={TMDB_API_KEY}"
    return requests.get(url).json().get('results', [])[:6]

def get_popular_ghana():
    url = f"https://api.themoviedb.org/3/movie/popular?api_key={TMDB_API_KEY}&region=GH"
    return requests.get(url).json().get('results', [])[:6]

def get_movies_by_filter(genre_id=None, country_code=None):
    url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&sort_by=popularity.desc"
    if genre_id: url += f"&with_genres={genre_id}"
    if country_code: url += f"&with_origin_country={country_code}"
    return requests.get(url).json().get('results', [])[:12]

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
                firebase_web_api_key = "AIzaSyCyZ9aCtchLZyejKzTRjbSDnNp8uu9o1RI"
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
                    else: st.error("Login Failed. Check credentials.")
                except: st.error("An error occurred.")
        
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
        st.markdown("<h1 style='text-align: center; color: #E50914;'>GROUP 6</h1>", unsafe_allow_html=True)
        st.write(f"Logged in as: **{st.session_state.u_name}**")
        
        # SEARCH FILTERS
        st.markdown("---")
        st.subheader("🎯 Discover by Filter")
        genre_map = {"All": None, "Action": 28, "Comedy": 35, "Drama": 18, "Horror": 27, "Romance": 10749, "Sci-Fi": 878}
        sel_genre = st.selectbox("Genre:", list(genre_map.keys()))
        country_map = {"Global": None, "Ghana 🇬🇭": "GH", "Nigeria 🇳🇬": "NG", "USA 🇺🇸": "US", "UK 🇬🇧": "GB"}
        sel_country = st.selectbox("Country:", list(country_map.keys()))
        
        if st.button("Apply Filters", use_container_width=True):
            st.session_state.filter_results = get_movies_by_filter(genre_map[sel_genre], country_map[sel_country])

        st.markdown("---")
        if st.button("🚪 Sign Out", use_container_width=True):
            st.session_state.user_auth = False
            st.rerun()

    # --- MAIN CONTENT TABS ---
    tab_discovery, tab_ai, tab_watchlist = st.tabs(["🔥 Discovery", "🔍 AI Recommender", "🔖 My Watchlist"])

    with tab_discovery:
        st.title("What's Trending")
        
        # Display Filter Results if applied
        if st.session_state.filter_results:
            st.subheader("Filter Results")
            cols = st.columns(6)
            for i, m in enumerate(st.session_state.filter_results[:6]):
                with cols[i]:
                    st.image(f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m['poster_path'] else "https://via.placeholder.com/500x750")
                    st.caption(m['title'])
                    if st.button("🔖", key=f"f_{m['id']}"):
                        db.collection('watchlists').document(st.session_state.u_id).collection('movies').document(str(m['id'])).set({'title': m['title'], 'id': m['id']})
                        st.toast("Added to Watchlist!")
            st.markdown("---")

        # Trending Row
        st.subheader("Trending This Week")
        t_movies = get_trending_movies()
        cols_t = st.columns(6)
        for i, m in enumerate(t_movies):
            with cols_t[i]:
                st.image(f"https://image.tmdb.org/t/p/w500{m['poster_path']}")
                st.caption(m['title'])

        # Popular in GH Row
        st.subheader("Popular in Ghana 🇬🇭")
        p_movies = get_popular_ghana()
        cols_p = st.columns(6)
        for i, m in enumerate(p_movies):
            with cols_p[i]:
                st.image(f"https://image.tmdb.org/t/p/w500{m['poster_path']}")
                st.caption(m['title'])

    with tab_ai:
        st.title("AI Search Engine")
        selected_movie = st.selectbox('Select a movie you liked:', movies['title'].values)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button('✨ Generate Recommendations', use_container_width=True):
                idx = movies[movies['title'] == selected_movie].index[0]
                dist = sorted(list(enumerate(similarity[idx])), reverse=True, key=lambda x: x[1])
                st.session_state.recs = [{'id': int(movies.iloc[dist[i][0]].movie_id), 'title': movies.iloc[dist[i][0]].title} for i in range(1, 7)]
                st.session_state.last_choice = selected_movie
                st.rerun()
        with col2:
            if st.button('❤️ Add to Favorites', use_container_width=True):
                m = movies[movies['title'] == selected_movie].iloc[0]
                db.collection('favorites').document(st.session_state.u_id).collection('movies').document(str(m.movie_id)).set({'title': selected_movie, 'id': int(m.movie_id)})
                st.toast("Saved to Favorites!")

        if st.session_state.recs:
            st.markdown("---")
            st.subheader(f"Based on {st.session_state.last_choice}")
            cols_r = st.columns(3)
            for i in range(3):
                item = st.session_state.recs[i]
                with cols_r[i]:
                    poster, platforms = get_movie_details(item['id'])
                    st.image(poster)
                    st.markdown(f"**{item['title']}**")
                    if st.button("Add to Watchlist", key=f"r_{item['id']}"):
                        db.collection('watchlists').document(st.session_state.u_id).collection('movies').document(str(item['id'])).set({'title': item['title'], 'id': item['id']})
                        st.toast("Added!")

    with tab_watchlist:
        st.title("My Watchlist")
        w_list = db.collection('watchlists').document(st.session_state.u_id).collection('movies').stream()
        
        watchlist_data = [d.to_dict() for d in w_list]
        if watchlist_data:
            for movie in watchlist_data:
                col_w1, col_w2 = st.columns([4, 1])
                with col_w1:
                    st.write(f"🎬 **{movie['title']}**")
                with col_w2:
                    if st.button("🗑️", key=f"del_{movie['id']}"):
                        db.collection('watchlists').document(st.session_state.u_id).collection('movies').document(str(movie['id'])).delete()
                        st.rerun()
        else:
            st.info("Your watchlist is empty. Add movies from the Discovery or AI tabs!")

    # Footer
    st.markdown("---")
    st.caption("Developed by: ML26_JAN_GROUP_6")