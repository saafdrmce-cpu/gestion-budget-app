# -*- coding: utf-8 -*-
"""
Created on Mon Oct 26 12:18:59 2026

@author: drmcesaaf
"""

"""
Gestion de la base de données SQLite pour l'application de budget.
Toutes les transactions et catégories sont stockées localement.
"""

import sqlite3
import os
from contextlib import closing
from pathlib import Path
from tempfile import NamedTemporaryFile
from datetime import datetime, date


def budget_path():
    legacy = Path(__file__).resolve().with_name("budget.db")
    if "ANDROID_ARGUMENT" not in os.environ:
        return legacy
    from android.storage import app_storage_path
    target = Path(app_storage_path()) / "budget.db"
    snapshot = target.parent / "budget-migration" / "budget.db"
    if snapshot.is_file():
        legacy = snapshot
    if not target.exists() and legacy.is_file():
        # SQLite backup includes committed WAL entries; publish only a complete copy.
        with NamedTemporaryFile(dir=target.parent, delete=False) as temp:
            staging = Path(temp.name)
        try:
            with closing(sqlite3.connect(legacy.as_uri() + ("?mode=rw" if legacy == snapshot else "?mode=ro"), uri=True)) as source:
                with closing(sqlite3.connect(str(staging))) as dest:
                    source.backup(dest)
                    if dest.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise sqlite3.DatabaseError("La copie de l’ancienne base est invalide.")
            if not target.exists():
                os.replace(staging, target)
        finally:
            staging.unlink(missing_ok=True)
    return target


def _clean_money(value):
    """Arrondit un montant à 2 décimales en évitant -0.0."""
    rounded = round(float(value or 0.0), 2)
    return 0.0 if rounded == 0.0 else rounded


class Database:
    def __init__(self, db_path=None):
        self.conn = sqlite3.connect(db_path or budget_path(), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Accès aux colonnes par nom
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.conn.cursor()
        self._create_tables()
        with self.conn:
            self.conn.execute("BEGIN IMMEDIATE")
            if self.conn.execute("PRAGMA user_version").fetchone()[0] == 0:
                self._migrate_budget()
    
    def _create_tables(self):
        """Crée les 3 tables nécessaires si elles n'existent pas."""
        
        # Table des catégories (enveloppes budgétaires)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL CHECK(type IN ('depense', 'revenu')),
                icon TEXT DEFAULT '📦',
                color TEXT DEFAULT '#808080',
                budget_limit REAL DEFAULT 0.0
            )
        ''')
        
        # Table des transactions
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL CHECK(amount > 0),
                category_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                description TEXT DEFAULT '',
                is_recurring INTEGER DEFAULT 0,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            )
        ''')
        
        # Table de suivi des récurrents (anti-doublon)
        # Enregistre quelle transaction récurrente a été validée pour quel mois
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS recurring_validations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                validated INTEGER DEFAULT 1,
                FOREIGN KEY (transaction_id) REFERENCES transactions(id),
                UNIQUE(transaction_id, year, month)
            )
        ''')
        
        # Index pour accélérer les requêtes par date et catégorie
        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_transactions_date 
            ON transactions(date)
        ''')
        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_transactions_category 
            ON transactions(category_id)
        ''')
        
        self.conn.commit()
    
    def _insert_default_categories(self):
        """Insère les catégories par défaut au premier lancement."""
        defaults = [
            ('Alimentation', 'depense', '🍔', '#FF6B6B', 300.0),
            ('Transport',    'depense', '🚗', '#4ECDC4', 150.0),
            ('Loisirs',      'depense', '🎮', '#95E1D3', 100.0),
            ('Courses',      'depense', '🛒', '#F39C12', 0.0),
            ('Logement',     'depense', '🏠', '#3498DB', 700.0),
            ('Salaire',      'revenu',  '💰', '#2ECC71', 0.0),
            ('Divers',       'depense', '📦', '#95A5A6', 0.0),
        ]
        self.conn.executemany(
            "INSERT INTO categories (name, type, icon, color, budget_limit) VALUES (?, ?, ?, ?, ?)",
            defaults
        )

    def _migrate_budget(self):
        if not self.conn.execute("SELECT 1 FROM categories LIMIT 1").fetchone():
            self._insert_default_categories()
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(categories)")}
        if "fallback" not in columns:
            self.conn.execute("ALTER TABLE categories ADD COLUMN fallback INTEGER NOT NULL DEFAULT 0")
        for kind, base in (("depense", "Divers"), ("revenu", "Autres revenus")):
            name = base
            suffix = 1
            while True:
                row = self.conn.execute("SELECT type FROM categories WHERE name=?", (name,)).fetchone()
                if row is None:
                    self.conn.execute("INSERT INTO categories(name,type) VALUES (?,?)", (name, kind))
                    break
                if row[0] == kind:
                    break
                suffix += 1
                name = f"{base} ({suffix})"
            self.conn.execute("UPDATE categories SET fallback=1 WHERE name=?", (name,))
        for row in self.conn.execute("SELECT id,date FROM transactions").fetchall():
            try:
                normalized = datetime.strptime(row["date"], "%Y-%m-%d").date().isoformat()
            except ValueError:
                continue
            if normalized != row["date"]:
                self.conn.execute("UPDATE transactions SET date=? WHERE id=?", (normalized, row["id"]))
        self.conn.execute("PRAGMA user_version=1")

    # ==================== TRANSACTIONS ====================
    
    def add_transaction(self, amount, category_id, date_str, description='', is_recurring=False):
        """Ajoute une transaction. Retourne son id."""
        date_str = datetime.strptime(date_str, '%Y-%m-%d').date().isoformat()
        self.cursor.execute('''
            INSERT INTO transactions (amount, category_id, date, description, is_recurring)
            VALUES (?, ?, ?, ?, ?)
        ''', (amount, category_id, date_str, description, 1 if is_recurring else 0))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def update_transaction(self, transaction_id, amount, category_id, date_str, description, is_recurring):
        date_str = datetime.strptime(date_str, "%Y-%m-%d").date().isoformat()
        with self.conn:
            self.conn.execute(
                "UPDATE transactions SET amount=?, category_id=?, date=?, description=?, is_recurring=? WHERE id=?",
                (amount, category_id, date_str, description, int(is_recurring), transaction_id)
            )

    def delete_transaction(self, transaction_id):
        """Supprime une transaction et son historique de validation récurrente."""
        with self.conn:
            self.conn.execute('DELETE FROM recurring_validations WHERE transaction_id = ?',
                              (transaction_id,))
            self.conn.execute('DELETE FROM transactions WHERE id = ?', (transaction_id,))

    def reset_transactions(self):
        """Supprime toutes les transactions et validations récurrentes en conservant les catégories."""
        with self.conn:
            self.conn.execute('DELETE FROM recurring_validations')
            self.conn.execute('DELETE FROM transactions')
    
    def get_transactions(self, year=None, month=None):
        """Retourne les transactions, éventuellement filtrées par mois."""
        query = '''
            SELECT t.id, t.category_id, t.amount, t.date, t.description, t.is_recurring,
                   c.name AS category_name, c.icon, c.color, c.type
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
        '''
        params = []
        if year is not None and month is not None:
            query += '''
                WHERE strftime('%Y', t.date) = ? 
                  AND strftime('%m', t.date) = ?
            '''
            params = [str(year), f'{month:02d}']
        query += ' ORDER BY t.date DESC, t.id DESC'
        self.cursor.execute(query, params)
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_last_transactions(self, limit=5):
        """Retourne les N dernières transactions (pour le dashboard)."""
        self.cursor.execute('''
            SELECT t.id, t.amount, t.date, t.description,
                   c.name AS category_name, c.icon, c.color, c.type
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            ORDER BY t.date DESC, t.id DESC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in self.cursor.fetchall()]
    
    # ==================== CALCULS ====================
    
    def get_global_balance(self):
        """Solde global = total revenus - total dépenses (tout l'historique)."""
        self.cursor.execute('''
            SELECT 
                COALESCE(SUM(CASE WHEN c.type = 'revenu' THEN t.amount ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN c.type = 'depense' THEN t.amount ELSE 0 END), 0)
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
        ''')
        return _clean_money(self.cursor.fetchone()[0])
    
    def get_monthly_totals(self, year, month):
        """Retourne (total_revenus, total_depenses) pour un mois donné."""
        self.cursor.execute('''
            SELECT 
                COALESCE(SUM(CASE WHEN c.type = 'revenu' THEN t.amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN c.type = 'depense' THEN t.amount ELSE 0 END), 0)
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE strftime('%Y', t.date) = ? AND strftime('%m', t.date) = ?
        ''', (str(year), f'{month:02d}'))
        row = self.cursor.fetchone()
        return _clean_money(row[0]), _clean_money(row[1])
    
    def get_category_spending(self, year, month):
        """Retourne la liste des dépenses par catégorie pour un mois, avec budget."""
        self.cursor.execute('''
            SELECT c.id, c.name, c.icon, c.color, c.budget_limit,
                   COALESCE(SUM(t.amount), 0) AS spent
            FROM categories c
            LEFT JOIN transactions t 
                ON t.category_id = c.id 
                AND strftime('%Y', t.date) = ? 
                AND strftime('%m', t.date) = ?
            WHERE c.type = 'depense'
            GROUP BY c.id
            ORDER BY spent DESC
        ''', (str(year), f'{month:02d}'))
        rows = []
        for row in self.cursor.fetchall():
            item = dict(row)
            item['spent'] = _clean_money(item['spent'])
            rows.append(item)
        return rows
    
    def get_category_spending_for_category(self, category_id, year, month):
        """Dépense totale d'une catégorie précise pour un mois."""
        self.cursor.execute('''
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE category_id = ?
              AND strftime('%Y', date) = ?
              AND strftime('%m', date) = ?
        ''', (category_id, str(year), f'{month:02d}'))
        return _clean_money(self.cursor.fetchone()[0])
    
    # ==================== CATÉGORIES ====================
    
    def get_categories(self, type_filter=None):
        """Retourne toutes les catégories, éventuellement filtrées par type."""
        if type_filter:
            self.cursor.execute('SELECT * FROM categories WHERE type = ? ORDER BY name',
                                (type_filter,))
        else:
            self.cursor.execute('SELECT * FROM categories ORDER BY type, name')
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_category_by_id(self, category_id):
        self.cursor.execute('SELECT * FROM categories WHERE id = ?', (category_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def add_category(self, name, type_, icon='📦', color='#808080', budget_limit=0.0):
        """Ajoute une catégorie. Retourne son id."""
        with self.conn:
            self.cursor.execute('''
                INSERT INTO categories (name, type, icon, color, budget_limit)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, type_, icon, color, budget_limit))
        return self.cursor.lastrowid
    
    def update_category(self, category_id, name, icon, color, budget_limit):
        """Met à jour une catégorie (y compris sa limite de budget)."""
        with self.conn:
            self.cursor.execute('''
                UPDATE categories 
                SET name = ?, icon = ?, color = ?, budget_limit = ?
                WHERE id = ?
            ''', (name, icon, color, budget_limit, category_id))
    
    def delete_category(self, category_id):
        with self.conn:
            self.conn.execute("BEGIN IMMEDIATE")
            row = self.conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
            if not row or row["fallback"]:
                return False
            target = self.conn.execute(
                "SELECT id FROM categories WHERE type=? AND fallback=1", (row["type"],)
            ).fetchone()
            if not target:
                return False
            self.conn.execute("UPDATE transactions SET category_id=? WHERE category_id=?", (target[0], category_id))
            self.conn.execute("DELETE FROM categories WHERE id=?", (category_id,))
        return True

    # ==================== RÉCURRENTS ====================
    
    def get_recurring_transactions(self):
        """Retourne toutes les transactions marquées comme récurrentes."""
        self.cursor.execute('''
            SELECT t.id, t.amount, t.description,
                   c.name AS category_name, c.icon, c.type
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.is_recurring = 1
            ORDER BY c.type, c.name
        ''')
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_pending_recurrings(self, year, month):
        """
        Retourne les transactions récurrentes qui n'ont pas encore été
        validées OU ignorées pour le mois donné.
        """
        self.cursor.execute('''
            SELECT t.id, t.amount, t.description,
                   c.name AS category_name, c.icon, c.type
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.is_recurring = 1
              AND substr(t.date,1,7) < ?
              AND t.id NOT IN (
                  SELECT transaction_id FROM recurring_validations
                  WHERE year = ? AND month = ?
              )
            ORDER BY c.type, c.name
        ''', (date(year, month, 1).isoformat()[:7], year, month))
        return [dict(row) for row in self.cursor.fetchall()]
    
    def validate_recurring(self, transaction_id, year, month):
        """
        Valide une récurrente pour un mois : crée une copie datée du 1er du mois
        et enregistre la validation pour éviter les doublons.
        """
        new_date = date(year, month, 1).isoformat()
        with self.conn:
            self.conn.execute("BEGIN IMMEDIATE")
            original = self.conn.execute(
                "SELECT * FROM transactions WHERE id=? AND is_recurring=1 AND substr(date,1,7) < ?",
                (transaction_id, new_date[:7])
            ).fetchone()
            if not original:
                return False
            marker = self.conn.execute(
                "INSERT OR IGNORE INTO recurring_validations(transaction_id,year,month,validated) VALUES (?,?,?,1)",
                (transaction_id, year, month)
            )
            if not marker.rowcount:
                return False
            self.conn.execute(
                "INSERT INTO transactions(amount,category_id,date,description) VALUES (?,?,?,?)",
                (original["amount"], original["category_id"], new_date, original["description"])
            )
        return True

    def ignore_recurring(self, transaction_id, year, month):
        """Marque une récurrente comme ignorée pour un mois (ne la crée pas)."""
        with self.conn:
            marker = self.conn.execute(
                "INSERT OR IGNORE INTO recurring_validations(transaction_id,year,month,validated) VALUES (?,?,?,0)",
                (transaction_id, year, month)
            )
            return bool(marker.rowcount)

    # ==================== EXPORT ====================
    
    def export_to_csv(self, filepath):
        """Exporte toutes les transactions vers un fichier CSV."""
        with open(filepath, 'w', newline='', encoding='utf-8') as stream:
            return self.write_csv(stream)

    def write_csv(self, stream):
        import csv
        self.cursor.execute('''
            SELECT t.date, c.name, c.type, t.amount, t.description
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            ORDER BY t.date DESC
        ''')
        rows = self.cursor.fetchall()
        writer = csv.writer(stream)
        writer.writerow(['Date', 'Catégorie', 'Type', 'Montant', 'Description'])
        writer.writerows(rows)
        return len(rows)
    
    def close(self):
        self.conn.close()


# Instance globale unique
db = Database()