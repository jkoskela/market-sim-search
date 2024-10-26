import threading
from collections import namedtuple
from typing import Callable

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, time
import pytz

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from market_span_cluster.config import EST
from market_span_cluster.data import load_csv, resample
from market_span_cluster.matches import StrategyRunner


def create_candlestick_plot(df, title="Price Chart"):
    """Create a candlestick chart from OHLCV data"""
    fig = go.Figure(data=[go.Candlestick(x=df.index,
                                         open=df['open'],
                                         high=df['high'],
                                         low=df['low'],
                                         close=df['close'])])

    fig.update_layout(
        title=title,
        yaxis_title='Price',
        xaxis_title='Date',
        height=400,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig


@st.cache_data
def fetch_and_clean_data():
    input_file = "C:\\Users\\jkosk\dev\\data\\qqq-20230101-20241004.ohlcv-1m.csv.zip"
    df = load_csv(input_file, EST)
    df = resample(df, '5min')
    return df.loc['2024-01-01':]


def main():
    st.title("Financial Pattern Finder")

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

        # Load historical data
        st.session_state.df = fetch_and_clean_data()

    st.header(f"This page has run {st.session_state.counter} times.")
    st.session_state.counter += 1

    with st.form("pattern_search_form"):
        # Create two columns for the form
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Search Range")
            ticker = st.text_input("Ticker Symbol", value="BTCUSDT", key='ticker')
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
                index=0,
                key='strategy'
            )

        with col4:
            top_n = st.number_input(
                "Number of matches",
                min_value=1,
                max_value=10,
                key='top_n'
            )

        submitted = st.form_submit_button("Find Patterns")

        if submitted:
            # pattern_start_dt = datetime.combine(pattern_start, pattern_start_time, tzinfo=pytz.UTC)
            # print(f"{st.session_state.counter} Pattern end date: {pattern_end_time}")

            df = st.session_state.df
            progress_bar = st.progress(0, 'Searching for patterns...')

            def report_progress(progress: int):
                progress_bar.progress(progress)

            def get_results():
                pattern_end_dt = EST.localize(datetime.combine(pattern_end, pattern_end_time))
                runner = StrategyRunner(progress_reporter=report_progress)
                st.session_state.search_results = runner.find_similar_dtw_high_low_close_4(df,
                                                                                           time(9, 30),
                                                                                           pattern_lookback_days,
                                                                                           pattern_end_dt, top_n)

            thread = threading.Thread(target=get_results)
            thread.start()

    # Display pattern if we have results
    if st.session_state.search_results is not None:
        st.subheader("Pattern Matches")

        # Create tabs for different view options
        tab1, tab2 = st.tabs(["Individual Charts", "Combined View"])

        with tab1:
            for i, match_df in enumerate(st.session_state.search_results):
                st.plotly_chart(
                    create_candlestick_plot(match_df, f"Match {i + 1}"),
                    use_container_width=True
                )

        with tab2:
            # Create subplot with all matches
            if st.session_state.search_results:
                fig = go.Figure()
                for i, match_df in enumerate(st.session_state.search_results):
                    fig.add_trace(go.Candlestick(
                        x=match_df.index,
                        open=match_df['open'],
                        high=match_df['high'],
                        low=match_df['low'],
                        close=match_df['close'],
                        name=f"Match {i + 1}"
                    ))

                fig.update_layout(
                    title="All Matches Comparison",
                    yaxis_title='Price',
                    xaxis_title='Date',
                    height=600,
                    showlegend=True
                )
                st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
