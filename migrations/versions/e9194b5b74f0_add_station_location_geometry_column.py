"""add station location geometry column

Revision ID: e9194b5b74f0
Revises: e1389df0c1dd
Create Date: 2026-07-08 12:35:24.396155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


# revision identifiers, used by Alembic.
revision: str = 'e9194b5b74f0'
down_revision: Union[str, Sequence[str], None] = 'e1389df0c1dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable first — a table with existing rows can't have a NOT NULL
    # column added with no default. Backfill, then tighten.
    # Note: geoalchemy2's Geometry type creates its own GiST index
    # automatically as a side effect of add_column (named idx_stations_location)
    # — an explicit op.create_index() here would try to create it twice.
    op.add_column(
        'stations',
        sa.Column('location', Geometry(geometry_type='POINT', srid=4326), nullable=True),
    )

    op.execute(
        "UPDATE stations SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) "
        "WHERE location IS NULL"
    )

    op.alter_column('stations', 'location', nullable=False)


def downgrade() -> None:
    op.drop_index('idx_stations_location', table_name='stations', postgresql_using='gist')
    op.drop_column('stations', 'location')
