import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime
import re
# import textwrap # New import for text wrapping

import streamlit as st


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
    st.markdown(
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400..900&display=swap">',
        unsafe_allow_html=True
    )
    try:
        with open(css_file) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"CSS file '{css_file}' not found.")

apply_custom_css('styles.css')
px.defaults.template = "plotly_dark"

# --- Database Connection ---
@st.cache_resource
def get_db_engine():
    """Returns a SQLAlchemy engine for the F1 results database."""
    # Using 'model_results.db' as specified in your query examples
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

# --- NEW: Specific Data Loading for Red Bull Post ---
@st.cache_data
def get_all_time_skill_data(_engine):
    """Fetches all-time conservative and mean skill rankings for specific drivers."""
    query = text("""
        SELECT forename, surname, u0_skill_mean, u0_skill_lower_bound, race_count 
        FROM driver_all_time_u0_ranking_conservative 
        WHERE driverid IN ('sergio-perez', 'liam-lawson', 'yuki-tsunoda', 'isack-hadjar', 'max-verstappen')
        ORDER BY u0_skill_lower_bound DESC;
    """)
    with _engine.connect() as conn:
        df = pd.read_sql(query, conn)
    if not df.empty:
        df['full_name'] = df['forename'] + ' ' + df['surname']
    return df

@st.cache_data
def get_yearly_skill_data(_engine):
    """Fetches yearly skill scores for Pérez, Tsunoda and Lawson."""
    query = text("""
        SELECT year, forename, surname, yearly_pure_skill_score, yearly_rank 
        FROM driver_yearly_pure_skill_rankings 
        WHERE driverid IN ('sergio-perez', 'yuki-tsunoda', 'liam-lawson') AND year >= 2021
        ORDER BY surname, year;
    """)
    with _engine.connect() as conn:
        df = pd.read_sql(query, conn)
    if not df.empty:
        df['full_name'] = df['forename'] + ' ' + df['surname']
    return df

@st.cache_data
def get_poe_data(_engine):
    """
    Fetches the average performance over expectation for specific drivers for each
    year between 2021 and 2024.
    """
    query = text("""
        SELECT 
            forename, 
            surname, 
            year, 
            AVG(performance_over_expectation) as average_poe, 
            COUNT(raceid) as race_count 
        FROM 
            driver_performance_over_expectation 
        WHERE 
            driverid IN ('sergio-perez', 'liam-lawson', 'yuki-tsunoda', 'isack-hadjar', 'max-verstappen') 
            AND year BETWEEN 2021 AND 2025
        GROUP BY 
            forename, surname, year
        ORDER BY 
            surname, year;
    """)
    with _engine.connect() as conn:
        df = pd.read_sql(query, conn)
    if not df.empty:
        df['full_name'] = df['forename'] + ' ' + df['surname']
    return df


@st.cache_data
def get_latest_year_poe_data(_engine):
    """
    Fetches Performance Over Expectation data for all drivers for the most
    recent year available in the database.
    """
    # This query finds the latest year and fetches all race data for that year
    query = text("""
        SELECT 
            raceid,
            forename, 
            surname,
            performance_over_expectation
        FROM 
            driver_performance_over_expectation 
        WHERE 
            year = (SELECT MAX(year) FROM driver_performance_over_expectation);
    """)
    with _engine.connect() as conn:
        df = pd.read_sql(query, conn)
    if not df.empty:
        df['full_name'] = df['forename'] + ' ' + df['surname']
    return df


# 2. --- REBUILT Plotting Function ---
# This function is now designed to create a line chart showing trends over time.
def plot_yearly_poe_trend(df):
    """
    Generates a line chart showing the yearly trend of 'Performance Over Expectation'.
    """
    # Create the line chart with markers for each data point (each year)

    df = df.sort_values('year')

    fig = px.line(df, 
                  x='year', 
                  y='average_poe', 
                  color='full_name',  # Creates a separate line for each driver
                  title="Yearly Trend: Performance Over Expectation (POE)",
                  labels={
                      "year": "Season", 
                      "average_poe": "Average POE (Higher is Better)", 
                      "full_name": "Driver"
                  },
                  markers=True, # Adds a dot for each year's data point
                  hover_data=['race_count']) # Show race count on hover
    
    # Add a crucial horizontal line at y=0. Points above are over-performing, below are under-performing.
    fig.add_hline(y=0, line_dash="dash", line_color="grey", 
                  annotation_text="Expectation Baseline", annotation_position="bottom right")
    
    # Ensure the x-axis ticks are set for each year and not as a continuous float (e.g., no "2021.5")
    fig.update_xaxes(type='category')
    
    # Apply standard dark theme styling
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    
    return fig

def plot_all_time_skill(df):
    """
    Generates a stacked bar chart showing the conservative (lower bound) and mean
    all-time skill estimates.
    """
    # Sort the dataframe by the mean skill for a clear visual hierarchy in the plot
    df = df.sort_values(by="u0_skill_mean", ascending=True)

    # Calculate the difference between the mean and the lower bound.
    # This will be the second (lighter) part of our stacked bar.
    df['skill_upside'] = df['u0_skill_mean'] - df['u0_skill_lower_bound']

    fig = go.Figure()

    # Add the base of the bar: The Conservative Skill Score
    fig.add_trace(go.Bar(
        y=df['full_name'],
        x=df['u0_skill_lower_bound'],
        name='Conservative Skill (Lower Bound)',
        orientation='h',
        marker_color="#000000",  # A distinct blue color
        hovertemplate=(
            "<b>%{y}</b><br>" +
            "Conservative Skill: %{x:.3f}<br>" +
            "Mean Skill: %{customdata[0]:.3f}<br>" +
            "Race Count: %{customdata[1]}" +
            "<extra></extra>" # Hides the trace name on hover
        ),
        customdata=df[['u0_skill_mean', 'race_count']]
    ))

    # Add the top part of the bar: The 'upside' from the lower bound to the mean
    fig.add_trace(go.Bar(
        y=df['full_name'],
        x=df['skill_upside'],
        name='Potential to Mean',
        orientation='h',
        marker_color='#aec7e8',  # A lighter shade of blue
        hovertemplate=(
            "<b>%{y}</b><br>" +
            "Upside to Mean: +%{x:.3f}<br>" +
            "Total Mean Skill: %{customdata[0]:.3f}" +
            "<extra></extra>"
        ),
        customdata=df[['u0_skill_mean']]
    ))

    # Update layout for stacked bars and better readability
    fig.update_layout(
        barmode='stack',
        title="All-Time Driver Skill: Conservative vs. Mean Estimate",
        xaxis_title="Driver Skill Score",
        yaxis_title=None, # Remove y-axis title for a cleaner look
        legend_title="Skill Metric",
        legend=dict(yanchor="bottom", y=0.01, xanchor="left", x=0.99),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=10, t=50, b=20), # Adjust margins
        height=400
    )
    
    return fig

def plot_yearly_skill_comparison(df):
    """Generates the yearly skill comparison line chart."""
    fig = px.line(df, 
                  x='year', 
                  y='yearly_pure_skill_score', 
                  color='full_name',
                  title="Yearly Performance Trajectory: Pérez vs. Tsunoda",
                  labels={"year": "Season", "yearly_pure_skill_score": "Yearly Pure Skill Score", "full_name": "Driver"},
                  markers=True)
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

def plot_latest_year_poe_interactive(df):
    """
    Generates a TALL, interactive line chart showing the race-by-race POE trend
    for a user-selected list of drivers.
    """
    if df.empty:
        return go.Figure()

    # --- ORDERING FIX ---
    # The dataframe is now pre-sorted by raceid before plotting.
    df = df.sort_values('raceid')

    # Create a cleaner 'Race 1', 'Race 2', etc. label for the x-axis
    race_ids = df['raceid'].unique() # Already sorted
    race_number_map = {race_id: f"Race {i+1}" for i, race_id in enumerate(race_ids)}
    df['race_label'] = df['raceid'].map(race_number_map)

    latest_year = 2024 
    
    fig = px.line(
        df, 
        x='race_label', 
        y='performance_over_expectation',
        color='full_name',
        markers=True,
        title=f"Race-by-Race Performance Over Expectation ({latest_year})",
        labels={
            "race_label": "Race of the Season",
            "performance_over_expectation": "Performance Over Expectation (POE)",
            "full_name": "Driver"
        },
        hover_data={"full_name": True, "performance_over_expectation": ':.3f'}
    )

    fig.add_hline(y=0, line_dash="dash", line_color="grey")

    # --- TALLER & CLEANER LAYOUT FIX ---
    fig.update_layout(
        height=700,  # Makes the plot much taller
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)',
        legend_title_text='Selected Drivers', # Add a title to the legend
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.4, # Position legend further down to accommodate more names
            xanchor="center",
            x=0.5
        )
    )
    
    return fig

def render_red_bull_post(_engine):
    """Loads data and creates all plots for the Red Bull post."""
    plots = {}
    
    # All-Time Skill Plot
    df_all_time = get_all_time_skill_data(_engine)
    if not df_all_time.empty:
        plots['all_time_skill'] = plot_all_time_skill(df_all_time)

    # Yearly Skill Plot
    df_yearly = get_yearly_skill_data(_engine)
    if not df_yearly.empty:
        plots['yearly_skill_comparison'] = plot_yearly_skill_comparison(df_yearly)
        
    # POE Plot
    df_poe = get_poe_data(_engine)
    if not df_poe.empty:
        plots['yearly_poe_trend'] = plot_yearly_poe_trend(df_poe)
        
    return plots


def render_latest_poe_post(engine):
    """
    Loads data and creates an INTERACTIVE plot for the latest year's POE review,
    allowing the user to select which drivers to display.
    """
    plots = {}
    
    # We still load ALL the data for the year initially
    df_latest_poe = get_latest_year_poe_data(engine)
    
    if not df_latest_poe.empty:
        # --- INTERACTIVITY WIDGET ---
        st.markdown("##### 📈 Chart Controls")
        st.info("The chart is interactive! Use the dropdown below to select the drivers you want to compare.")

        # Get a list of all drivers from the data, sorted alphabetically
        all_drivers = sorted(df_latest_poe['full_name'].unique())

        # Set a sensible default list of drivers to show initially
        default_drivers = [
            'Max Verstappen', 'Lando Norris', 'Charles Leclerc', 
            'Oscar Piastri', 'Alexander Albon'
        ]
        # Ensure defaults are actually in the data to prevent errors
        default_drivers = [d for d in default_drivers if d in all_drivers]

        # The multi-select widget
        selected_drivers = st.multiselect(
            "Select drivers to display on the chart:",
            options=all_drivers,
            default=default_drivers
        )
        
        # --- Filter the DataFrame based on user selection ---
        if selected_drivers:
            filtered_df = df_latest_poe[df_latest_poe['full_name'].isin(selected_drivers)]
            
            # Generate the plot using ONLY the filtered data
            plots['latest_year_poe_plot'] = plot_latest_year_poe_interactive(filtered_df)
        else:
            # If no drivers are selected, create an empty plot
            st.warning("Please select at least one driver to display the chart.")
            plots['latest_year_poe_plot'] = go.Figure().update_layout(
                height=700,
                paper_bgcolor='rgba(0,0,0,0)', 
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
    return plots



# --- NEW: Dictionary mapping posts to their renderer functions ---
POST_RENDERERS = {
    "2025-10-11-the-second-seat.md": render_red_bull_post,
    "2025-10-22-performance-ranking-after-us-grand-prix.md": render_latest_poe_post
}

# --- NEW: Generic function to render markdown with plot placeholders ---
def render_markdown_with_plots(content, plots):
    """Splits markdown by plot placeholders and injects Plotly charts."""
    # Regex to find all placeholders <!-- PLOT:name -->
    placeholders = re.findall(r'<!-- PLOT:(\w+) -->', content)
    
    # Split the content by the full placeholder tags
    parts = re.split(r'<!-- PLOT:\w+ -->', content)

    for i, part in enumerate(parts):
        st.markdown(part, unsafe_allow_html=True)
        if i < len(placeholders):
            plot_name = placeholders[i]
            if plot_name in plots:
                st.plotly_chart(plots[plot_name], use_container_width=True)
            else:
                st.warning(f"Warning: Plot '{plot_name}' not found.")

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
                date_str = "-".join(filename.split("-")[:3])
                post_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                title_slug = "-".join(filename.split('.')[0].split('-')[3:])
                title = title_slug.replace('-', ' ').title()
                posts[filename] = {
                    'title': title,
                    'date': post_date,
                    'path': os.path.join(folder_path, filename),
                    'filename': filename # Store filename for renderer mapping
                }
            except Exception as e:
                print(f"Skipping file with incorrect format: {filename} ({e})")
                continue
    sorted_posts = sorted(posts.values(), key=lambda x: x['date'], reverse=True)
    return sorted_posts

def read_markdown_file(markdown_file):
    """Reads and returns the content of a markdown file."""
    with open(markdown_file, 'r', encoding='utf-8') as f:
        return f.read()

# --- Main App ---
st.title("F1 Metrix")
st.header("A Formula 1 Data Analytics Blog")

blog_tab, dataviz_tab = st.tabs(["📝 Blog Posts", "📊 Data Visualizations"])

# --- Blog Tab ---
with blog_tab:
    st.header("Articles & Analysis")
    blog_posts = get_blog_posts()
    if not blog_posts:
        st.warning("No blog posts found!")
        st.info("To add posts, create a folder named `blog_posts` and add markdown files to it. Use the filename format `YYYY-MM-DD-your-title.md`.")
    else:
        post_options = {f"{post['date'].strftime('%Y-%m-%d')} - {post['title']}": post for post in blog_posts}
        st.subheader("Post Timeline")
        selected_post_key = st.selectbox("Select a post to read from the timeline:", options=list(post_options.keys()))
        st.divider()
        if selected_post_key:
            selected_post = post_options[selected_post_key]
            st.markdown(f"# {selected_post['title']}")
            st.caption(f"Published on: {selected_post['date'].strftime('%B %d, %Y')}")
            post_content = read_markdown_file(selected_post['path'])
            
            # --- MODIFIED SECTION: Intelligent Post Rendering ---
            post_filename = selected_post['filename']
            if post_filename in POST_RENDERERS:
                # This post has a special renderer function
                renderer_func = POST_RENDERERS[post_filename]
                plots = renderer_func(engine)
                render_markdown_with_plots(post_content, plots)
            else:
                # Default behavior for simple markdown posts
                st.markdown(post_content, unsafe_allow_html=True)
            # --- END OF MODIFIED SECTION ---

# --- Data Visualizations Tab (Your existing code is great, no changes needed here) ---
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