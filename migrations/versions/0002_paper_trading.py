"""Add the simulated portfolio, positions, and order ledger."""

from alembic import op
import sqlalchemy as sa

revision = "0002_paper_trading"
down_revision = "0001_market_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_portfolios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=48), nullable=False),
        sa.Column("starting_cash", sa.Numeric(20, 4), nullable=False),
        sa.Column("cash", sa.Numeric(20, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("starting_cash > 0", name="positive_starting_cash"),
        sa.CheckConstraint("cash >= 0", name="non_negative_cash"),
        sa.PrimaryKeyConstraint("id", name="pk_paper_portfolios"),
        sa.UniqueConstraint("name", name="uq_paper_portfolios_name"),
    )
    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("average_entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("stop_loss", sa.Numeric(20, 8), nullable=False),
        sa.Column("take_profit", sa.Numeric(20, 8), nullable=True),
        sa.CheckConstraint("quantity > 0", name="positive_position_quantity"),
        sa.CheckConstraint("average_entry_price > 0", name="positive_position_price"),
        sa.CheckConstraint("stop_loss > 0", name="positive_position_stop"),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["paper_portfolios.id"],
            name="fk_paper_positions_portfolio_id_paper_portfolios", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stock_id"], ["stocks.id"],
            name="fk_paper_positions_stock_id_stocks", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_paper_positions"),
        sa.UniqueConstraint("portfolio_id", "stock_id", name="uq_paper_position_stock"),
    )
    op.create_index("ix_paper_positions_portfolio_id", "paper_positions", ["portfolio_id"])
    op.create_index("ix_paper_positions_stock_id", "paper_positions", ["stock_id"])
    op.create_table(
        "paper_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("execution_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("stop_loss", sa.Numeric(20, 8), nullable=True),
        sa.Column("take_profit", sa.Numeric(20, 8), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(20, 4), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="valid_paper_order_side"),
        sa.CheckConstraint("status IN ('FILLED', 'REJECTED')", name="valid_paper_order_status"),
        sa.CheckConstraint("execution_price > 0", name="positive_paper_order_price"),
        sa.CheckConstraint("quantity >= 0", name="non_negative_paper_order_quantity"),
        sa.CheckConstraint(
            "status = 'REJECTED' OR quantity > 0", name="positive_filled_order_quantity"
        ),
        sa.CheckConstraint(
            "status = 'REJECTED' OR side = 'SELL' OR stop_loss IS NOT NULL",
            name="paper_buy_requires_stop",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["paper_portfolios.id"],
            name="fk_paper_orders_portfolio_id_paper_portfolios", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stock_id"], ["stocks.id"],
            name="fk_paper_orders_stock_id_stocks", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_paper_orders"),
        sa.UniqueConstraint("idempotency_key", name="uq_paper_orders_idempotency_key"),
    )
    op.create_index("ix_paper_orders_portfolio_id", "paper_orders", ["portfolio_id"])
    op.create_index("ix_paper_orders_stock_id", "paper_orders", ["stock_id"])
    op.create_index("ix_paper_orders_created_at", "paper_orders", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_paper_orders_created_at", table_name="paper_orders")
    op.drop_index("ix_paper_orders_stock_id", table_name="paper_orders")
    op.drop_index("ix_paper_orders_portfolio_id", table_name="paper_orders")
    op.drop_table("paper_orders")
    op.drop_index("ix_paper_positions_stock_id", table_name="paper_positions")
    op.drop_index("ix_paper_positions_portfolio_id", table_name="paper_positions")
    op.drop_table("paper_positions")
    op.drop_table("paper_portfolios")
