from collections import namedtuple

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
from market_span_cluster.matches import find_similar_dtw_high_low_close_4

# SearchData = namedtuple("SearchData", ["ticker", "search_start", "search_end",
#                                        "pattern_start", "pattern_end", "pattern_lookback_days", "strategy", "top_n"])


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


def main():
    st.title("Financial Pattern Finder")

    # Initialize session state for preserving values
    # if 'search_results' not in st.session_state:
    #     st.session_state.search_results = None
    if 'data' not in st.session_state:
        st.session_state.data = None

    if "counter" not in st.session_state:
        st.session_state.counter = 0
    st.session_state.counter += 1
    st.header(f"This page has run {st.session_state.counter} times.")

    # Set default dates
    now = datetime.now(pytz.UTC)
    default_search_start = now - timedelta(days=180)
    default_pattern_start = now - timedelta(days=1)

    # Load data
    if st.session_state.data is None:
        input_file = "C:\\Users\\jkosk\dev\\data\\qqq-20230101-20241004.ohlcv-1m.csv.zip"
        df = load_csv(input_file, EST)
        df = resample(df, '5min')
        st.session_state.data = df

    with st.form("pattern_search_form"):
        # Create two columns for the form
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Search Range")
            ticker = st.text_input("Ticker Symbol", value="BTCUSDT", key='ticker')
            search_start = st.date_input(
                "Search Start Date",
                value=default_search_start.date(),
                max_value=now.date(),
                key='search-start-date'
            )
            search_end = st.date_input(
                "Search End Date",
                value=now.date(),
                min_value=search_start,
                max_value=now.date(),
                key='search-end-date'
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
                value=now.date(),
                min_value=search_start,
                max_value=now.date(),
                key='pattern-end-date'
            )
            pattern_end_time = st.time_input(
                "Pattern End Time",
                value=now.time(),
                key='pattern-end-time'
            )
            pattern_lookback_days = st.number_input(
                "Lookback Days",
                value=1,
                min_value=1,
                max_value=3,
                key='lookback-days'
            )

        # Bottom form elements
        col3, col4, col5 = st.columns(3)

        with col3:
            strategy = st.selectbox(
                "Strategy",
                options=["DTW"],
                index=0
            )

        with col4:
            top_n = st.number_input(
                "Number of matches",
                min_value=1,
                max_value=10,
                value=5
            )

        submitted = st.form_submit_button("Find Patterns")

        if submitted:
            # pattern_start_dt = datetime.combine(pattern_start, pattern_start_time, tzinfo=pytz.UTC)
            print(f"{st.session_state.counter} Pattern end date: {pattern_end_time}")
            pattern_end_dt = EST.localize(datetime.combine(pattern_end, pattern_end_time))
            st.session_state.search_results = find_similar_dtw_high_low_close_4(st.session_state.data,
                                                                                time(9, 30),
                                                                                pattern_lookback_days,
                                                                                pattern_end_dt, top_n)

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
