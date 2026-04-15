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
            status_box = st.empty()
            if st.button("SIGN IN", use_container_width=True):
                with st.spinner("Connecting..."):
                    fb_key = "AIzaSyCyZ9aCtchLZyejKzTRjbSDnNp8uu9o1RI"
                    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={fb_key}"
                    try:
                        res = requests.post(url, json={"email": e, "password": p, "returnSecureToken": True}, timeout=20)
                        if res.status_code == 200:
                            data = res.json()
                            user = auth.get_user(data['localId'])
                            st.session_state.update({
                                "user_auth": True,
                                "u_id": data['localId'],
                                "u_name": user.display_name if user.display_name else e.split('@')[0]
                            })
                            st.rerun()
                        else: status_box.error("Invalid credentials.")
                    except: st.rerun() 

        with t2:
            ne, nu, np = st.text_input("Email", key="s_e"), st.text_input("Username", key="s_u"), st.text_input("Password", type="password", key="s_p")
            if st.button("CREATE ACCOUNT", use_container_width=True):
                try:
                    auth.create_user(email=ne, password=np, display_name=nu)
                    st.success(f"Account Created for {nu}! Please Login.")
                except Exception as ex: st.error(ex)

# --- 6. DATA LOADING (INCLUDES SVD MODEL) ---
@st.cache_resource(show_spinner=False)
def load_data():
    movies = pd.DataFrame(pickle.load(open('movie_dict.pkl', 'rb')))
    similarity = pickle.load(open('similarity.pkl', 'rb'))
    
    # Load the Collaborative SVD Model
    try:
        svd_model = pickle.load(open('svd_model.pkl', 'rb'))
    except FileNotFoundError:
        svd_model = None
        st.warning("Collaborative model (svd_model.pkl) not found. Using Fallback mode.")

    if 'id' in movies.columns:
        movies.rename(columns={'id': 'movie_id'}, inplace=True)
    return movies, similarity, svd_model

movies, similarity, svd_model = load_data()

# --- 7. MAIN APP LOGIC ---
if not st.session_state.user_auth:
    login_screen()
else:
    with st.sidebar:
        try: st.image("logo.jpg", width=250)
        except: st.markdown("<h1 style='text-align: center;'>🎬</h1>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #E50914;'>GROUP 6 SOLUTION</h2>", unsafe_allow_html=True)
        st.write(f"Welcome, **{st.session_state.u_name}**")
        st.markdown("---")
        
        # UI SETTINGS
        theme = st.selectbox("App Theme:", ["Netflix Dark", "Classic Light", "Ocean Blue"])
        rec_mode = st.radio("AI Strategy:", ["Content-Based", "Collaborative"])
        st.markdown("---")

        # FAVORITES SECTION
        st.subheader("❤️ Favorites")
        favs = db.collection('favorites').document(st.session_state.u_id).collection('movies').limit(5).stream()
        has_favs = False
        for f in favs:
            has_favs = True
            st.caption(f"⭐ {f.to_dict()['title']}")
        if not has_favs:
            st.caption("No favorites yet.")
        st.markdown("---")

        if st.button("🚪 Sign Out", use_container_width=True):
            st.session_state.user_auth = False
            st.rerun()

    # Theme Engine
    themes = {"Netflix Dark": ("#111", "white", "#E50914"), "Classic Light": ("white", "black", "#0078ff"), "Ocean Blue": ("#001f3f", "white", "#0074D9")}
    bg, txt, btn = themes[theme]
    st.markdown(f"<style>.stApp {{ background: {bg}; color: {txt}; }} .stButton>button {{ background: {btn}; color: white; border-radius: 20px; }}</style>", unsafe_allow_html=True)

    tab_discovery, tab_genres, tab_countries, tab_ai, tab_watchlist = st.tabs([
        "🔥 Discovery", "🎭 Genres", "🌍 Countries", "🔍 AI Recommender", "🔖 Watchlist"
    ])

    with tab_discovery:
        st.title("Popular & Trending")
        gh_movies = get_popular_ghana()
        cols_gh = st.columns(6)
        for i, m in enumerate(gh_movies):
            with cols_gh[i]:
                st.image(f"https://image.tmdb.org/t/p/w500{m['poster_path']}")
                st.caption(f"**{m['title']}**")
        st.markdown("---")
        tr_movies = get_trending_movies()
        cols_tr = st.columns(6)
        for i, m in enumerate(tr_movies):
            with cols_tr[i]:
                st.image(f"https://image.tmdb.org/t/p/w500{m['poster_path']}")
                st.caption(f"**{m['title']}**")

    with tab_genres:
        st.title("Explore Genres")
        g_list = sorted(movies['genre_label'].unique().tolist())
        sel_g = st.selectbox("Pick Genre:", g_list)
        filtered_g = movies[movies['genre_label'] == sel_g].head(24)
        cols_g = st.columns(4)
        for i, m in enumerate(filtered_g.to_dict('records')):
            with cols_g[i % 4]:
                m_id = m.get('movie_id') or m.get('id')
                st.image(get_movie_details(m_id))
                st.caption(m['title'])
                if st.button("Analyze", key=f"g_{m_id}"):
                    st.session_state.last_choice = m['title']
                    st.toast(f"Locked onto {m['title']}!")

    with tab_countries:
        st.title("World Cinema")
        c_list = sorted(movies['country_label'].unique().tolist())
        sel_c = st.selectbox("Pick Country:", c_list)
        filtered_c = movies[movies['country_label'] == sel_c].head(24)
        cols_c = st.columns(4)
        for i, m in enumerate(filtered_c.to_dict('records')):
            with cols_c[i % 4]:
                m_id = m.get('movie_id') or m.get('id')
                st.image(get_movie_details(m_id))
                st.caption(m['title'])
                if st.button("Analyze", key=f"c_{m_id}"):
                    st.session_state.last_choice = m['title']
                    st.toast(f"Locked onto {m['title']}!")

    with tab_ai:
        st.title("AI Recommender")
        movie_titles = movies['title'].tolist()
        try: d_idx = movie_titles.index(st.session_state.last_choice)
        except: d_idx = 0
        selected_movie = st.selectbox('Choose movie reference:', movie_titles, index=d_idx)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button('✨ Generate Top 5 Match', use_container_width=True):
                # STRATEGY 1: CONTENT-BASED
                if rec_mode == "Content-Based":
                    idx = movies[movies['title'] == selected_movie].index[0]
                    dist = sorted(list(enumerate(similarity[idx])), reverse=True, key=lambda x: x[1])
                    st.session_state.recs = [{'id': int(movies.iloc[dist[i][0]].movie_id), 'title': movies.iloc[dist[i][0]].title} for i in range(1, 6)]
                
                # STRATEGY 2: COLLABORATIVE (Using SVD)
                else:
                    if svd_model:
                        # We predict ratings for 50 random movies for this User ID and show the highest predicted titles
                        # Mapping the Firebase UID to an integer User ID for SVD
                        numerical_uid = hash(st.session_state.u_id) % 1000
                        movie_pool = movies.sample(50)
                        preds = []
                        for _, row in movie_pool.iterrows():
                            est = svd_model.predict(numerical_uid, row['movie_id']).est
                            preds.append({'id': row['movie_id'], 'title': row['title'], 'est': est})
                        preds.sort(key=lambda x: x['est'], reverse=True)
                        st.session_state.recs = [{'id': int(p['id']), 'title': p['title']} for p in preds[:5]]
                    else:
                        # Random Fallback if pkl is missing
                        st.session_state.recs = [{'id': int(movies.sample().movie_id.iloc[0]), 'title': movies.sample().title.iloc[0]} for _ in range(5)]
                
                st.session_state.last_choice = selected_movie
                st.rerun()
        
        with c2:
            if st.button('❤️ Favorite', use_container_width=True):
                m_data = movies[movies['title'] == selected_movie].iloc[0]
                db.collection('favorites').document(st.session_state.u_id).collection('movies').document(str(m_data.movie_id)).set({'title': selected_movie, 'id': int(m_data.movie_id)})
                st.toast("Saved to Favorites!")
        
        with c3:
            if st.session_state.recs:
                csv = pd.DataFrame(st.session_state.recs).to_csv(index=False).encode('utf-8')
                st.download_button("📥 Export List", csv, "top_5_recs.csv", "text/csv", use_container_width=True)

        if st.session_state.recs:
            st.markdown(f"### Results for you ({rec_mode})")
            cols_ai = st.columns(5)
            for i, item in enumerate(st.session_state.recs):
                with cols_ai[i]:
                    st.image(get_movie_details(item['id']))
                    st.markdown(f"**{item['title']}**")
                    if st.button("Add to Watch", key=f"ai_{item['id']}"):
                        db.collection('watchlists').document(st.session_state.u_id).collection('movies').document(str(item['id'])).set({'title': item['title'], 'id': item['id']})
                        st.toast("Added to Watchlist!")

    with tab_watchlist:
        st.title("My Watchlist")
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