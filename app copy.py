import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
import plotly.graph_objects as go

# --- Page Configuration & Theming ---
# This should be the first Streamlit command in your script.
st.set_page_config(
    page_title="F1 Driver Performance Analysis",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

def apply_custom_css(css_file):
    with open(css_file) as f:
        css = f.read()
    st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)

# NEW: Function to inject custom CSS for theming
# def set_custom_theme():
#     """
#     Injects custom CSS to set background color, font, and title colors.
#     """
#     custom_css = """
#     @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400..900&display=swap');

#     h1, h2, h3, h4, h5, h6 {
#         font-family: 'Orbitron', sans-serif;
#         color: #FF4B4B; /* Streamlit's default red color */
#     }
#     """
#     st.markdown(f'<style>{custom_css}</style>', unsafe_allow_html=True)

# # NEW: Apply the custom theme
# set_custom_theme()
apply_custom_css('styles.css')

# NEW: Set the default theme for all Plotly charts
px.defaults.template = "plotly_dark"

# --- Database Connection ---
# Use st.cache_resource to only create the connection once.
@st.cache_resource
def get_db_engine():
    """Returns a SQLAlchemy engine for the F1 results database."""
    # UPDATED: Changed the database filename
    return create_engine('sqlite:///model_results.db')

engine = get_db_engine()

# --- Data Loading Functions ---
# Use st.cache_data to load data and cache the result.
@st.cache_data
def load_data(table_name):
    """Generic function to load a table from the database."""
    try:
        df = pd.read_sql_table(table_name, engine)
        if 'forename' in df.columns and 'surname' in df.columns:
            df['full_name'] = df['forename'] + ' ' + df['surname']
        return df
    except Exception as e:
        # UPDATED: Changed the error message to reflect the new filename
        st.error(f"Error loading table '{table_name}': {e}. Make sure 'model_results.db' is in the same directory.")
        return pd.DataFrame()

# --- Main App ---

# --- Sidebar ---
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    [
        "📖 The Model Explained",
        "🏆 All-Time Rankings",
        "📅 Yearly Skill Rankings",
        "🏁 Race Performance Explorer",
        "🔮 2025 H2H Predictions",
        "⚙️ Model Internals"
    ]
)

# --- Page 1: The "Blog Post" Introduction ---
if page == "📖 The Model Explained":
    st.title("F1 Metrix - A Formula 1 data analytics blog")

    st.markdown("""
    Welcome to an interactive exploration of Formula 1 driver performance. The data you see here is the output of a sophisticated statistical model designed to answer a timeless question in motorsport:

    **"How much of a driver's success is due to their raw talent, and how much is due to the car they drive?"**

    This is a notoriously difficult question. A great driver in a slow car might finish 10th, while a good driver in a dominant car wins the race. Simply looking at finishing positions isn't enough. Our model attempts to untangle this complex relationship.

    ### What is "Performance Over Expectation"?
    This is the core metric for single-race performance. For every race a driver participates in, the model calculates an **expected performance level** based on factors like:
    - The historical strength of their team.
    - Their grid starting position.
    - The overall competitiveness of that specific race.
    - The driver's age and experience level.

    "Performance Over Expectation" is the difference between their actual race result (a metric called `rankit_points`) and this calculated expectation.
    - A **positive score** means the driver significantly **outperformed** what was expected of them. Think of a stunning drive from 15th on the grid to a points finish.
    - A **negative score** means they **underperformed** relative to the model's baseline.

    ### How are Skill Rankings Calculated?
    The model uses a technique called **Bayesian hierarchical modeling**. In simple terms, it learns a "base skill level" (`u0_skill`) for every driver across their entire career, while also learning how that skill might change with age and experience.

    - **Yearly Rankings:** Combine the driver's base skill with the model's estimate for their age and experience in a given year to produce a "Pure Skill Score" for that season.
    - **All-Time Rankings:** Ranks drivers by a *conservative estimate* of their base skill. We use the 10% lower bound of the model's estimate, which means we are 90% sure their true skill is at least this high. This method favors drivers who performed at a high level consistently over many races.

    Use the navigation in the sidebar to explore these findings interactively!
    """)

# --- Page 2: All-Time Rankings ---
elif page == "🏆 All-Time Rankings":
    st.title("🏆 All-Time Driver Rankings")
    st.markdown("Drivers are ranked by their `u0_skill_lower_bound`, a conservative estimate of their baseline skill. This rewards consistent, high-level performance over a career.")

    df = load_data("driver_all_time_u0_ranking_conservative")
    if not df.empty:
        top_n = st.slider("Select number of top drivers to display:", min_value=10, max_value=100, value=25)
        
        df_display = df.head(top_n).sort_values(by="u0_skill_lower_bound", ascending=True)

        fig = px.bar(
            df_display,
            x="u0_skill_lower_bound",
            y="full_name",
            orientation='h',
            title=f"Top {top_n} All-Time F1 Drivers (Conservative Skill Estimate)",
            labels={"u0_skill_lower_bound": "Conservative Skill Score (Higher is Better)", "full_name": "Driver"},
            hover_data=["race_count", "u0_skill_mean"]
        )
        fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=800, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("View Raw Data"):
            st.dataframe(df.head(top_n))

# --- Page 3: Yearly Rankings ---
elif page == "📅 Yearly Skill Rankings":
    st.title("📅 Yearly 'Pure Skill' Rankings")
    st.markdown("Explore the model's estimate of driver skill for any given season, accounting for age and experience.")

    df_yearly = load_data("driver_yearly_pure_skill_rankings")
    if not df_yearly.empty:
        years = sorted(df_yearly['year'].unique(), reverse=True)
        selected_year = st.selectbox("Select a Year:", options=years)

        df_filtered = df_yearly[df_yearly['year'] == selected_year].sort_values(by="yearly_rank")
        
        fig = px.bar(
            df_filtered.head(20).sort_values(by='yearly_pure_skill_score', ascending=True),
            x="yearly_pure_skill_score",
            y="full_name",
            orientation='h',
            title=f"Top Driver Skill Rankings for {selected_year}",
            labels={"yearly_pure_skill_score": "Yearly Pure Skill Score (Higher is Better)", "full_name": "Driver"},
            hover_data=["yearly_rank"]
        )
        fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=600, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

        with st.expander(f"View Full Rankings for {selected_year}"):
            st.dataframe(df_filtered)

# --- Page 4: Race Performance Explorer ---
elif page == " race Performance Explorer":
    st.title(" race Performance Explorer")
    st.markdown("Analyze individual race performances. Use the filters to find the greatest over- and under-performances in F1 history.")

    df_perf = load_data("driver_performance_over_expectation")
    if not df_perf.empty:
        drivers = sorted(df_perf['full_name'].unique())
        selected_drivers = st.multiselect("Select Driver(s):", options=drivers)
        
        min_year, max_year = int(df_perf['year'].min()), int(df_perf['year'].max())
        year_range = st.slider("Select Year Range:", min_year, max_year, (min_year, max_year))

        df_filtered = df_perf[
            (df_perf['year'] >= year_range[0]) & (df_perf['year'] <= year_range[1])
        ]
        if selected_drivers:
            df_filtered = df_filtered[df_filtered['full_name'].isin(selected_drivers)]

        if df_filtered.empty:
            st.warning("No data found for the selected filters.")
        else:
            st.subheader("Top 10 Overperformances (Selected Filters)")
            st.dataframe(df_filtered.sort_values(by="performance_over_expectation", ascending=False).head(10))

            st.subheader("Interactive Data Table")
            st.dataframe(df_filtered)

# --- Page 5: 2025 Predictions ---
elif page == "🔮 2025 H2H Predictions":
    st.title("🔮 2025 Teammate Head-to-Head Predictions")
    st.markdown("This table shows the model's predictions for potential 2025 teammate battles. The probabilities reflect which driver is more likely to have a higher 'pure skill' score in a typical race scenario.")
    
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
            with col1:
                st.metric(label=row['driver1_name'], value=d1_prob_str)
            with col2:
                st.markdown("<h4 style='text-align: center; color: grey; margin-top: 25px;'>vs</h4>", unsafe_allow_html=True)
            with col3:
                st.metric(label=row['driver2_name'], value=d2_prob_str)
            
            # Custom progress bar color
            st.markdown(f"""
                <style>
                    .st-d8 {{
                        background-color: #FF4B4B;
                    }}
                </style>
                """, unsafe_allow_html=True)
            st.progress(d1_prob_float)
            
            with st.expander("See Prediction Details"):
                st.write(f"**Average Performance Gap:** {row['avg_performance_gap']}")
                st.write(f"**94% Credible Interval for Gap:** {row['gap_94_hdi']}")
                st.caption(f"Full prediction string: {row['prediction_for']}")
            st.divider()

# --- Page 6: Model Internals ---
elif page == "⚙️ Model Internals":
    st.title("⚙️ Model Internals")
    st.markdown("""
    This table shows the raw summary output from the Bayesian model, generated by the `arviz` library. It's useful for diagnosing the model's performance and understanding the posterior distributions of the parameters.
    - **`mean`**: The average estimated value for the parameter.
    - **`sd`**: The standard deviation of the posterior distribution (a measure of uncertainty).
    - **`hdi_3%` & `hdi_97%`**: The 94% Highest Density Interval.
    - **`r_hat`**: Should be very close to 1.0. A value > 1.01 indicates a potential problem with model convergence.
    - **`ess_bulk` & `ess_tail`**: Effective Sample Size. Higher is better.
    """)
    df_summary = load_data("model_summary")
    if not df_summary.empty:
        st.dataframe(df_summary, height=500)