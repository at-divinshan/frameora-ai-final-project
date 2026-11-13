"""Migration/ORM parity checks; MySQL DDL is compiled, never executed."""
from pathlib import Path
import re
import unittest
from sqlalchemy import CheckConstraint, UniqueConstraint, create_engine
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from app.models.customer_project import CustomerProject
from app.models.ai_generation import AIGeneration
from app.models.share_link import ShareLink
from app.models.project_generation_phase import ProjectGenerationPhase as Phase, ShareLinkPhase


def normalize(sql):
    value = re.sub(r'\s+', ' ', sql.replace('`', '')).strip().lower()
    return re.sub(r'\binteger\b', 'int', value)


class PhaseSchemaTests(unittest.TestCase):
    def test_mysql_columns_constraints_and_engine_match_migration(self):
        sql = Path(__file__).resolve().parents[1].joinpath('migrations/010_project_generation_phases.sql').read_text()
        for model in (Phase, ShareLinkPhase):
            table = model.__table__
            source = normalize(sql.split(f'CREATE TABLE IF NOT EXISTS {table.name} (',1)[1].split(';',1)[0])
            compiled = normalize(str(CreateTable(table).compile(dialect=mysql.dialect())))
            self.assertEqual(table.dialect_options['mysql']['engine'], 'InnoDB')
            self.assertIn('engine=innodb', source)
            self.assertIn('engine=innodb', compiled)
            for column in table.columns:
                self.assertFalse(column.nullable)
                kind = 'datetime' if column.name == 'created_at' else 'int'
                fragment = f'{column.name} {kind} not null'
                self.assertIn(fragment, source)
                self.assertIn(fragment, compiled)
                self.assertIsNone(column.server_default)
            self.assertIn('id int not null auto_increment', source)
            self.assertIn('id int not null auto_increment', compiled)
            for constraint in table.constraints:
                if isinstance(constraint, UniqueConstraint):
                    fragment = f"constraint {constraint.name} unique ({', '.join(c.name for c in constraint.columns)})"
                elif isinstance(constraint, CheckConstraint):
                    fragment = f'constraint {constraint.name} check ({constraint.sqltext})'
                else:
                    continue
                self.assertIn(normalize(fragment), source)
                self.assertIn(normalize(fragment), compiled)
            for constraint in table.foreign_key_constraints:
                fk = next(iter(constraint.elements))
                target_table, target_column = fk.target_fullname.split('.')
                fragment = normalize(f'constraint {constraint.name} foreign key ({fk.parent.name}) references {target_table} ({target_column})')
                # Source SQL omits whitespace before referenced column parentheses.
                self.assertIn(fragment.replace(' (','('), source.replace(' (','('))
                self.assertIn(fragment.replace(' (','('), compiled.replace(' (','('))
                self.assertIsNone(constraint.ondelete)
                self.assertIsNone(constraint.onupdate)
        self.assertEqual({c.name for c in Phase.__table__.constraints if isinstance(c, CheckConstraint)}, {'chk_phase_positive'})

    def test_positive_phase_check_is_enforced_in_isolated_sqlite(self):
        engine = create_engine('sqlite://')
        try:
            Phase.__table__.create(engine)
            with engine.begin() as connection:
                from datetime import datetime
                for number in (0, -1):
                    with self.assertRaises(IntegrityError):
                        connection.execute(Phase.__table__.insert().values(project_id=1,generation_id=1,phase_number=number,created_at=datetime(2026,1,1)))
                connection.execute(Phase.__table__.insert().values(project_id=1,generation_id=1,phase_number=1,created_at=datetime(2026,1,1)))
        finally:
            engine.dispose()
