import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# Page config 
st.set_page_config(page_title="Recipe Finder | Hoos Hungry?", layout="centered", initial_sidebar_state="collapsed")

# Session state defaults 
if "recipe_filter" not in st.session_state:
    st.session_state.recipe_filter = "All"
if "cal_range" not in st.session_state:
    st.session_state.cal_range = (200, 750)
if "search_query" not in st.session_state:
    st.session_state.search_query = ""
if "sort_sel" not in st.session_state:
    st.session_state.sort_sel = "Rating ↓"
if "show_advanced" not in st.session_state:
    st.session_state.show_advanced = False
# Dependent dropdown state
if "selected_category_dep" not in st.session_state:
    st.session_state.selected_category_dep = "All"
if "selected_recipe_dep" not in st.session_state:
    st.session_state.selected_recipe_dep = None

# CSS 
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;900&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [data-testid="stAppViewContainer"] {
    background: #b8ccb5 !important;
    font-family: 'Nunito', sans-serif !important;
}
[data-testid="stAppViewContainer"] > .main { background: #b8ccb5 !important; padding-bottom: 60px !important; }
#MainMenu, footer { visibility: hidden; }
[data-testid="stToolbar"] { background: #7a9e7e !important; }
header[data-testid="stHeader"] { background: #7a9e7e !important; }
[data-testid="stDecoration"] { display: none; }
[data-testid="stSidebarNav"] { display: block !important; }
[data-testid="stSidebarCollapsedControl"] { display: block !important; }
[data-testid="stCaptionContainer"] p { color: black !important; }

.section-header {
    background: #6b6b6b; color: #fff; padding: 8px 14px;
    font-size: 1rem; font-weight: 700; border-radius: 6px 6px 0 0; margin-top: 16px;
}
.recipe-grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px;
    background: #d4e0d2; padding: 8px; border-radius: 0 0 8px 8px;
}
.recipe-card { border-radius: 6px; overflow: hidden; background: #8fa98c; }
.recipe-img-placeholder {
    width: 100%; aspect-ratio: 1; background: #7a9e7e;
    display: flex; align-items: center; justify-content: center; font-size: 1.8rem;
}
.recipe-label {
    background: rgba(0,0,0,0.55); color: #fff; font-size: 0.6rem;
    font-weight: 700; padding: 4px 5px; text-align: center;
}

div[data-testid="stButton"] > button {
    background: #6b6b6b !important; color: white !important;
    border: none !important; border-radius: 8px !important;
    font-family: 'Nunito', sans-serif !important; font-weight: 700 !important;
}
div[data-testid="stButton"] > button:hover { background: #4a7a50 !important; }
</style>
""", unsafe_allow_html=True)

SPOONACULAR_SITE = "https://api.spoonacular.com"

def get_api_key():
    try:
        return st.secrets["SPOONACULAR_KEY"]
    except (KeyError, FileNotFoundError):
        return None

@st.cache_data(ttl=3600)
def search_recipes(query, meal_type, max_ready_time, number=9):
    api_key = get_api_key()
    if not api_key:
        return None, "no_key"
    
    params = {
        "apiKey" : api_key,
        "query" : query,
        "number": number,
        "addRecipeInformation": True,
        "fillIngredients" : False,
    }
    if meal_type != "All":
        params["type"] = meal_type.lower()
    if max_ready_time < 120:
        params['maxReadyTime'] = max_ready_time

    try:
        response = requests.get(f"{SPOONACULAR_SITE}/recipes/complexSearch",
                                params=params, timeout=10)
        if response.status_code == 401:
            return None, "unauthorized"
        elif response.status_code == 404:
            return None, "not_found"
        elif response.status_code == 429:
            return None, "rate_limit"
        elif response.status_code >= 500:
            return None, "server_error"
        elif response.status_code != 200:
            return None, f"unexpected_error_{response.status_code}"
        
        data = response.json()
        results = data.get("results", [])

        if len(results) == 0:
            return None, "empty"  
        return results, "ok"
    
    except requests.exceptions.Timeout:
        return None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, "connection_error"
    except requests.exceptions.RequestException as e:
        return None, f"request_error: {e}"
    except ValueError:
        return None, "parse_error"

# Cached recipe data 
@st.cache_data
def load_recipe_data():
    """Load and cache the full recipe dataset."""
    data = {
        "Name": [
            "Butter Chickpeas", "Mushroom Spinach Pasta", "Burrito Bowl",
            "Fettucine Alfredo", "Caesar Wrap", "Samosas",
            "Cauliflower Rice & Zucchini", "Mozzarella Pesto Sandwich",
            "Avocado Toast", "Greek Salad", "Lentil Soup", "Veggie Stir Fry"
        ],
        "Category": [
            "Dinner", "Dinner", "Lunch", "Dinner", "Lunch", "Breakfast",
            "Lunch", "Lunch", "Breakfast", "Lunch", "Dinner", "Dinner"
        ],
        "Calories": [450, 520, 610, 720, 480, 310, 290, 540, 320, 210, 380, 330],
        "Prep Time (min)": [30, 25, 20, 35, 10, 40, 20, 10, 5, 10, 45, 25],
        "Rating": [4.5, 4.2, 4.7, 4.1, 4.8, 4.3, 3.9, 4.4, 4.6, 4.0, 4.2, 4.5],
        "Emoji": ["🍛", "🍝", "🥙", "🍜", "🌯", "🥟", "🥗", "🥪", "🥑", "🥗", "🍲", "🥦"],
    }
    return pd.DataFrame(data)

df = load_recipe_data()

# Callback: Reset all filters (on_click)
# on_click callback is necessary here because we need to reset numerous pieces of session state atomically before the next render 
# a plain if-block after the button press would fire a frame too late and leave stale widget values
def reset_all_filters():
    st.session_state.recipe_filter = "All"
    st.session_state.recipe_search = ""        # key= lets us clear the widget value
    st.session_state.sort_sel = "Rating ↓"
    st.session_state.cal_range_slider = (200, 750)
    st.session_state.show_advanced = False
    st.session_state.selected_category_dep = "All"
    st.session_state.selected_recipe_dep = None

# Callback: on_change for dependent dropdown
# on_change is needed here to clear the child dropdown selection whenever the parent category changes 
# if we used a plain if-block the stale child value would remain in session state and produce a misleading selection
def on_category_change():
    st.session_state.selected_recipe_dep = None

# Page title 
st.title("🔍 Recipe Finder")

# Widget 1: search text input
# key="recipe_search" — needed so reset_all_filters() can clear it by name
search_query = st.text_input(
    "", placeholder="Search recipes or keywords…",
    key="recipe_search",  # key required: reset callback clears this widget by key
    label_visibility="collapsed"
)

api_results = None
api_status = None

if search_query:
    api_results, api_status = search_recipes(
        search_query,
        st.session_state.recipe_filter,
        120
    )

    if api_status == "ok":
        st.write(f"✅ API call worked. Found {len(api_results)} recipe(s) from Spoonacular.")
    elif api_status == "no_key":
        st.error("No API key found in Streamlit secrets.")
    elif api_status == "unauthorized":
        st.error("Unauthorized: your Spoonacular API key may be invalid.")
    elif api_status == "rate_limit":
        st.error("Rate limit reached for the Spoonacular API.")
    elif api_status == "not_found":
        st.warning("No matching recipes found from the API.")
    else:
        st.error(f"API call failed: {api_status}")

# Layout primitive: st.columns for category filter buttons + sort
col1, col2, col3, col4, col5 = st.columns(5)
for col, label in zip([col1, col2, col3, col4], ["All", "Breakfast", "Lunch", "Dinner"]):
    with col:
        if st.button(label, key=f"cat_{label}"):
            st.session_state.recipe_filter = label
            st.rerun()

with col5:
    # Widget 2: sort selectbox
    sort_by = st.selectbox("Sort", ["Rating ↓", "Calories ↑", "Prep Time ↑"],
                           key="sort_sel", label_visibility="collapsed")

st.caption(f"Active filter: **{st.session_state.recipe_filter}**")

# Layout primitive: st.columns for category filter buttons + sort
col1, col2, col3, col4, col5 = st.columns(5)
for col, label in zip([col1, col2, col3, col4], ["All", "Breakfast", "Lunch", "Dinner"]):
    with col:
        if st.button(label, key=f"cat_{label}"):  # key required: unique per button to avoid collisions
            st.session_state.recipe_filter = label
            st.rerun()

with col5:
    # Widget 2: sort selectbox
    sort_by = st.selectbox(
        "Sort", ["Rating ↓", "Calories ↑", "Prep Time ↑"],
        key="sort_sel",  # key required: reset callback restores this widget by key
        label_visibility="collapsed"
    )

# Reset button using on_click callback
col_reset, _ = st.columns([1, 3])
with col_reset:
    st.button("🔄 Reset Filters", key="reset_btn", on_click=reset_all_filters)

st.caption(f"Active filter: **{st.session_state.recipe_filter}**")

# Apply filters 
filtered = df.copy()
if st.session_state.recipe_filter != "All":
    filtered = filtered[filtered["Category"] == st.session_state.recipe_filter]
if search_query:
    filtered = filtered[filtered["Name"].str.contains(search_query, case=False, na=False)]

# Apply sort
sort_map = {
    "Rating ↓": ("Rating", False),
    "Calories ↑": ("Calories", True),
    "Prep Time ↑": ("Prep Time (min)", True)
}
sort_col, sort_asc = sort_map[sort_by]
filtered = filtered.sort_values(sort_col, ascending=sort_asc)

# Show API results when available
if search_query and api_status == "ok" and api_results:
    st.subheader("🍽️ Spoonacular Results")
    for recipe in api_results:
        st.write(f"**{recipe['title']}**")
        if recipe.get("image"):
            st.image(recipe["image"], width=200)

# Feedback messages 
if search_query:
    st.info(f"🔍 Results for **\"{search_query}\"** — {len(filtered)} recipe(s) from local database found.")
elif st.session_state.recipe_filter != "All":
    st.info(f"📂 Showing **{st.session_state.recipe_filter}** — {len(filtered)} recipes.")
else:
    st.caption(f"{len(filtered)} recipes available")

if filtered.empty:
    st.warning("⚠️ No recipes match your search. Try a different keyword or filter.")
else:
    # Recipe card sections 
    sections = [
        ("⭐ Recommended for you", filtered[filtered["Rating"] >= 4.5].head(3)),
        ("🔥 Popular Recipes", filtered.head(3)),
        ("🕐 Past Recipes You've Tried", filtered.tail(3)),
    ]
    for title, section_df in sections:
        if section_df.empty:
            continue
        st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
        grid_html = '<div class="recipe-grid">'
        for _, r in section_df.iterrows():
            grid_html += (f'<div class="recipe-card">'
                          f'<div class="recipe-img-placeholder">{r["Emoji"]}</div>'
                          f'<div class="recipe-label">{r["Name"]}</div></div>')
        grid_html += '</div>'
        st.markdown(grid_html, unsafe_allow_html=True)

    # Full data table in expander 
    with st.expander("📊 View all recipes as table"):
        st.dataframe(
            filtered[["Name", "Category", "Calories", "Prep Time (min)", "Rating"]].reset_index(drop=True),
            use_container_width=True
        )

# DYNAMIC UI #1: Advanced Filters toggle
# The calorie slider, prep time filter, and chart only appear when the user enables "Advanced Filters"
# keeps the UI clean for quick browsing but gives Bob deeper controls when he wants to optimize for his iron-deficiency diet
st.write("")
show_advanced = st.toggle(
    "⚙️ Show Advanced Filters",
    value=st.session_state.show_advanced,
    key="show_advanced"  # key required: reset callback can turn this off by key
)

if show_advanced:
    # Widget 3: calorie range filter slider — only visible in advanced mode
    st.subheader("🔢 Filter by Calories")
    cal_min, cal_max = int(df["Calories"].min()), int(df["Calories"].max())
    cal_range = st.slider(
        "Calorie range", cal_min, cal_max,
        st.session_state.get("cal_range_slider", (cal_min, cal_max)),
        key="cal_range_slider"  # key required: reset callback clears this by key
    )

    # Widget 4: max prep time slider — only visible in advanced mode
    max_prep = st.slider("Max prep time (min)", 5, 60, 60, key="adv_max_prep_slider")

    # Apply advanced filters
    cal_filtered = filtered[
        (filtered["Calories"] >= cal_range[0]) &
        (filtered["Calories"] <= cal_range[1]) &
        (filtered["Prep Time (min)"] <= max_prep)
    ]

    if cal_filtered.empty:
        st.warning("⚠️ No recipes in that calorie/prep-time range.")
    else:
        st.write(f"✅ {len(cal_filtered)} recipe(s) between {cal_range[0]}–{cal_range[1]} cal · under {max_prep} min prep.")
        st.dataframe(cal_filtered[["Name", "Category", "Calories", "Prep Time (min)", "Rating"]].reset_index(drop=True),
                     use_container_width=True)

    # Visualization only shown in advanced mode
    st.write("")
    st.subheader("📈 Calories vs. Prep Time")
    st.caption("Bubble size = Rating · Color = Category · Updates with your active filters")

    viz_df = cal_filtered if not cal_filtered.empty else filtered

    if not viz_df.empty:
        fig = px.scatter(
            viz_df,
            x="Prep Time (min)",
            y="Calories",
            color="Category",
            size="Rating",
            text="Name",
            hover_data={"Name": True, "Calories": True, "Prep Time (min)": True, "Rating": True},
            color_discrete_map={"Breakfast": "#e8a87c", "Lunch": "#7a9e7e", "Dinner": "#4a7a50"},
            size_max=22,
            title="",
        )
        fig.update_traces(textposition="top center", textfont_size=9)
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#d4e0d2",
            font_family="Nunito, sans-serif",
            legend_title_text="Meal Type",
            xaxis_title="Prep Time (minutes)",
            yaxis_title="Calories",
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    # Provide a sensible default so downstream code that references cal_range still works
    cal_range = (int(df["Calories"].min()), int(df["Calories"].max()))

# DYNAMIC UI #2 + DEPENDENT DROPDOWNS: Add-to-Plan panel
# The specific-recipe dropdown only appears AFTER the user picks a meal category
# Its options are filtered to that category, so Bob always sees relevant meals (e.g. only Breakfast recipes when planning breakfast)
# The "Add to Plan" button and confirmation only appear once a recipe is chosen
st.write("")
st.subheader("📌 Add a Recipe to Your Plan")
st.caption("Pick a category first — the recipe list will update to match.")

# Parent dropdown: meal category
selected_category = st.selectbox(
    "Meal category",
    ["All", "Breakfast", "Lunch", "Dinner"],
    key="selected_category_dep",   # key required: on_change callback reads this by key
    on_change=on_category_change   # clears child selection when parent changes
)

# Build child options based on parent selection
if selected_category == "All":
    child_options = df["Name"].tolist()
else:
    child_options = df[df["Category"] == selected_category]["Name"].tolist()

# Determine safe default index for child dropdown
current_child = st.session_state.get("selected_recipe_dep")
default_idx = child_options.index(current_child) if current_child in child_options else 0

# Child dropdown: specific recipe — options depend on parent selection
selected_recipe = st.selectbox(
    "Choose recipe",
    child_options,
    index=default_idx,
    key="selected_recipe_dep"  # key required: on_category_change resets this by key
)

# Dynamic UI #2: "Add to Plan" controls only appear once a recipe is selected
if selected_recipe:
    recipe_row = df[df["Name"] == selected_recipe].iloc[0]
    st.info(
        f"**{recipe_row['Emoji']} {selected_recipe}** · "
        f"{recipe_row['Calories']} cal · "
        f"{recipe_row['Prep Time (min)']} min prep · "
        f"⭐ {recipe_row['Rating']}"
    )

    plan_date = st.date_input("Plan for date", key="dep_plan_date")
    plan_type = st.selectbox(
        "Meal slot", ["Breakfast", "Lunch", "Dinner", "Snack"],
        index=["Breakfast", "Lunch", "Dinner", "Snack"].index(
            recipe_row["Category"] if recipe_row["Category"] in ["Breakfast", "Lunch", "Dinner"] else "Snack"
        ),
        key="dep_plan_type"
    )

    if st.button("➕ Add to Plan", key="dep_add_btn"):
        if "saved_meals" not in st.session_state:
            st.session_state.saved_meals = []
        st.session_state.saved_meals.append({
            "date": str(plan_date), "type": plan_type, "name": selected_recipe
        })
        st.success(f"✅ **{selected_recipe}** added to your plan for {plan_date}!")
