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
from datetime import datetime, date


class Database:
    def __init__(self):
        # La base est stockée dans le même dossier que le script
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'budget.db')
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Accès aux colonnes par nom
        self.cursor = self.conn.cursor()
        self._create_tables()
        self._insert_default_categories()
    
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
        for name, type_, icon, color, limit in defaults:
            try:
                self.cursor.execute(
                    '''INSERT INTO categories (name, type, icon, color, budget_limit)
                       VALUES (?, ?, ?, ?, ?)''',
                    (name, type_, icon, color, limit)
                )
            except sqlite3.IntegrityError:
                pass  # Existe déjà
        self.conn.commit()
    
    # ==================== TRANSACTIONS ====================
    
    def add_transaction(self, amount, category_id, date_str, description='', is_recurring=False):
        """Ajoute une transaction. Retourne son id."""
        self.cursor.execute('''
            INSERT INTO transactions (amount, category_id, date, description, is_recurring)
            VALUES (?, ?, ?, ?, ?)
        ''', (amount, category_id, date_str, description, 1 if is_recurring else 0))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def delete_transaction(self, transaction_id):
        """Supprime une transaction et son historique de validation récurrente."""
        self.cursor.execute('DELETE FROM recurring_validations WHERE transaction_id = ?',
                            (transaction_id,))
        self.cursor.execute('DELETE FROM transactions WHERE id = ?', (transaction_id,))
        self.conn.commit()
    
    def get_transactions(self, year=None, month=None):
        """Retourne les transactions, éventuellement filtrées par mois."""
        query = '''
            SELECT t.id, t.amount, t.date, t.description, t.is_recurring,
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
        return self.cursor.fetchone()[0]
    
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
        return row[0], row[1]
    
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
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_category_spending_for_category(self, category_id, year, month):
        """Dépense totale d'une catégorie précise pour un mois."""
        self.cursor.execute('''
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE category_id = ?
              AND strftime('%Y', date) = ?
              AND strftime('%m', date) = ?
        ''', (category_id, str(year), f'{month:02d}'))
        return self.cursor.fetchone()[0]
    
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
        self.cursor.execute('''
            INSERT INTO categories (name, type, icon, color, budget_limit)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, type_, icon, color, budget_limit))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def update_category(self, category_id, name, icon, color, budget_limit):
        """Met à jour une catégorie (y compris sa limite de budget)."""
        self.cursor.execute('''
            UPDATE categories 
            SET name = ?, icon = ?, color = ?, budget_limit = ?
            WHERE id = ?
        ''', (name, icon, color, budget_limit, category_id))
        self.conn.commit()
    
    def delete_category(self, category_id):
        """
        Supprime une catégorie en transférant ses transactions vers 'Divers'.
        La catégorie 'Divers' est protégée et ne peut pas être supprimée.
        """
        # Récupérer l'id de 'Divers'
        self.cursor.execute("SELECT id FROM categories WHERE name = 'Divers'")
        row = self.cursor.fetchone()
        if not row:
            return False
        divers_id = row[0]
        
        if category_id == divers_id:
            return False  # Catégorie protégée
        
        # Transférer les transactions
        self.cursor.execute(
            'UPDATE transactions SET category_id = ? WHERE category_id = ?',
            (divers_id, category_id)
        )
        # Supprimer la catégorie
        self.cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        self.conn.commit()
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
              AND t.id NOT IN (
                  SELECT transaction_id FROM recurring_validations
                  WHERE year = ? AND month = ?
              )
            ORDER BY c.type, c.name
        ''', (year, month))
        return [dict(row) for row in self.cursor.fetchall()]
    
    def validate_recurring(self, transaction_id, year, month):
        """
        Valide une récurrente pour un mois : crée une copie datée du 1er du mois
        et enregistre la validation pour éviter les doublons.
        """
        # Récupérer la transaction originale
        self.cursor.execute('SELECT * FROM transactions WHERE id = ?', (transaction_id,))
        original = self.cursor.fetchone()
        if not original:
            return False
        
        # Créer une copie datée du 1er du mois
        new_date = f'{year}-{month:02d}-01'
        self.cursor.execute('''
            INSERT INTO transactions (amount, category_id, date, description, is_recurring)
            VALUES (?, ?, ?, ?, 0)
        ''', (original['amount'], original['category_id'], new_date, original['description']))
        new_id = self.cursor.lastrowid
        
        # Enregistrer la validation (anti-doublon)
        try:
            self.cursor.execute('''
                INSERT INTO recurring_validations (transaction_id, year, month, validated)
                VALUES (?, ?, ?, 1)
            ''', (transaction_id, year, month))
        except sqlite3.IntegrityError:
            # Doublon détecté : annuler la création
            self.cursor.execute('DELETE FROM transactions WHERE id = ?', (new_id,))
            self.conn.rollback()
            return False
        
        self.conn.commit()
        return True
    
    def ignore_recurring(self, transaction_id, year, month):
        """Marque une récurrente comme ignorée pour un mois (ne la crée pas)."""
        try:
            self.cursor.execute('''
                INSERT INTO recurring_validations (transaction_id, year, month, validated)
                VALUES (?, ?, ?, 0)
            ''', (transaction_id, year, month))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    # ==================== EXPORT ====================
    
    def export_to_csv(self, filepath):
        """Exporte toutes les transactions vers un fichier CSV."""
        import csv
        self.cursor.execute('''
            SELECT t.date, c.name, c.type, t.amount, t.description
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.is_recurring = 0
            ORDER BY t.date DESC
        ''')
        rows = self.cursor.fetchall()
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Catégorie', 'Type', 'Montant', 'Description'])
            for row in rows:
                writer.writerow(row)
        return len(rows)
    
    def close(self):
        self.conn.close()


# Instance globale unique
db = Database()