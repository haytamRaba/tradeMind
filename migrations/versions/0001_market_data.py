"""Create stock and historical OHLCV tables."""

from alembic import op
import sqlalchemy as sa

revision = "0001_market_data"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stocks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=12), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("exchange", sa.String(length=16), nullable=False),
        sa.Column("sector", sa.String(length=64), nullable=False),
        sa.Column("market_cap", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("country", sa.String(length=32), nullable=False),
        sa.Column("update_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_stocks"),
    )
    op.create_index("ix_stocks_symbol", "stocks", ["symbol"], unique=True)
    op.create_table(
        "historical_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["stock_id"], ["stocks.id"], name="fk_historical_prices_stock_id_stocks", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_historical_prices"),
        sa.UniqueConstraint("stock_id", "timestamp", name="uq_stock_timestamp"),
        sa.CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0",
            name="ck_historical_prices_positive_prices",
        ),
        sa.CheckConstraint(
            "low <= open AND low <= close AND open <= high AND close <= high",
            name="ck_historical_prices_valid_ohlc_range",
        ),
        sa.CheckConstraint("volume >= 0", name="ck_historical_prices_non_negative_volume"),
    )
    op.create_index("ix_historical_prices_stock_id", "historical_prices", ["stock_id"])
    op.create_index("ix_historical_prices_timestamp", "historical_prices", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_historical_prices_timestamp", table_name="historical_prices")
    op.drop_index("ix_historical_prices_stock_id", table_name="historical_prices")
    op.drop_table("historical_prices")
    op.drop_index("ix_stocks_symbol", table_name="stocks")
    op.drop_table("stocks")
