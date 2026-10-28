"""bases d'apprentissage : questions a l'assistant, expressions apprises, lectures des tickets

Revision ID: b3e8d1f4a6c2
Revises: a1f7c3d9e2b4
Create Date: 2026-10-28 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3e8d1f4a6c2'
down_revision: Union[str, None] = 'a1f7c3d9e2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('questions',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('quand', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('texte', sa.String(500), nullable=False),
                    sa.Column('cle', sa.String(500), nullable=False),
                    sa.Column('langue', sa.String(2), nullable=False),
                    sa.Column('zone_lat', sa.Float(), nullable=True),
                    sa.Column('zone_lon', sa.Float(), nullable=True),
                    sa.Column('ville', sa.String(80), nullable=True),
                    sa.Column('moteur', sa.String(10), nullable=False),
                    sa.Column('intention', sa.String(30), nullable=True),
                    sa.Column('parametres', sa.JSON(), nullable=True),
                    sa.Column('etapes', sa.JSON(), nullable=True),
                    sa.Column('resultats', sa.JSON(), nullable=True),
                    sa.Column('reponse', sa.Text(), nullable=True),
                    sa.Column('trouve', sa.Boolean(), nullable=False),
                    sa.Column('erreur', sa.String(300), nullable=True),
                    sa.Column('recherches_web', sa.Integer(), nullable=False),
                    sa.Column('sources', sa.JSON(), nullable=True),
                    sa.Column('modele', sa.String(40), nullable=True),
                    sa.Column('consignes', sa.String(20), nullable=True),
                    sa.Column('tokens_entree', sa.Integer(), nullable=False),
                    sa.Column('tokens_sortie', sa.Integer(), nullable=False),
                    sa.Column('cout_usd', sa.Float(), nullable=False),
                    sa.Column('duree_ms', sa.Integer(), nullable=False),
                    sa.Column('note', sa.Integer(), nullable=True),
                    sa.Column('commentaire', sa.String(1000), nullable=True),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_questions_user_id', 'questions', ['user_id'])
    op.create_index('ix_questions_quand', 'questions', ['quand'])
    op.create_index('ix_questions_cle', 'questions', ['cle'])
    op.create_index('ix_questions_intention', 'questions', ['intention'])
    op.create_table('expressions_apprises',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('cle', sa.String(500), nullable=False),
                    sa.Column('intention', sa.String(30), nullable=False),
                    sa.Column('parametres', sa.JSON(), nullable=False),
                    sa.Column('appris_le', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('utilisee', sa.Integer(), nullable=False),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_expressions_apprises_cle', 'expressions_apprises', ['cle'], unique=True)
    op.create_table('lectures_tickets',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('receipt_id', sa.Integer(), sa.ForeignKey('receipts.id', ondelete='CASCADE'),
                              nullable=True),
                    sa.Column('quand', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('source', sa.String(5), nullable=False),
                    sa.Column('media_type', sa.String(40), nullable=True),
                    sa.Column('nb_fichiers', sa.Integer(), nullable=False),
                    sa.Column('taille_octets', sa.Integer(), nullable=False),
                    sa.Column('largeur', sa.Integer(), nullable=True),
                    sa.Column('hauteur', sa.Integer(), nullable=True),
                    sa.Column('fichier_chemin', sa.String(300), nullable=True),
                    sa.Column('methode', sa.String(10), nullable=True),
                    sa.Column('modele', sa.String(40), nullable=True),
                    sa.Column('resultat', sa.String(10), nullable=False),
                    sa.Column('message', sa.String(300), nullable=True),
                    sa.Column('duree_ms', sa.Integer(), nullable=False),
                    sa.Column('tokens_entree', sa.Integer(), nullable=False),
                    sa.Column('tokens_sortie', sa.Integer(), nullable=False),
                    sa.Column('cout_usd', sa.Float(), nullable=False),
                    sa.Column('enseigne', sa.String(60), nullable=True),
                    sa.Column('nb_articles', sa.Integer(), nullable=False),
                    sa.Column('nb_illisibles', sa.Integer(), nullable=False),
                    sa.Column('ecart', sa.Float(), nullable=True),
                    sa.Column('lu', sa.JSON(), nullable=True),
                    sa.Column('corrige', sa.JSON(), nullable=True),
                    sa.Column('nb_corrections', sa.Integer(), nullable=False),
                    sa.Column('corrige_le', sa.DateTime(timezone=True), nullable=True),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_lectures_tickets_user_id', 'lectures_tickets', ['user_id'])
    op.create_index('ix_lectures_tickets_receipt_id', 'lectures_tickets', ['receipt_id'])
    op.create_index('ix_lectures_tickets_quand', 'lectures_tickets', ['quand'])
    op.create_index('ix_lectures_tickets_resultat', 'lectures_tickets', ['resultat'])


def downgrade() -> None:
    op.drop_table('lectures_tickets')
    op.drop_table('expressions_apprises')
    op.drop_table('questions')
