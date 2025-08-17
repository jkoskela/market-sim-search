from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from pandas import DataFrame

# A match with start and end timestamps and a score.
# The score is a float value representing the distance, so smaller is better.
MatchModel = namedtuple('MatchModel', ['start', 'end', 'score'])


# Contains the matched price data and the data immediately following. The data following the match may be historical
# data, or it may be generated data (a real projection). But we refer to them both as projections. The projection start
# should usually be immediately following the match_end.
@dataclass
class WindowMatch:
    window: DataFrame
    match_end: datetime
    projection_start: datetime
    score: float = -1

    def __getstate__(self):
        # Convert DataFrame to JSON string
        state = dict()
        state['window'] = self.window.to_json()
        state['match_end'] = self.match_end.isoformat()
        state['projection_start'] = self.projection_start.isoformat()
        state['score'] = self.score
        return state

    def __setstate__(self, state):
        # Convert JSON string back to DataFrame
        self.window = pd.read_json(state['window'])
        self.match_end = datetime.fromisoformat(state['match_end'])
        self.projection_start = datetime.fromisoformat(state['projection_start'])
        self.score = int(state['score'])

    def __hash__(self):
        return hash((self.match_end, self.projection_start))
