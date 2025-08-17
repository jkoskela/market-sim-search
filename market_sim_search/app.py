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
def load_data():
    input_file = Path(f'{PROJ_ROOT}/data/examples/qqq-20240701-20241004.ohlcv-1m.csv.zip')
    df = load_csv(input_file, EST)
    df = resample(df, '5min')
    df.dropna(inplace=True)
    return df


@st.cache_data(show_spinner=False)
def run_search(data: pd.DataFrame, window_time_start: time, window_size_days: int, target_end: datetime,
               top: int = None) -> list[WindowMatch]:
    progress_bar = st.progress(0, 'Searching for patterns...')
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

        # Initialize default form values
        st.session_state.search_start_date = (now - timedelta(days=180)).date()
        st.session_state.search_end_date = now.date()
        st.session_state.pattern_end_date = now.date()
        st.session_state.pattern_end_time = now.time()
        st.session_state.lookback_days = 1
        st.session_state.top_n = 7
        st.session_state.search_results = None
        st.session_state.search_results = None

        # Load historical data
        st.session_state.df = load_data()

    st.header(f"This page has run {st.session_state.counter} times.")
    st.session_state.counter += 1

    form_container = st.container(key='form_container')
    with form_container.form("pattern_search_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Search Range")
            # ticker = st.text_input("Ticker Symbol", value="BTCUSDT", key='ticker')
            search_start = st.date_input(
                "Search Start Date",
                max_value=now.date(),
                key='search_start_date'
            )
            search_end = st.date_input(
                "Search End Date",
                min_value=search_start,
                max_value=now.date(),
                key='search_end_date'
            )

        with col2:
            st.subheader("Pattern Range")
            # pattern_start = st.date_input(
            #     "Pattern Start Date",
            #     value=default_pattern_start.date(),
            #     min_value=search_start,
            #     max_value=now.date()
            # )
            # pattern_start_time = st.time_input(
            #     "Pattern Start Time",
            #     value=default_pattern_start.time()
            # )
            # pattern_end = st.date_input(
            #     "Pattern End Date",
            #     value=now.date(),
            #     min_value=pattern_start,
            #     max_value=now.date()
            # )
            pattern_end = st.date_input(
                "Pattern End Date",
                min_value=search_start,
                max_value=now.date(),
                key='pattern_end_date'
            )
            pattern_end_time = st.time_input(
                "Pattern End Time",
                key='pattern_end_time'
            )
            pattern_lookback_days = st.number_input(
                "Lookback Days",
                min_value=1,
                max_value=3,
                key='lookback_days'
            )

        # Bottom form elements
        col3, col4, col5 = st.columns(3)
        with col3:
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
        with col5:
            equity_type = st.selectbox(
                "Equity Type",
                options=["Stock", "Crypto", "Future"],
                key='equity_type'
            )

        submitted = st.form_submit_button("Find Patterns")
        if submitted:
            pattern_end_dt = EST.localize(datetime.combine(pattern_end, pattern_end_time))
            st.session_state.search_results = run_search(st.session_state.df, time(9, 30),
                                                         pattern_lookback_days,
                                                         pattern_end_dt, top_n)

    # Display pattern if we have results
    if st.session_state.search_results is not None:
        st.subheader("Pattern Matches")
        with st.container(key='matches-container'):
            col6, col7 = st.columns(2)
            with col6:
                for match in st.session_state.search_results[::2]:
                    chart = create_streamlit_chart(match)
                    chart.load()
            with col7:
                for match in st.session_state.search_results[1::2]:
                    chart = create_streamlit_chart(match)
                    chart.load()


if __name__ == "__main__":
    main()
