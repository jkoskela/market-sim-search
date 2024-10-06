from datetime import timedelta, time, datetime
from typing import Callable

import pandas as pd
import numpy as np
from tslearn.metrics import dtw

from market_pattern_search.config import EST
from market_pattern_search.models import MatchModel

Strategy = Callable[[pd.DataFrame, pd.DataFrame], float]
window_boundary_tolerance = timedelta(minutes=5)


def hlc4(data: pd.DataFrame):
    return (data.high + data.low + data.close + data.close) / 4


# def normalize_window(data: pd.DataFrame, feature: pd.Series):
#     norm = (feature  - data.low.min()) / (data.high.max() - data.low.min())
#     if norm_percent:
#       norm = norm * 100/data.low.min()
#     return norm

def normalize_window(feature: pd.Series, base: float):
    """Normalize data as percent change from base"""
    return (feature - base) / base


def dtw_hlc4(target: pd.DataFrame, window: pd.DataFrame):
    """Run DTW using hlc4"""
    norm_target = normalize_window(hlc4(target), target.close[-1])
    norm_window = normalize_window(hlc4(window), window.close[-1])
    return dtw(norm_target, norm_window)


def dtw_close(target: pd.DataFrame, window: pd.DataFrame):
    """Run DTW using close price"""
    norm_target = normalize_window(target.close, target.close[-1])
    norm_window = normalize_window(window.close, window.close[-1])
    return dtw(norm_target, norm_window)


def dtw_high(target: pd.DataFrame, window: pd.DataFrame):
    """Run DTW using high price"""
    norm_target = normalize_window(target.high, target.close[-1])
    norm_window = normalize_window(window.high, window.close[-1])
    return dtw(norm_target, norm_window)


def dtw_low(target: pd.DataFrame, window: pd.DataFrame):
    """Run DTW using low price"""
    norm_target = normalize_window(target.low, target.close[-1])
    norm_window = normalize_window(window.low, window.close[-1])
    return dtw(norm_target, norm_window)


def get_window(data: pd.DataFrame, window_start_time: time, window_size_days: int,
               window_end: datetime) -> pd.DataFrame:
    """Get data starting n days back from window_end and beginning at window_start_time"""

    # Convert the data index into a list of dates, removing duplicates
    dates = np.unique(data.index.date)
    idx = np.searchsorted(dates, window_end.date())

    if idx >= window_size_days:
        window_start = datetime.combine(dates[idx - window_size_days], window_start_time)
        window_start = EST.localize(window_start)
        indexer = data.index.get_indexer([window_start], method='nearest', tolerance=window_boundary_tolerance)

        if not indexer or indexer[0] == -1:
            nearest = data.index.get_indexer([window_start], method='nearest')
            print(f"Can't load window starting at {window_start}. indexer was {indexer}. nearest was {nearest}.")
            return None
        else:
            window_start = data.index[indexer[0]]
            window = data.loc[window_start:window_end]
            # print(f"get_window: Loaded window starting at {window_start}. indexer was {indexer}. head:")
            # print(window.head())
            return window
    else:
        print(f"Can't load window ending at {window_end}. Date index for start was {idx}.")
        return None


def find_similar_windows(data: pd.DataFrame, window_time_start: time, window_size_days: int, target_end: datetime,
                         strategy: Strategy) -> list[MatchModel]:
    """Find similar windows to the last using the provided strategy.

    Each window is size window_size_days and begins at the same time of day.
    Using the window ending at target_end, find all similar windows occurring before.
    """
    target_window: pd.DataFrame = get_window(data, window_time_start, window_size_days, target_end)
    if target_window is None:
        raise Exception('Can''t load target window')

    print(f'Using target window {target_window.index[0]}-{target_window.index[-1]}')
    print(f'Searching for windows of length {window_size_days} days ending at time {target_end.time()}')
    idxs = data.index.indexer_at_time(target_end.time())

    matches = []
    success = 0
    fail = 0
    for i in idxs:
        window_end = data.index[i]
        window = get_window(data, window_time_start, window_size_days, window_end)
        if window is None:
            fail += 1
            continue
        try:
            score = strategy(target_window, window)
        except Exception as e:
            print(f'Error calculating score: {e}')
            fail += 1
            continue
        score = strategy(target_window, window)
        matches.append(MatchModel(window.index[0], window.index[-1], score))
        success += 1
    print(f'Successfully processed {success} matches, with {fail} failures.')
    return matches


def least_distance(matches: list[MatchModel], top: int = 0):
    """Return the top matches by least distance (score), or all if top is 0"""
    # Sort ascending
    if not top:
        return sorted(matches, key=lambda match: match.score)
    else:
        return sorted(matches, key=lambda match: match.score)[:top]


# def highest_score(matches: list[MatchModel], top: int = 0):
#     # Sort descending
#     if not top:
#         return sorted(matches, key=lambda match: match.score, reverse=True)
#     else:
#         return sorted(matches, key=lambda match: match.score, reverse=True)[:top]


def find_similar_dtw_hlc4(data: pd.DataFrame, window_time_start: time, window_size_days: int, target_end: datetime,
                          top: int = None) -> list[MatchModel]:
    """Find similar windows using DTW on hlc4"""
    matches = find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_hlc4)
    return least_distance(matches, top)


def find_similar_dtw_high_low_1(data: pd.DataFrame, window_time_start: time, window_size_days: int,
                                target_end: datetime, top: int = None) -> list[MatchModel]:
    """Find matches using average distance of DTW on high and low. Filter to results that are top matches for both."""
    matches_high = find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_high)
    matches_low = find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_low)

    # Select the top from the intermediate results, only use results that are in both top results.
    intermediate_top_size = int(len(matches_high) / 5)
    matches_high = least_distance(matches_high, intermediate_top_size)
    matches_low = least_distance(matches_low, intermediate_top_size)

    matches = []
    for match_high in matches_high:
        for match_low in matches_low:
            if match_high.end.date() == match_low.end.date():
                score = (match_high.score + match_low.score) / 2
                matches.append(MatchModel(match_high.start, match_high.end, score))
    return least_distance(matches, top)


def find_similar_dtw_high_low_2(data: pd.DataFrame, window_time_start: time, window_size_days: int,
                                target_end: datetime, top: int = None) -> list[MatchModel]:
    """Find matches using average distance of DTW on high and low."""
    matches_high = find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_high)
    matches_low = find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_low)

    lookup_low = {match.end: match for match in matches_low}
    matches = []
    for match_high in matches_high:
        score = (match_high.score + lookup_low[match_high.end].score) / 2
        matches.append(MatchModel(match_high.start, match_high.end, score))
    return least_distance(matches, top)


def find_similar_dtw_high_low_close_4(data: pd.DataFrame, window_time_start: time, window_size_days: int,
                                      target_end: datetime, top: int = None) -> list[MatchModel]:
    """Find matches using average distance of DTW on high, low, and close. Assign 2x weight to close.

    The difference from this and find_similar_dtw_hlc4 is that this method runs DTW separately on each feature.
    """
    matches_high = find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_high)
    matches_low = find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_low)
    matches_close = find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_close)

    matches = []
    lookup_high = {match.end: match for match in matches_high}
    lookup_low = {match.end: match for match in matches_low}
    for match_close in matches_close:
        score = (lookup_high[match_close.end].score + lookup_low[match_close.end].score + match_close.score * 2) / 4
        matches.append(MatchModel(match_close.start, match_close.end, score))
    return least_distance(matches, top)
