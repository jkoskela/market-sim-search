import numpy as np
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import pytz

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
# st.set_page_config(layout="wide")

from market_sim_search.config import EST, PROJ_ROOT
from market_sim_search.data import load_csv, resample
from market_sim_search.matches import StrategyRunner
from market_sim_search.models import WindowMatch
from market_sim_search.plotting import get_window_matches, create_streamlit_chart


@st.cache_data
def load_data(uploaded_file):
    """Load and cache data from uploaded file"""
    if uploaded_file is not None:
        df = load_csv(uploaded_file, EST)
        df = resample(df, '5min')
        df.dropna(inplace=True)
        return df
    return None


@st.cache_data(show_spinner=False)
def run_search(data: pd.DataFrame, window_time_start: time, window_size_days: int, target_end: datetime,
               top: int = None) -> list[WindowMatch]:
    progress_bar = st.progress(0, 'Searching for similar time ranges...')
    runner = StrategyRunner(lambda x: progress_bar.progress(x))
    matches = runner.find_similar_dtw_high_low_close_4(data, window_time_start, window_size_days, target_end, top)
    return get_window_matches(data, matches)


def main():
    st.markdown("""
        <style>
            .block-container {
                max-width: 80vw;
                padding: 1rem;
            }
            .st-key-form_container {
                width: 50%;
            }
        </style>
    """, unsafe_allow_html=True)

    st.title("Market Sim Search")

    now = datetime.now(pytz.UTC)
    if "counter" not in st.session_state:
        st.session_state.counter = 0
        st.session_state.df = None
        st.session_state.search_results = None

        # Initialize default form values
        st.session_state.search_start_date = now.date()
        st.session_state.search_end_date = now.date()
        st.session_state.target_end_date = now.date()
        st.session_state.target_end_time = now.time()
        st.session_state.lookback_days = 1
        st.session_state.top_n = 7

    st.header(f"This page has run {st.session_state.counter} times.")
    st.session_state.counter += 1

    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=['csv', 'zip'],
        help="Upload a CSV file with OHLCV data or a zipped CSV file"
    )

    # Load data if file is uploaded
    if uploaded_file is not None:
        st.session_state.df = load_data(uploaded_file)

        if st.session_state.df is not None:
            # Get dataframe date range for defaults
            df_start_date = st.session_state.df.index.min().date()
            df_end_date = st.session_state.df.index.max().date()

            st.success(f"Data loaded successfully! Date range: {df_start_date} to {df_end_date}")

            # Update form values based on dataframe
            st.session_state.search_start_date = df_start_date
            st.session_state.search_end_date = df_end_date
            st.session_state.target_end_date = df_end_date
            st.session_state.target_end_time = time(10)
            st.session_state.lookback_days = 1
            st.session_state.top_n = 7

            # Only render the form if data is loaded
            form_container = st.container(key='form_container')
            with form_container.form("target_search_form"):
                st.subheader("Target Range")
                target_end = st.date_input(
                    "Target End Date",
                    min_value=st.session_state.get('search_start_date', now.date()),
                    max_value=st.session_state.get('search_end_date', now.date()),
                    key='target_end_date'
                )
                target_end_time = st.time_input(
                    "Target End Time",
                    key='target_end_time'
                )
                target_lookback_days = st.number_input(
                    "Lookback Days",
                    min_value=1,
                    max_value=3,
                    key='lookback_days'
                )
                # Bottom form elements
                col3, col4 = st.columns(2)
                with col3:
                    # Unused for now
                    strategy = st.selectbox(
                        "Strategy",
                        options=["DTW"],
                        key='strategy'
                    )
                with col4:
                    top_n = st.number_input(
                        "Number of matches",
                        min_value=1,
                        max_value=10,
                        key='top_n'
                    )
                submitted = st.form_submit_button("Find Matches")
                if submitted:
                    target_end_dt = EST.localize(datetime.combine(target_end, target_end_time))
                    st.session_state.search_results = run_search(st.session_state.df, time(9, 30),
                                                                target_lookback_days,
                                                                target_end_dt, top_n)

    # Display target if we have results
    if st.session_state.search_results is not None:
        st.subheader("Matches")
        with st.container(key='matches-container'):
            col6, col7 = st.columns(2)
            with col6:
                for match in st.session_state.search_results[::2]:
                    match_end_date = match.match_end.strftime('%Y-%m-%d')
                    st.write(f"**Match End: {match_end_date}**")
                    chart = create_streamlit_chart(match)
                    chart.load()
            with col7:
                for match in st.session_state.search_results[1::2]:
                    match_end_date = match.match_end.strftime('%Y-%m-%d')
                    st.write(f"**Match End: {match_end_date}**")
                    chart = create_streamlit_chart(match)
                    chart.load()


if __name__ == "__main__":
    main()
