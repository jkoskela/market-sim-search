import pandas as pd
import traceback
from lightweight_charts import JupyterChart, Chart, AbstractChart
from lightweight_charts.widgets import StreamlitChart
from plotly import graph_objects as go

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


def create_streamlit_chart(window_match: WindowMatch, show_projection: bool = True, width: int = 800,
                           height: int = 600) -> StreamlitChart | None:
    """Plot streamlit chart from a WindowMatch, with an optional projection"""
    if pd.notna(window_match.match_end):
        chart = StreamlitChart(width=width, height=height)
        create_chart_impl(chart, window_match, show_projection)
        return chart
    else:
        return None


def create_chart_impl(chart: AbstractChart, window_match: WindowMatch, show_projection: bool):
    data = window_match.window.copy()
    data.index = data.index.tz_localize(None)
    projection_start = window_match.projection_start.replace(tzinfo=None)
    if not show_projection:
        chart.set(data.loc[:projection_start])  # Little leakage, should be non inclusive
    else:
        chart.set(data)
    chart.fit()
    chart.vertical_span(projection_start, color='#E8F2FD')


def create_jupyter_chart(window_match: WindowMatch, show_projection: bool = True, width: int = 1200,
                         height: int = 600) -> JupyterChart | None:
    """Plot jupyter chart from a WindowMatch, with an optional projection"""
    if pd.notna(window_match.match_end):
        chart = JupyterChart(width=width, height=height)
        create_chart_impl(chart, window_match, show_projection)
        return chart
    else:
        return None


def create_jupyter_chart_from_model(data: pd.DataFrame, match: MatchModel,
                                    show_projection: bool = True) -> JupyterChart:
    """Plot candlestick chart a dataframe and a match, with an optional projection"""
    window_match = get_window_match(data, match)
    return create_jupyter_chart(window_match, show_projection)


def create_jupyter_chart_from_df(data: pd.DataFrame, width: int = 1600, height: int = 700) -> JupyterChart:
    """Plot candlestick chart from a dataframe."""
    chart = JupyterChart(width=width, height=height)
    data = data.copy()
    data.index = data.index.tz_localize(None)
    chart.set(data)
    chart.fit()
    chart.load()
    return chart


def create_candlestick_plotly_impl(match: WindowMatch, title=None):
    """Create a candlestick chart from OHLCV data"""
    df = match.window
    return go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name=title)


def create_candlestick_plotly(match: WindowMatch, title="Price Chart"):
    """Create a candlestick chart from OHLCV data"""
    fig = go.Figure(data=[create_candlestick_plotly_impl(match)])

    fig.update_layout(
        title=title,
        yaxis_title='Price',
        xaxis_title='Date',
        height=400,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig
