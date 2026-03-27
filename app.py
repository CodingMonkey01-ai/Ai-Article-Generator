import streamlit as st
import pandas as pd
import os

from utils.excel_loader import load_keywords_with_dates, update_fetch_dates, add_keywords_to_excel, remove_keyword_from_excel, expand_keywords_with_modifiers
from search.gemini_search import get_news_for_keyword, get_web_content_for_article
from llm.gemini_text import generate_article_from_web_search
from llm.gemini_image import generate_image
from utils.file_saver import save_article

# ---------------------------------
# Page config
# ---------------------------------
st.set_page_config(
    page_title="AI Article Generator",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------
# Custom CSS for modern styling
# ---------------------------------
st.markdown("""
<style>
    /* Main container */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Header styling */
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }

    .main-header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: 700;
    }

    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 1.1rem;
    }

    /* Card styling */
    .custom-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
        border: 1px solid #e0e0e0;
    }

    .custom-card:hover {
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
        transition: box-shadow 0.3s ease;
    }

    /* Step indicator */
    .step-indicator {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 600;
        margin-bottom: 1rem;
    }

    /* Keyword badge */
    .keyword-badge {
        display: inline-block;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.4rem 0.8rem;
        border-radius: 20px;
        margin: 0.2rem;
        font-size: 0.85rem;
        font-weight: 500;
    }

    /* Metric card */
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8eb 100%);
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #e0e0e0;
    }

    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #667eea;
    }

    .metric-label {
        font-size: 0.9rem;
        color: #666;
        margin-top: 0.3rem;
    }

    /* Success message */
    .success-box {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        border: 1px solid #28a745;
        border-radius: 10px;
        padding: 1rem;
        color: #155724;
    }

    /* Article card */
    .article-card {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        border: 1px solid #e8e8e8;
    }

    /* Image container */
    .image-container {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
    }

    /* Button styling */
    .stButton > button {
        border-radius: 25px;
        padding: 0.5rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }

    /* Sidebar styling */
    .css-1d391kg {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
    }

    /* Progress bar */
    .stProgress > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }

    /* Expander styling */
    .streamlit-expanderHeader {
        font-weight: 600;
        font-size: 1rem;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 10px 10px 0 0;
        padding: 10px 20px;
        font-weight: 500;
    }

    /* Hide default streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ---------------------------------
# Header
# ---------------------------------
st.markdown("""
<div class="main-header">
    <h1>📝 AI Article Generator</h1>
    <p>Powered by Gemini AI | Professional Content Creation</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------
# Load keywords from Excel or session state
# ---------------------------------
KEYWORD_FILE = "data/keywords.xlsx"

# Initialize keywords in session state (with fetch dates)
if "keywords_data" not in st.session_state:
    if os.path.exists(KEYWORD_FILE):
        st.session_state["keywords_data"] = load_keywords_with_dates(KEYWORD_FILE)
    else:
        st.session_state["keywords_data"] = []

keywords_data = st.session_state["keywords_data"]
keywords = [kd["keyword"] for kd in keywords_data]

# ---------------------------------
# Sidebar
# ---------------------------------
with st.sidebar:
    st.markdown("### 🎯 Keywords Dashboard")
    st.markdown("---")

    # Add keywords section
    st.markdown("#### ➕ Add Keywords")
    new_keywords = st.text_area(
        "Enter keywords (one per line)",
        placeholder="Enter keywords here...\nOne keyword per line",
        height=100,
        key="new_keywords_input"
    )

    expand_keywords = st.checkbox(
        "Expand with modifiers (fall, demand, supply, rise)",
        value=False,
        key="expand_keywords_toggle",
        help="Creates keyword variations by appending: fall, demand, supply, rise"
    )

    col_add, col_clear = st.columns(2)
    with col_add:
        if st.button("Add Keywords", use_container_width=True):
            if new_keywords.strip():
                new_kw_list = [kw.strip() for kw in new_keywords.strip().split("\n") if kw.strip()]
                # Expand keywords with modifiers if toggled on
                if expand_keywords:
                    new_kw_list = expand_keywords_with_modifiers(new_kw_list)
                # Add to Excel file
                added_count = add_keywords_to_excel(KEYWORD_FILE, new_kw_list)
                # Reload from Excel to sync
                st.session_state["keywords_data"] = load_keywords_with_dates(KEYWORD_FILE)
                st.session_state.pop("news_per_keyword", None)
                st.session_state.pop("selected_articles", None)
                st.toast(f"Added {added_count} keywords to Excel!", icon="✅")
                st.rerun()

    with col_clear:
        if st.button("Clear Session", use_container_width=True):
            st.session_state.pop("news_per_keyword", None)
            st.session_state.pop("selected_articles", None)
            st.session_state.pop("generated_articles", None)
            st.rerun()

    st.markdown("---")

    # Domain filters section
    st.markdown("#### 🌐 Domain Filters")
    with st.expander("Configure Domain Filters", expanded=False):
        include_domains_input = st.text_area(
            "Include Domains (one per line)",
            value=st.session_state.get("include_domains_text", ""),
            placeholder="reuters.com\nbbc.com\ncnn.com",
            height=80,
            key="include_domains_input",
            help="Only search from these domains. Leave empty to search all domains."
        )

        exclude_domains_input = st.text_area(
            "Exclude Domains (one per line)",
            value=st.session_state.get("exclude_domains_text", ""),
            placeholder="example.com\nspam-site.com",
            height=80,
            key="exclude_domains_input",
            help="Never search from these domains."
        )

        if st.button("Apply Filters", use_container_width=True):
            # Parse and save domain filters
            include_list = [d.strip() for d in include_domains_input.strip().split("\n") if d.strip()]
            exclude_list = [d.strip() for d in exclude_domains_input.strip().split("\n") if d.strip()]

            st.session_state["include_domains"] = include_list if include_list else None
            st.session_state["exclude_domains"] = exclude_list if exclude_list else None
            st.session_state["include_domains_text"] = include_domains_input
            st.session_state["exclude_domains_text"] = exclude_domains_input

            # Clear previous search results when filters change
            st.session_state.pop("news_per_keyword", None)
            st.session_state.pop("selected_articles", None)

            st.toast("Domain filters applied!", icon="🌐")
            st.rerun()

        # Show current filters
        if st.session_state.get("include_domains"):
            st.success(f"✅ Include: {', '.join(st.session_state['include_domains'])}")
        if st.session_state.get("exclude_domains"):
            st.error(f"🚫 Exclude: {', '.join(st.session_state['exclude_domains'])}")

    st.markdown("---")

    # Metrics in sidebar
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Keywords", len(keywords), delta=None)
    with col2:
        generated_count = len(st.session_state.get("generated_articles", []))
        st.metric("Generated", generated_count)

    st.markdown("---")
    st.markdown("#### 📋 Current Keywords")

    # Display keywords with remove option
    if keywords_data:
        for idx, kd in enumerate(keywords_data):
            date_info = f" ({kd['fetch_date']})" if kd['fetch_date'] else " (new)"
            col_kw, col_del = st.columns([4, 1])
            with col_kw:
                st.markdown(f'<span class="keyword-badge">{kd["keyword"]}{date_info}</span>', unsafe_allow_html=True)
            with col_del:
                if st.button("🗑️", key=f"del_{idx}_{kd['keyword']}", help=f"Remove {kd['keyword']}"):
                    remove_keyword_from_excel(KEYWORD_FILE, kd["keyword"])
                    st.session_state["keywords_data"] = load_keywords_with_dates(KEYWORD_FILE)
                    st.session_state.pop("news_per_keyword", None)
                    st.session_state.pop("selected_articles", None)
                    st.toast(f"Removed '{kd['keyword']}' from Excel!", icon="🗑️")
                    st.rerun()
    else:
        st.info("No keywords added yet. Add keywords above.")

    st.markdown("---")
    st.markdown("#### ℹ️ How to Use")
    with st.expander("View Instructions", expanded=False):
        st.markdown("""
        1. **Add Keywords** - Enter keywords manually or load from Excel
        2. **Fetch News** - Find relevant news for each keyword (confidence > 40%)
        3. **Select Articles** - Choose which articles to generate
        4. **Generate** - Create AI-powered articles using web search data
        5. **Download** - Get your DOCX files with embedded images
        """)

# ---------------------------------
# Main Content Area
# ---------------------------------

# Step 1: Fetch News
st.markdown('<div class="step-indicator">📰 Step 1</div>', unsafe_allow_html=True)
st.markdown("### Fetch News for All Keywords")

if not keywords:
    st.warning("Please add keywords first using the sidebar.")
else:
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        fetch_button = st.button("🔍 Fetch News for All Keywords", use_container_width=True, type="primary")

    if fetch_button:
        news_per_keyword = {}  # Dict: keyword -> list of articles
        keywords_with_news = []  # Track keywords that got news

        progress_container = st.container()
        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, kw_data in enumerate(keywords_data):
                kw = kw_data["keyword"]
                fetch_date = kw_data["fetch_date"]

                status_text.markdown(f"🔄 **Finding relevant news for:** `{kw}` (from: {fetch_date or 'week ago'})")
                news_list = get_news_for_keyword(
                    kw,
                    num_results=10,
                    min_confidence=0.4,
                    last_fetch_date=fetch_date,
                    include_domains=st.session_state.get("include_domains"),
                    exclude_domains=st.session_state.get("exclude_domains")
                )

                if news_list:
                    news_per_keyword[kw] = news_list
                    keywords_with_news.append(kw)

                progress_bar.progress((idx + 1) / len(keywords_data))

            status_text.empty()
            progress_bar.empty()

        # Update fetch dates in Excel for keywords that got news
        if keywords_with_news and os.path.exists(KEYWORD_FILE):
            update_fetch_dates(KEYWORD_FILE, keywords_with_news)
            # Reload keywords data to reflect updated dates
            st.session_state["keywords_data"] = load_keywords_with_dates(KEYWORD_FILE)

        st.session_state["news_per_keyword"] = news_per_keyword
        st.session_state.pop("selected_articles", None)
        st.session_state.pop("generated_articles", None)

        total_articles = sum(len(articles) for articles in news_per_keyword.values())
        st.toast(f"✅ Found {total_articles} articles for {len(news_per_keyword)} keywords!", icon="🎉")
        st.rerun()

# ---------------------------------
# Step 2: Display and Select Articles Per Keyword
# ---------------------------------
if "news_per_keyword" in st.session_state and st.session_state["news_per_keyword"]:
    st.markdown("---")
    st.markdown('<div class="step-indicator">✅ Step 2</div>', unsafe_allow_html=True)
    st.markdown("### Select Article for Each Keyword")

    news_per_keyword = st.session_state["news_per_keyword"]

    # Summary metrics
    total_keywords_with_news = len(news_per_keyword)
    total_articles = sum(len(articles) for articles in news_per_keyword.values())
    keywords_without_news = [kd["keyword"] for kd in st.session_state["keywords_data"] if kd["keyword"] not in news_per_keyword]

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total_keywords_with_news}</div>
            <div class="metric-label">Keywords with News</div>
        </div>
        """, unsafe_allow_html=True)
    with metric_col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total_articles}</div>
            <div class="metric-label">Total Articles Found</div>
        </div>
        """, unsafe_allow_html=True)
    with metric_col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(keywords_without_news)}</div>
            <div class="metric-label">Keywords Without Match</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if keywords_without_news:
        st.warning(f"⚠️ No relevant news found for: {', '.join(keywords_without_news)}")

    st.markdown("#### 📋 Select Articles Per Keyword (Multiple Allowed)")
    st.info("💡 You can select multiple articles for each keyword. An article will be generated for each selection.")

    # Store selections - list of {keyword, title, url, confidence}
    all_selections = []

    # Create expandable sections for each keyword
    for kw, articles in news_per_keyword.items():
        with st.expander(f"🔑 **{kw}** ({len(articles)} articles)", expanded=True):
            # Build options for multiselect
            options = []
            option_details = {}

            for idx, art in enumerate(articles):
                conf_pct = int(art["confidence"] * 100)
                display_title = art["title"][:70] + "..." if len(art["title"]) > 70 else art["title"]
                option_text = f"[{conf_pct}%] {display_title}"
                options.append(option_text)
                option_details[option_text] = {
                    "title": art["title"],
                    "url": art["url"],
                    "confidence": art["confidence"]
                }

            # Multiselect for this keyword - default to first article
            selected_options = st.multiselect(
                f"Select articles for '{kw}'",
                options=options,
                default=[options[0]] if options else [],
                key=f"select_{kw}",
                label_visibility="collapsed"
            )

            # Show article details table
            df_articles = pd.DataFrame([{
                "Confidence": f"{int(art['confidence']*100)}%",
                "Title": art["title"][:80] + "..." if len(art["title"]) > 80 else art["title"],
                "URL": art["url"]
            } for art in articles])

            st.dataframe(
                df_articles,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Confidence": st.column_config.TextColumn("Relevance%", width="small"),
                    "Title": st.column_config.TextColumn("Article Title", width="large"),
                    "URL": st.column_config.LinkColumn("URL", width="medium")
                }
            )

            # Add selected articles to list
            for option in selected_options:
                art_data = option_details[option]
                all_selections.append({
                    "keyword": kw,
                    "title": art_data["title"],
                    "url": art_data["url"],
                    "confidence": art_data["confidence"]
                })

    # Save selections to session state
    if all_selections:
        st.session_state["selected_articles"] = all_selections

        st.markdown("---")
        st.success(f"✅ {len(all_selections)} articles selected for generation")

        # Show selection summary
        st.markdown("#### 📝 Selection Summary")
        summary_df = pd.DataFrame([{
            "Keyword": art["keyword"],
            "Selected Article": art["title"][:60] + "..." if len(art["title"]) > 60 else art["title"],
            "Confidence": f"{int(art['confidence']*100)}%"
        } for art in all_selections])

        st.dataframe(summary_df, use_container_width=True, hide_index=True)
    else:
        st.session_state.pop("selected_articles", None)
        st.warning("No articles selected. Please select at least one article to generate.")

# ---------------------------------
# Step 3: Generate Articles for Selected Articles
# ---------------------------------
if "selected_articles" in st.session_state and st.session_state["selected_articles"]:
    st.markdown("---")
    st.markdown('<div class="step-indicator">🚀 Step 3</div>', unsafe_allow_html=True)
    st.markdown("### Generate Articles")

    selected_articles = st.session_state["selected_articles"]

    # Group selected articles by keyword
    articles_by_keyword = {}
    for art in selected_articles:
        kw = art["keyword"]
        if kw not in articles_by_keyword:
            articles_by_keyword[kw] = []
        articles_by_keyword[kw].append(art)

    num_keywords = len(articles_by_keyword)
    total_news = len(selected_articles)

    st.info(f"💡 Ready to generate {num_keywords} articles from {total_news} selected news sources.")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        generate_button = st.button("✨ Generate Articles", use_container_width=True, type="primary")

    if generate_button:
        generated_articles = []

        progress_container = st.container()
        with progress_container:
            progress_bar = st.progress(0)
            status_container = st.empty()

            total_steps = num_keywords * 2  # 2 steps per keyword: content+article, image
            current_step = 0

            for kw, news_list in articles_by_keyword.items():
                news_titles = [n["title"] for n in news_list]
                combined_title = " | ".join([t[:50] for t in news_titles])

                # Step 1: Fetch web content for ALL selected news and generate article
                with status_container:
                    st.markdown(f"""
                    <div class="custom-card">
                        <strong>📝 Processing: {kw}</strong><br>
                        <small>Step 1/2: Fetching content from {len(news_list)} sources and generating article...</small>
                    </div>
                    """, unsafe_allow_html=True)

                # Fetch web content for each selected news and combine
                all_web_content = []
                for news in news_list:
                    content = get_web_content_for_article(
                        keyword=kw,
                        news_title=news["title"],
                        num_results=5  # Get more results per source
                    )
                    if content:
                        all_web_content.append(f"=== NEWS: {news['title'][:100]} ===\n{content}")

                combined_content = "\n\n".join(all_web_content)

                # Generate article using combined content from all sources
                article = generate_article_from_web_search(
                    keyword=kw,
                    news_title=combined_title,
                    web_content=combined_content
                )
                current_step += 1
                progress_bar.progress(current_step / total_steps)

                filename = kw.replace(" ", "_")

                # Step 2: Generate image
                with status_container:
                    st.markdown(f"""
                    <div class="custom-card">
                        <strong>🎨 Processing: {kw}</strong><br>
                        <small>Step 2/2: Generating featured image...</small>
                    </div>
                    """, unsafe_allow_html=True)
                image_path = f"output/images/{filename}.png"
                generate_image(
                    article_title=f"{kw} - {news_titles[0]}",
                    save_path=image_path
                )
                current_step += 1
                progress_bar.progress(current_step / total_steps)

                # Save article with embedded image
                save_article(article, filename, image_path=image_path)

                generated_articles.append({
                    "keyword": kw,
                    "filename": filename,
                    "article": article,
                    "image_path": image_path,
                    "source_news": f"{len(news_list)} sources: {', '.join([t[:40] for t in news_titles])}"
                })

            status_container.empty()
            progress_bar.empty()

        st.session_state["generated_articles"] = generated_articles
        st.toast(f"✅ Generated {len(generated_articles)} articles successfully!", icon="🎉")
        st.balloons()
        st.rerun()

# ---------------------------------
# Output Section - Display All Generated Articles
# ---------------------------------
if "generated_articles" in st.session_state and st.session_state["generated_articles"]:
    st.markdown("---")
    st.markdown('<div class="step-indicator">📄 Results</div>', unsafe_allow_html=True)
    st.markdown("### Generated Articles")

    # Success summary
    st.markdown(f"""
    <div class="success-box">
        <strong>🎉 Success!</strong> Generated {len(st.session_state["generated_articles"])} articles with embedded images.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Create tabs for each article (use filename for unique identification)
    tab_labels = []
    for idx, art in enumerate(st.session_state["generated_articles"]):
        filename = art.get("filename", art["keyword"].replace(" ", "_"))
        tab_labels.append(f"📄 {filename}")

    tabs = st.tabs(tab_labels)

    for idx, (tab, art_data) in enumerate(zip(tabs, st.session_state["generated_articles"])):
        with tab:
            filename = art_data.get("filename", art_data["keyword"].replace(" ", "_"))

            # Article header
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        padding: 1rem; border-radius: 10px; margin-bottom: 1rem;">
                <h4 style="color: white; margin: 0;">📌 {art_data['keyword']}</h4>
                <small style="color: rgba(255,255,255,0.8);">Source: {art_data['source_news'][:100]}...</small>
            </div>
            """, unsafe_allow_html=True)

            # Two column layout: Article + Image
            col1, col2 = st.columns([3, 2])

            with col1:
                st.markdown("##### 📝 Article Content")
                st.text_area(
                    "Article",
                    art_data["article"],
                    height=400,
                    key=f"article_{idx}_{filename}",
                    label_visibility="collapsed"
                )

                # Download button
                docx_path = f"output/articles/{filename}.docx"
                if os.path.exists(docx_path):
                    with open(docx_path, "rb") as f:
                        st.download_button(
                            "📥 Download Article (DOCX)",
                            f.read(),
                            file_name=f"{filename}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"download_{idx}_{filename}",
                            use_container_width=True
                        )

            with col2:
                st.markdown("##### 🖼️ Featured Image")
                if os.path.exists(art_data["image_path"]):
                    st.image(art_data["image_path"], use_container_width=True)
                    st.caption(f"AI-generated image for: {art_data['keyword']}")
                else:
                    st.warning("Image not found")

# ---------------------------------
# Footer
# ---------------------------------
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; padding: 1rem;">
    <small>Built with Streamlit | Powered by Gemini AI</small>
</div>
""", unsafe_allow_html=True)
