import pandas as pd
import traceback
from lightweight_charts import JupyterChart
from collections import namedtuple

from market_span_cluster.models import MatchModel, WindowMatch


def get_window_match(data: pd.DataFrame, match: MatchModel):
    """Return the dataframe slice associated with the model"""
    try:
        project_start_idx = data.index.get_loc(match.end) + 1
        project_start = data.index[project_start_idx]
        project_end = data.index.asof(match.end.replace(hour=23, minute=59, second=59))
        window = data.loc[match.start:match.end]
        project = data.loc[project_start:project_end]
        window = pd.concat([window, project])
        return WindowMatch(window, match.end, project_start, match.score)
    except Exception as e:
        print(f'Error getting window_match: {e}')
        traceback.print_exc()
        return None


def get_window_matches(data: pd.DataFrame, matches: list[MatchModel]):
    """Return the dataframe slices associated with the models"""
    window_matches = []
    for match in matches:
        window_match = get_window_match(data, match)
        if window_match is None:
            continue
        else:
            window_matches.append(window_match)
    return window_matches


def create_jupyter_chart(window_match: WindowMatch, show_projection: bool = True, width: int = 1200, height: int = 600) -> JupyterChart:
    """Plot candlestick chart from a WindowMatch, with an optional projection"""
    if pd.notna(window_match.match_end):
        chart = JupyterChart(width=width, height=height)
        data = window_match.window.copy()
        data.index = data.index.tz_localize(None)
        projection_start = window_match.projection_start.tz_localize(None)
        if not show_projection:
            chart.set(data.loc[:projection_start])  # Little leakage, should be non inclusive
        else:
            chart.set(data)
        chart.fit()
        chart.vertical_span(projection_start, color='#E8F2FD')
        return chart
    else:
        return None


def create_jupyter_chart_from_model(data: pd.DataFrame, match: MatchModel, show_projection: bool = True) -> JupyterChart:
    """Plot candlestick chart a dataframe and a match, with an optional projection"""
    window_match = get_window_match(data, match)
    return create_jupyter_chart(window_match, show_projection)


# def create_charts(window_matches: list[WindowMatch], width: int=1600, height: int=700):
#   charts = []
#   for projection in projections:
#     chart = create_chart(projection, width, height)
#     charts.append(chart)
#   return charts


def create_jupyter_chart_from_df(data: pd.DataFrame, width: int = 1600, height: int = 700) -> JupyterChart:
    """Plot candlestick chart from a dataframe."""
    chart = JupyterChart(width=width, height=height)
    data = data.copy()
    data.index = data.index.tz_localize(None)
    chart.set(data)
    chart.fit()
    chart.load()
    return chart
