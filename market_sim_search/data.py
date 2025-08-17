from pathlib import Path

from loguru import logger
import pandas as pd

from market_sim_search.config import EST


def load_csv(input_file: Path, tz=EST, dedupe: bool = True) -> pd.DataFrame:
    """Load a CSV file from disk"""
    df = pd.read_csv(input_file, compression='zip', parse_dates=['ts_event'], index_col='ts_event',
                     date_format='ISO8601')
    if tz:
        df.index = df.index.tz_convert(tz)
    df.index.rename('time', inplace=True)
    logger.info(f"Loaded {len(df)} rows from {input_file}")

    if dedupe:
        logger.info(f'Found {df.index.duplicated().sum()} duplicates, dropping.')
        df = df[~df.index.duplicated()]

    df.dropna(inplace=True)
    df = df.between_time('04:00', '17:00')
    return df


def resample(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Resample a DataFrame to a new frequency"""
    df = df.resample(freq).agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
    df.dropna(inplace=True)
    return df
