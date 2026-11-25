"""TradeMind Streamlit Frontend - Main Entry Point."""

from __future__ import annotations

import streamlit as st

from frontend.config import get_frontend_settings


def main():
    """Main Streamlit application."""
    settings = get_frontend_settings()

    st.set_page_config(
        page_title=settings.page_title,
        page_icon=settings.page_icon,
        layout=settings.layout,
        initial_sidebar_state="expanded",
    )

    # Sidebar - API Configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # API Key input
        api_key = st.text_input(
            "API Key",
            type="password",
            value=st.session_state.get("api_key", ""),
            help="Enter your API key for authenticated endpoints",
        )
        if api_key:
            st.session_state["api_key"] = api_key

        # API Base URL
        api_url = st.text_input(
            "API Base URL",
            value=st.session_state.get("api_base_url", settings.api_base_url),
            help="FastAPI backend URL",
        )
        if api_url != st.session_state.get("api_base_url", settings.api_base_url):
            st.session_state["api_base_url"] = api_url
            st.cache_resource.clear()  # Reset API client

        st.divider()

        # Connection status
        if st.button("🔄 Test Connection"):
            test_connection()

        st.divider()

        # Cache controls
        st.subheader("🗄️ Cache")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Clear All"):
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("Caches cleared!")
        with col2:
            if st.button("Invalidate Data"):
                from frontend.services.cache import invalidate_market_data, invalidate_research, invalidate_portfolio, invalidate_orders
                invalidate_market_data()
                invalidate_research()
                invalidate_portfolio()
                invalidate_orders()
                st.success("Data caches invalidated!")

        st.divider()

        # Quick stats
        st.subheader("📊 Quick Stats")
        show_quick_stats()

    # Main content - Navigation
    pages = {
        "📊 Market Data": "pages/1_📊_Market_Data.py",
        "🔬 Research": "pages/2_🔬_Research.py",
        "📈 Trading": "pages/3_📈_Trading.py",
        "⚠️ Risk": "pages/4_⚠️_Risk.py",
        "📜 History": "pages/5_📜_History.py",
    }

    # Since we use multi-page, just show welcome
    st.title("📈 TradeMind")
    st.markdown("""
    Welcome to **TradeMind** - Your AI-powered trading research and paper trading platform.

    **Navigate using the sidebar** (or the pages menu above) to access:
    - 📊 **Market Data** - Search tickers, view charts with technical indicators
    - 🔬 **Research** - Run AI agent analysis with strategy consensus
    - 📈 **Trading** - Execute paper trades, monitor portfolio
    - ⚠️ **Risk** - View exposure limits, position sizing, daily loss tracking
    - 📜 **History** - Order history, P&L analysis, performance metrics

    ### Quick Start
    1. Ensure the FastAPI backend is running: `uvicorn app.main:app --reload`
    2. Enter your API key in the sidebar (if required)
    3. Click **Test Connection** to verify
    4. Navigate to any page to start!
    """)


def test_connection():
    """Test API connection."""
    from frontend.services.async_runner import run_async

    api_key = st.session_state.get("api_key")
    try:
        result = run_async(lambda c: c.health_check(), api_key)
        st.sidebar.success(f"✅ Connected: {result}")
    except Exception as e:
        st.sidebar.error(f"❌ Connection failed: {e}")


def show_quick_stats():
    """Show quick portfolio stats in sidebar."""
    from frontend.services.cache import cached_portfolio

    try:
        portfolio = cached_portfolio()
        st.metric("Equity", f"${portfolio.get('equity', 0):,.2f}")
        st.metric("Cash", f"${portfolio.get('cash', 0):,.2f}")
        st.metric("Positions", len(portfolio.get('positions', [])))
    except Exception:
        st.caption("Connect to backend to see stats")


if __name__ == "__main__":
    main()