import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

# --- Page Configuration & Theming ---
st.set_page_config(
    page_title="F1 Metrix | Data & Analysis",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="auto"
)

def apply_custom_css(css_file):
    """
    Loads a CSS file and injects a custom Google Fonts link.
    """
    # 1. Add the Google Fonts link directly to the HTML head
    st.markdown(
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400..900&display=swap">',
        unsafe_allow_html=True
    )

    # 2. Load the local CSS file
    try:
        with open(css_file) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"CSS file '{css_file}' not found.")

# Apply custom CSS and set Plotly default theme
apply_custom_css('styles.css') # Uncomment if you have a styles.css file
px.defaults.template = "plotly_dark"


# --- Database Connection ---
@st.cache_resource
def get_db_engine():
    """Returns a SQLAlchemy engine for the F1 results database."""
    return create_engine('sqlite:///model_results.db')

engine = get_db_engine()


# --- Data Loading Functions ---
@st.cache_data
def load_data(table_name):
    """Generic function to load a table from the database."""
    try:
        df = pd.read_sql_table(table_name, engine)
        if 'forename' in df.columns and 'surname' in df.columns:
            df['full_name'] = df['forename'] + ' ' + df['surname']
        return df
    except Exception as e:
        st.error(f"Error loading table '{table_name}': {e}. Make sure 'model_results.db' is in the same directory.")
        return pd.DataFrame()

# --- Blog Helper Functions ---
@st.cache_data
def get_blog_posts(folder_path="blog_posts"):
    """Scans a folder for markdown files and returns a sorted list of posts."""
    if not os.path.exists(folder_path):
        return {}
    
    posts = {}
    for filename in os.listdir(folder_path):
        if filename.endswith(".md"):
            try:
                # Expects format: YYYY-MM-DD-your-post-title.md
                date_str = "-".join(filename.split("-")[:3])
                post_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                # Create a clean title from the rest of the filename
                title_slug = "-".join(filename.split('.')[0].split('-')[3:])
                title = title_slug.replace('-', ' ').title()
                
                posts[filename] = {
                    'title': title,
                    'date': post_date,
                    'path': os.path.join(folder_path, filename)
                }
            except Exception as e:
                print(f"Skipping file with incorrect format: {filename} ({e})")
                continue
    
    # Sort posts by date, newest first
    sorted_posts = sorted(posts.values(), key=lambda x: x['date'], reverse=True)
    return sorted_posts

def read_markdown_file(markdown_file):
    """Reads and returns the content of a markdown file."""
    with open(markdown_file, 'r', encoding='utf-8') as f:
        return f.read()

# --- Main App ---
st.title("F1 Metrix - A Formula 1 Data Analytics Blog")

# --- Tab Implementation ---
blog_tab, dataviz_tab = st.tabs(["📝 Blog Posts", "📊 Data Visualizations"])

# --- Blog Tab ---
with blog_tab:
    st.header("Articles & Analysis")
    
    blog_posts = get_blog_posts()

    if not blog_posts:
        st.warning("No blog posts found!")
        st.info("To add posts, create a folder named `blog_posts` and add markdown files to it. Use the filename format `YYYY-MM-DD-your-title.md`.")
    else:
        # Create a mapping from "Date - Title" to the post dictionary
        post_options = {f"{post['date'].strftime('%Y-%m-%d')} - {post['title']}": post for post in blog_posts}
        
        st.subheader("Post Timeline")
        selected_post_key = st.selectbox("Select a post to read from the timeline:", options=list(post_options.keys()))
        
        st.divider()
        
        if selected_post_key:
            selected_post = post_options[selected_post_key]
            st.markdown(f"# {selected_post['title']}")
            st.caption(f"Published on: {selected_post['date'].strftime('%B %d, %Y')}")
            
            post_content = read_markdown_file(selected_post['path'])
            st.markdown(post_content, unsafe_allow_html=True)

# --- Data Visualizations Tab ---
with dataviz_tab:
    st.header("Interactive Data Explorers")
    st.info("Explore the model's findings through these interactive charts and tables.")

    with st.expander("🏆 All-Time Driver Rankings", expanded=True):
        st.markdown("Drivers are ranked by their `u0_skill_lower_bound`, a conservative estimate of their baseline skill. This rewards consistent, high-level performance over a career.")
        df_all_time = load_data("driver_all_time_u0_ranking_conservative")
        if not df_all_time.empty:
            top_n = st.slider("Select number of top drivers:", min_value=10, max_value=100, value=25, key="all_time_slider")
            df_display = df_all_time.head(top_n).sort_values(by="u0_skill_lower_bound", ascending=True)
            fig = px.bar(df_display, x="u0_skill_lower_bound", y="full_name", orientation='h', title=f"Top {top_n} All-Time F1 Drivers", labels={"u0_skill_lower_bound": "Conservative Skill Score", "full_name": "Driver"}, hover_data=["race_count", "u0_skill_mean"])
            fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=800, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

    with st.expander("📅 Yearly 'Pure Skill' Rankings"):
        st.markdown("Explore the model's estimate of driver skill for any given season, accounting for age and experience.")
        df_yearly = load_data("driver_yearly_pure_skill_rankings")
        if not df_yearly.empty:
            years = sorted(df_yearly['year'].unique(), reverse=True)
            selected_year = st.selectbox("Select a Year:", options=years)
            df_filtered = df_yearly[df_yearly['year'] == selected_year].sort_values(by="yearly_rank")
            fig = px.bar(df_filtered.head(20).sort_values(by='yearly_pure_skill_score', ascending=True), x="yearly_pure_skill_score", y="full_name", orientation='h', title=f"Top Driver Skill Rankings for {selected_year}", labels={"yearly_pure_skill_score": "Yearly Pure Skill Score", "full_name": "Driver"}, hover_data=["yearly_rank"])
            fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=600, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_filtered)

    with st.expander("🔮 2025 Teammate Head-to-Head Predictions"):
        st.markdown("This table shows the model's predictions for potential 2025 teammate battles. The probabilities reflect which driver is more likely to have a higher 'pure skill' score.")
        df_h2h = load_data("predictions_h2h_2025")
        if not df_h2h.empty:
            df_h2h['constructor_id'] = df_h2h['constructor_id'].str.replace('-', ' ').str.title()
            for _, row in df_h2h.iterrows():
                st.subheader(f"🏎️ {row['constructor_id']}")
                d1_prob_str = row['prob_d1_outperforms']
                d2_prob_str = row['prob_d2_outperforms']
                try:
                    d1_prob_float = float(d1_prob_str.strip('%')) / 100
                except:
                    d1_prob_float = 0.5
                col1, col2, col3 = st.columns([2, 1, 2])
                with col1: st.metric(label=row['driver1_name'], value=d1_prob_str)
                with col2: st.markdown("<h4 style='text-align: center; color: grey; margin-top: 25px;'>vs</h4>", unsafe_allow_html=True)
                with col3: st.metric(label=row['driver2_name'], value=d2_prob_str)
                st.progress(d1_prob_float)
                st.divider()

    with st.expander("⚙️ Model Internals"):
        st.markdown("This table shows the raw summary output from the Bayesian model, which is useful for diagnosing the model's performance and understanding parameter distributions.")
        df_summary = load_data("model_summary")
        if not df_summary.empty:
            st.dataframe(df_summary, height=500)