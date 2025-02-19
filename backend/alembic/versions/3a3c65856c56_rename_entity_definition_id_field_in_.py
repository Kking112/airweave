"""rename entity_definition_id field in dagnode

Revision ID: 3a3c65856c56
Revises: a91009f29194
Create Date: 2025-02-18 11:23:33.903386

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3a3c65856c56"
down_revision = "a91009f29194"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("dag_node", sa.Column("entity_definition_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "dag_node_entity_definition_id_fkey",
        "dag_node",
        "entity_definition",
        ["entity_definition_id"],
        ["id"],
    )
    op.drop_column("dag_node", "entity_id")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("dag_node", sa.Column("entity_id", sa.UUID(), autoincrement=False, nullable=True))
    op.create_foreign_key(
        "dag_node_entity_id_fkey", "dag_node", "entity_definition", ["entity_id"], ["id"]
    )
    op.drop_column("dag_node", "entity_definition_id")
    # ### end Alembic commands ###
