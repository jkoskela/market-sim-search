from datetime import timedelta, time, datetime
from typing import Callable

import pandas as pd
import numpy as np
from tslearn.metrics import dtw
from loguru import logger

from market_span_cluster.config import EST
from market_span_cluster.models import MatchModel
from market_span_cluster.types import ProgressReporter

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
    norm_target = normalize_window(hlc4(target), target.close.iloc[-1])
    norm_window = normalize_window(hlc4(window), window.close.iloc[-1])
    return dtw(norm_target, norm_window)


def dtw_close(target: pd.DataFrame, window: pd.DataFrame):
    """Run DTW using close price"""
    norm_target = normalize_window(target.close, target.close.iloc[-1])
    norm_window = normalize_window(window.close, window.close.iloc[-1])
    return dtw(norm_target, norm_window)


def dtw_high(target: pd.DataFrame, window: pd.DataFrame):
    """Run DTW using high price"""
    norm_target = normalize_window(target.high, target.close.iloc[-1])
    norm_window = normalize_window(window.high, window.close.iloc[-1])
    return dtw(norm_target, norm_window)


def dtw_low(target: pd.DataFrame, window: pd.DataFrame):
    """Run DTW using low price"""
    norm_target = normalize_window(target.low, target.close.iloc[-1])
    norm_window = normalize_window(window.low, window.close.iloc[-1])
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
            logger.warning(f"Can't load window starting at {window_start}. indexer was {indexer}. nearest was {nearest}.")
            return None
        else:
            window_start = data.index[indexer[0]]
            window = data.loc[window_start:window_end]
            return window
    else:
        logger.warning(f"Can't load window ending at {window_end}. Date index for start was {idx}.")
        return None


def least_distance(matches: list[MatchModel], top: int = 0):
    """Return the top matches by least distance (score), or all if top is 0"""
    # Sort ascending
    if not top:
        return sorted(matches, key=lambda match: match.score)
    else:
        return sorted(matches, key=lambda match: match.score)[:top]


class StrategyRunner:
    def __init__(self, progress_reporter: ProgressReporter | None = None):
        self.progress_reporter = progress_reporter
        self.progress_count = 0
        self.max_progress_count = np.nan
        self.outer_loop_count = 0
        self.max_outer_loop_count = np.nan

    def find_similar_windows(self, data: pd.DataFrame, window_time_start: time, window_size_days: int,
                             target_end: datetime,
                             strategy: Strategy) -> list[MatchModel]:
        """Find similar windows to the last using the provided strategy.

        Each window is size window_size_days and begins at the same time of day.
        Using the window ending at target_end, find all similar windows occurring before.
        """
        target_window: pd.DataFrame = get_window(data, window_time_start, window_size_days, target_end)
        if target_window is None:
            raise Exception('Can''t load target window')

        logger.info(f'Using target window {target_window.index[0]}-{target_window.index[-1]}')
        logger.info(f'Searching for windows of length {window_size_days} days ending at time {target_end.time()}')
        idxs = data.index.indexer_at_time(target_end.time())

        matches = []
        success = 0
        fail = 0
        num_indices = len(idxs)
        if self.progress_reporter and np.isnan(self.max_progress_count):
            if np.isnan(self.max_outer_loop_count):
                raise ValueError("max_outer_loop_count wasn't initialized")

            # Assuming that num_indices is the same for each inner loop
            self.max_progress_count = num_indices * self.max_outer_loop_count

        for idx in idxs:
            if self.progress_reporter:
                self.progress_reporter(self.progress_count / float(self.max_progress_count))
                self.progress_count += 1

            window_end = data.index[idx]
            window = get_window(data, window_time_start, window_size_days, window_end)
            if window is None:
                fail += 1
                continue
            try:
                score = strategy(target_window, window)
            except Exception as e:
                logger.exception(f'Error calculating score')
                fail += 1
                continue
            matches.append(MatchModel(window.index[0], window.index[-1], score))
            success += 1

        logger.info(f'Successfully processed {success} matches, with {fail} failures.')
        return matches

    def find_similar_dtw_hlc4(self, data: pd.DataFrame, window_time_start: time, window_size_days: int,
                              target_end: datetime,
                              top: int = None) -> list[MatchModel]:
        """Find similar windows using DTW on hlc4"""
        matches = self.find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_hlc4)
        return least_distance(matches, top)

    def find_similar_dtw_high_low_1(self, data: pd.DataFrame, window_time_start: time, window_size_days: int,
                                    target_end: datetime, top: int = None) -> list[MatchModel]:
        """Find matches using average distance of DTW on high and low. Filter to results that are top matches for both."""
        matches_high = self.find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_high)
        matches_low = self.find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_low)

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

    def find_similar_dtw_high_low_2(self, data: pd.DataFrame, window_time_start: time, window_size_days: int,
                                    target_end: datetime, top: int = None) -> list[MatchModel]:
        """Find matches using average distance of DTW on high and low."""
        matches_high = self.find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_high)
        matches_low = self.find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_low)

        lookup_low = {match.end: match for match in matches_low}
        matches = []
        for match_high in matches_high:
            score = (match_high.score + lookup_low[match_high.end].score) / 2
            matches.append(MatchModel(match_high.start, match_high.end, score))
        return least_distance(matches, top)

    def find_similar_dtw_high_low_close_4(self, data: pd.DataFrame, window_time_start: time, window_size_days: int,
                                          target_end: datetime, top: int = None) -> list[MatchModel]:
        """Find matches using average distance of DTW on high, low, and close. Assign 2x weight to close.

        The difference from this and find_similar_dtw_hlc4 is that this method runs DTW separately on each feature.
        """
        self.max_outer_loop_count = 3
        matches_high = self.find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_high)
        matches_low = self.find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_low)
        matches_close = self.find_similar_windows(data, window_time_start, window_size_days, target_end, dtw_close)

        matches = []
        lookup_high = {match.end: match for match in matches_high}
        lookup_low = {match.end: match for match in matches_low}
        for match_close in matches_close:
            score = (lookup_high[match_close.end].score + lookup_low[match_close.end].score + match_close.score * 2) / 4
            matches.append(MatchModel(match_close.start, match_close.end, score))
        return least_distance(matches, top)
