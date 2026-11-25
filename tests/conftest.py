from collections.abc import Iterator

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.models import Base


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def ohlcv_frame() -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=3, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "Open": [10.0, 11.0, 12.0],
            "High": [12.0, 13.0, 14.0],
            "Low": [9.0, 10.0, 11.0],
            "Close": [11.0, 12.0, 13.0],
            "Volume": [100, 110, 120],
        },
        index=index,
    )
