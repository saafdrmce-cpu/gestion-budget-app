"""
Application de gestion de budget personnel avec KivyMD.
Design Material Design professionnel avec icônes.
"""
import os
import re
from kivy.clock import mainthread
from kivy.utils import platform
import sqlite3
from kivy.metrics import dp
from datetime import date, datetime
from kivy.uix.screenmanager import SlideTransition

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDIconButton, MDFloatingActionButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import MDList, OneLineListItem, TwoLineListItem, ThreeLineListItem
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.toolbar import MDTopAppBar

from database import db


THEME_COLORS = {
    "green": (0.3, 0.7, 0.3, 1),
    "red": (0.95, 0.26, 0.21, 1),
    "orange": (1.0, 0.6, 0.0, 1),
    "blue": (0.13, 0.59, 0.95, 1),
}

MONTH_NAMES = [
    'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]


def _clean_money(value):
    rounded = round(float(value or 0.0), 2)
    return 0.0 if rounded == 0.0 else rounded


def format_mad(amount, signed=False):
    value = _clean_money(amount)
    if signed:
        sign = '+' if value >= 0 else '-'
    else:
        sign = '-' if value < 0 else ''
    return f'{sign}{abs(value):,.2f} MAD'.replace(',', ' ')


def format_amount_input(amount):
    value = _clean_money(amount)
    if value == int(value):
        return str(int(value))
    return f'{value:.2f}'


def parse_mad(text):
    value = text.strip()
    if not re.fullmatch(r"[0-9]+(?:[.,][0-9]{1,2})?", value):
        raise ValueError("Saisissez un montant avec au maximum deux décimales.")
    amount = float(value.replace(",", "."))
    if amount == float("inf"):
        raise ValueError("Montant trop élevé.")
    return amount

# ============================================================
# ÉCRAN 1 : TABLEAU DE BORD
# ============================================================

class DashboardScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        
        layout = MDBoxLayout(orientation='vertical', spacing=dp(10))
        
        # Barre d'application
        toolbar = MDTopAppBar(
            title="Gestion Budget",
            elevation=4
        )
        layout.add_widget(toolbar)
        
        # Contenu scrollable
        scroll = MDScrollView()
        content = MDBoxLayout(orientation='vertical', spacing=dp(15), padding=dp(15),
                              size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))
        
        # Carte Solde global
        balance = _clean_money(db.get_global_balance())
        
        balance_card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            height=dp(140),
            padding=dp(20),
            radius=[dp(12)],
            elevation=2
        )
        balance_card.add_widget(MDLabel(
            text='Solde Global',
            font_style='Subtitle1',
            theme_text_color='Secondary'
        ))
        balance_card.add_widget(MDLabel(
            text=format_mad(balance),
            font_style='H4',
            theme_text_color='Custom',
            text_color=MDApp.get_running_app().theme_cls.primary_color if balance >= 0 else THEME_COLORS["red"],
            bold=True,
            halign='center'
        ))
        content.add_widget(balance_card)
        
        # Carte Résumé du mois
        today = date.today()
        revenues, expenses = db.get_monthly_totals(today.year, today.month)
        remaining = _clean_money(revenues - expenses)
        month_label = f'{MONTH_NAMES[today.month - 1]} {today.year}'
        
        month_card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            height=dp(130),
            padding=dp(15),
            radius=[dp(12)],
            elevation=2
        )
        month_card.add_widget(MDLabel(
            text=month_label,
            font_style='Subtitle1',
            theme_text_color='Secondary'
        ))
        
        stats_row = MDBoxLayout(spacing=dp(10), size_hint_y=None, height=dp(60))
        for label, value, color in [
            ('Revenus', revenues, "green"),
            ('Dépenses', expenses, "red"),
            ('Reste', remaining, "blue" if remaining >= 0 else "red")
        ]:
            col = MDBoxLayout(orientation='vertical')
            col.add_widget(MDLabel(text=label, font_style='Caption', theme_text_color='Secondary'))
            col.add_widget(MDLabel(
                text=format_mad(value),
                font_style='Body1',
                theme_text_color='Custom',
                text_color=self._get_theme_color(color),
                bold=True,
                halign='center'
            ))
            stats_row.add_widget(col)
        month_card.add_widget(stats_row)
        content.add_widget(month_card)
        
        # Bannière des récurrents à valider
        pending = db.get_pending_recurrings(today.year, today.month)
        if pending:
            banner = MDRaisedButton(
                text=f'⚠️ {len(pending)} paiement(s) à valider',
                md_bg_color=THEME_COLORS["orange"],
                size_hint=(1, None),
                height=dp(50)
            )
            banner.bind(on_press=lambda x: self._show_recurring_dialog(pending))
            content.add_widget(banner)
        
        # Dernières transactions
        content.add_widget(MDLabel(
            text='Dernières transactions',
            font_style='Subtitle1',
            bold=True,
            size_hint_y=None,
            height=dp(28)
        ))
        
        last_txs = db.get_last_transactions(5)
        if not last_txs:
            content.add_widget(MDLabel(
                text='Aucune transaction.\nAppuyez sur + pour commencer.',
                theme_text_color='Secondary',
                halign='center',
                size_hint_y=None,
                height=dp(60)
            ))
        else:
            for tx in last_txs:
                color = "green" if tx['type'] == 'revenu' else "red"
                sign = '+' if tx['type'] == 'revenu' else '-'
                
                # Construire le texte secondaire : description + date
                if tx['description']:
                    secondary = f"{tx['description']}  •  {tx['date']}"
                else:
                    secondary = tx['date']
                
                item = ThreeLineListItem(
                    text=f"{tx['category_name']}",
                    secondary_text=secondary,
                    tertiary_text=f'{sign}{tx["amount"]:,.2f} MAD'.replace(',', ' '),
                    theme_text_color='Custom',
                    text_color=self._get_theme_color(color)
                )
                content.add_widget(item)
        
        history = MDRaisedButton(
            text="HISTORIQUE COMPLET",
            size_hint=(1, None),
            height=dp(44)
        )
        history.bind(on_release=lambda *_: self._open_history())
        content.add_widget(history)

        scroll.add_widget(content)
        layout.add_widget(scroll)
        
        # Bouton flottant +
        fab = MDFloatingActionButton(
            icon="plus",
            md_bg_color=MDApp.get_running_app().theme_cls.primary_color,
            pos_hint={'center_x': 0.5}
        )
        fab.bind(on_press=lambda x: self._open_add_screen())
        layout.add_widget(fab)
        
        self.add_widget(layout)
    
    def _get_theme_color(self, color_name):
        """Retourne la couleur RGBA pour un nom de couleur."""
        return THEME_COLORS.get(color_name, (0, 0, 0, 1))
    
    def _open_history(self):
        self.manager.transition = SlideTransition(direction='left')
        self.manager.current = 'history'

    def _open_add_screen(self):
        add_screen = self.manager.get_screen('add')
        add_screen.editing = None
        add_screen.return_screen = 'dashboard'
        self.manager.transition = SlideTransition(direction='up')
        self.manager.current = 'add'
    
    def _show_recurring_dialog(self, pending):
        """Affiche la dialog de validation des récurrents."""
        row_height = dp(64)
        scroll_height = min(dp(260), max(row_height, len(pending) * row_height))
        content = MDScrollView(size_hint_y=None, height=scroll_height)
        list_layout = MDBoxLayout(
            orientation='vertical',
            spacing=dp(6),
            size_hint_y=None
        )
        list_layout.bind(minimum_height=list_layout.setter('height'))
        
        for tx in pending:
            row = MDBoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(58),
                spacing=dp(6),
                padding=[dp(4), 0]
            )
            info = MDBoxLayout(orientation='vertical')
            info.add_widget(MDLabel(
                text=f"{tx['category_name']}",
                font_style='Body1',
                bold=True
            ))
            details = format_mad(tx['amount'])
            if tx['description']:
                details = f"{details}  •  {tx['description']}"
            info.add_widget(MDLabel(
                text=details,
                font_style='Caption',
                theme_text_color='Secondary'
            ))
            row.add_widget(info)

            validate_btn = MDIconButton(
                icon="check",
                theme_text_color="Custom",
                text_color=THEME_COLORS["green"]
            )
            validate_btn.bind(on_release=lambda x, t=tx: self._validate_one(t))
            row.add_widget(validate_btn)

            ignore_btn = MDIconButton(
                icon="close",
                theme_text_color="Custom",
                text_color=THEME_COLORS["red"]
            )
            ignore_btn.bind(on_release=lambda x, t=tx: self._ignore_one(t))
            row.add_widget(ignore_btn)

            list_layout.add_widget(row)
        
        content.add_widget(list_layout)
        
        self.dialog = MDDialog(
            title='Paiements à valider',
            type="custom",
            content_cls=content,
            buttons=[
                MDRaisedButton(
                    text="TOUT VALIDER",
                    md_bg_color=THEME_COLORS["green"],
                    on_release=lambda x: self._validate_all(pending)
                ),
                MDRaisedButton(
                    text="FERMER",
                    on_release=lambda x: self.dialog.dismiss()
                )
            ]
        )
        self.dialog.open()
    
    def _validate_one(self, tx):
        today = date.today()
        db.validate_recurring(tx['id'], today.year, today.month)
        self.dialog.dismiss()
        self.on_enter()

    def _ignore_one(self, tx):
        today = date.today()
        db.ignore_recurring(tx['id'], today.year, today.month)
        self.dialog.dismiss()
        self.on_enter()
    
    def _validate_all(self, pending):
        today = date.today()
        for tx in pending:
            db.validate_recurring(tx['id'], today.year, today.month)
        self.dialog.dismiss()
        self.on_enter()


# ============================================================
# ÉCRAN 2 : AJOUT DE TRANSACTION
# ============================================================

class HistoryScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        layout = MDBoxLayout(orientation="vertical")
        layout.add_widget(MDTopAppBar(
            title="Historique des transactions",
            left_action_items=[["arrow-left", lambda *_: self._go_back()]]
        ))
        scroll = MDScrollView()
        items = MDList()
        for tx in db.get_transactions():
            sign = "+" if tx["type"] == "revenu" else "-"
            color = THEME_COLORS["green"] if tx["type"] == "revenu" else THEME_COLORS["red"]
            amount_str = f"{sign}{tx['amount']:,.2f} MAD".replace(',', ' ')
            item = TwoLineListItem(
                text=f"{tx['date']}   {amount_str}   {tx['category_name']}",
                secondary_text=tx["description"] or "Modifier cette transaction",
                theme_text_color="Custom",
                text_color=color
            )
            item.bind(on_release=lambda _, row=tx: self.edit(row))
            items.add_widget(item)
        if not items.children:
            items.add_widget(OneLineListItem(text="Aucune transaction"))
        scroll.add_widget(items)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def _go_back(self):
        self.manager.transition = SlideTransition(direction='right')
        self.manager.current = 'dashboard'

    def edit(self, tx):
        add_screen = self.manager.get_screen("add")
        add_screen.editing = tx
        add_screen.return_screen = "history"
        self.manager.transition = SlideTransition(direction='up')
        self.manager.current = "add"


class AddTransactionScreen(MDScreen):
    editing = None
    return_screen = 'dashboard'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_category_id = None
        self.selected_category_name = None
        self._confirm_dialog = None
    
    def on_enter(self):
        self.clear_widgets()
        self.selected_category_id = None
        self.selected_category_name = None
        
        layout = MDBoxLayout(orientation='vertical', spacing=dp(10), padding=dp(15))
        
        # Barre d'application
        toolbar = MDTopAppBar(
            title="Modifier la transaction" if self.editing else "Nouvelle transaction",
            left_action_items=[["arrow-left", lambda x: self._close()]]
        )
        layout.add_widget(toolbar)
        
        # Contenu scrollable
        scroll = MDScrollView()
        content = MDBoxLayout(orientation='vertical', spacing=dp(15),
                              size_hint_y=None, padding=[0, dp(10)])
        content.bind(minimum_height=content.setter('height'))
        
        # Champ montant
        self.amount_field = MDTextField(
            hint_text="Montant (MAD)",
            multiline=False,
            mode="rectangle",
            font_size=dp(24),
            size_hint_y=None,
            height=dp(60)
        )
        content.add_widget(self.amount_field)
        
        # Catégories de dépense
        content.add_widget(MDLabel(
            text='Catégories de dépense',
            font_style='Subtitle2',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(24)
        ))
        
        self.depense_grid = MDGridLayout(cols=4, spacing=dp(8), size_hint_y=None)
        self.depense_grid.bind(minimum_height=self.depense_grid.setter('height'))
        content.add_widget(self.depense_grid)
        
        # Catégories de revenu
        content.add_widget(MDLabel(
            text='Catégories de revenu',
            font_style='Subtitle2',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(24)
        ))
        
        self.revenu_grid = MDGridLayout(cols=4, spacing=dp(8), size_hint_y=None)
        self.revenu_grid.bind(minimum_height=self.revenu_grid.setter('height'))
        content.add_widget(self.revenu_grid)
        
        # Date
        self.date_field = MDTextField(
            hint_text="Date (AAAA-MM-JJ)",
            text=date.today().strftime('%Y-%m-%d'),
            multiline=False,
            mode="rectangle",
            size_hint_y=None,
            height=dp(50)
        )
        content.add_widget(self.date_field)
        
        # Objet / Détail
        content.add_widget(MDLabel(
            text='Objet / Détail (ex: fruits, légumes, essence...)',
            font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(20)
        ))
        self.desc_field = MDTextField(
            hint_text="Ex: pommes, pain, carburant...",
            multiline=False,
            mode="rectangle",
            size_hint_y=None,
            height=dp(50)
        )
        content.add_widget(self.desc_field)
        
        # Case récurrent
        recur_box = MDBoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        recur_box.add_widget(MDLabel(text='Répéter chaque mois'))
        self.recurring_check = MDCheckbox(active=False, size_hint_x=None, width=dp(50))
        recur_box.add_widget(self.recurring_check)
        content.add_widget(recur_box)
        
        scroll.add_widget(content)
        layout.add_widget(scroll)
        
        # Bouton valider
        validate_btn = MDRaisedButton(
            text="VALIDER",
            md_bg_color=THEME_COLORS["green"],
            size_hint=(1, None),
            height=dp(50),
            font_size=dp(16)
        )
        validate_btn.bind(on_press=self._validate)
        layout.add_widget(validate_btn)
        
        self.add_widget(layout)
        self._load_categories()
    
        if self.editing:
            tx = self.editing
            self.amount_field.text = f"{tx['amount']:.2f}"
            self.date_field.text = tx["date"]
            self.desc_field.text = tx["description"]
            self.recurring_check.active = bool(tx["is_recurring"])
            for grid in (self.depense_grid, self.revenu_grid):
                for button in grid.children:
                    if button.cat_id == tx["category_id"]:
                        self._select_category(button)
            delete = MDRaisedButton(
                text="SUPPRIMER CETTE TRANSACTION",
                md_bg_color=THEME_COLORS["red"],
                size_hint=(1, None),
                height=dp(48)
            )
            delete.bind(on_release=self._confirm_delete)
            layout.add_widget(delete)

    def _confirm_delete(self, *_):
        if not self.editing:
            return
        transaction_id = self.editing["id"]
        def confirm(*_):
            db.delete_transaction(transaction_id)
            if self._confirm_dialog:
                self._confirm_dialog.dismiss()
            self._close()
        self._confirm_dialog = MDDialog(
            title="Supprimer cette transaction ?",
            text="Cette suppression est définitive.",
            buttons=[
                MDRaisedButton(text="ANNULER", on_release=lambda *_: self._confirm_dialog.dismiss()),
                MDRaisedButton(
                    text="SUPPRIMER",
                    md_bg_color=THEME_COLORS["red"],
                    on_release=confirm
                )
            ]
        )
        self._confirm_dialog.open()

    def on_pre_leave(self):
        if self._confirm_dialog:
            self._confirm_dialog.dismiss()
            self._confirm_dialog = None
        self.editing = None
        self.return_screen = 'dashboard'

    def _load_categories(self):
        self.depense_grid.clear_widgets()
        self.revenu_grid.clear_widgets()
        
        categories = db.get_categories()
        for cat in categories:
            btn = MDRaisedButton(
                text=f"{cat['icon']}\n{cat['name'][:8]}",
                size_hint=(1, None),
                height=dp(72),
                md_bg_color=(0.9, 0.9, 0.9, 1),
                text_color=(0.2, 0.2, 0.2, 1)
            )
            btn.cat_id = cat['id']
            btn.cat_name = cat['name']
            btn.bind(on_press=self._select_category)
            
            if cat['type'] == 'depense':
                self.depense_grid.add_widget(btn)
            else:
                self.revenu_grid.add_widget(btn)
    
    def _select_category(self, instance):
        self.selected_category_id = instance.cat_id
        self.selected_category_name = instance.cat_name
        
        # Mettre en surbrillance
        for grid in [self.depense_grid, self.revenu_grid]:
            for child in grid.children:
                if child.cat_id == instance.cat_id:
                    child.md_bg_color = MDApp.get_running_app().theme_cls.primary_color
                    child.text_color = (1, 1, 1, 1)
                else:
                    child.md_bg_color = (0.9, 0.9, 0.9, 1)
                    child.text_color = (0.2, 0.2, 0.2, 1)
    
    def _validate(self, instance):
        try:
            amount = parse_mad(self.amount_field.text)
            if amount <= 0:
                raise ValueError("Le montant doit être supérieur à 0.")
        except ValueError as error:
            self._show_error(str(error) or 'Montant invalide')
            return
        
        if self.selected_category_id is None:
            self._show_error('Sélectionnez une catégorie')
            return
        
        date_str = self.date_field.text.strip()
        try:
            transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            self._show_error('Format de date invalide (AAAA-MM-JJ)')
            return
        
        values = dict(
            amount=amount,
            category_id=self.selected_category_id,
            date_str=date_str,
            description=self.desc_field.text.strip(),
            is_recurring=self.recurring_check.active
        )
        
        if self.editing:
            db.update_transaction(self.editing['id'], **values)
        else:
            db.add_transaction(**values)

        # Alerte budget
        cat = db.get_category_by_id(self.selected_category_id)
        if cat and cat['type'] == 'depense' and cat['budget_limit'] > 0:
            spent = db.get_category_spending_for_category(
                self.selected_category_id, transaction_date.year, transaction_date.month
            )
            ratio = spent / cat['budget_limit']
            if ratio > 1.0:
                self._show_info(f"🔴 Budget dépassé !\n{cat['name']} : {format_mad(spent)} / {format_mad(cat['budget_limit'])}")
            elif ratio >= 0.75:
                self._show_info(f"🟠 Limite proche\n{cat['name']} : {format_mad(spent)} / {format_mad(cat['budget_limit'])}")
        
        self._close()
    
    def _close(self, *args):
        target = 'history' if self.editing else (self.return_screen or 'dashboard')
        self.manager.transition = SlideTransition(direction='down')
        self.manager.current = target
    
    def _show_error(self, message):
        dialog = MDDialog(
            title='Erreur',
            text=message,
            buttons=[
                MDRaisedButton(text="OK", on_release=lambda x: dialog.dismiss())
            ]
        )
        dialog.open()
    
    def _show_info(self, message):
        dialog = MDDialog(
            title='Information',
            text=message,
            buttons=[
                MDRaisedButton(text="OK", on_release=lambda x: dialog.dismiss())
            ]
        )
        dialog.open()


# ============================================================
# ÉCRAN 3 : MOIS & BUDGETS
# ============================================================

class BudgetsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_year = date.today().year
        self.current_month = date.today().month
    
    def on_enter(self):
        self.clear_widgets()
        
        layout = MDBoxLayout(orientation='vertical', spacing=dp(10))
        
        # Barre d'application
        toolbar = MDTopAppBar(
            title="📊 Mois & Budgets",
            elevation=4
        )
        layout.add_widget(toolbar)
        
        # Sélecteur de mois
        month_row = MDBoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10), padding=dp(15))
        prev_btn = MDIconButton(icon="chevron-left")
        prev_btn.bind(on_press=self._prev_month)
        month_row.add_widget(prev_btn)
        
        self.month_label = MDLabel(
            text=f'{MONTH_NAMES[self.current_month - 1]} {self.current_year}',
            font_style='H6',
            bold=True,
            halign='center'
        )
        month_row.add_widget(self.month_label)
        
        next_btn = MDIconButton(icon="chevron-right")
        next_btn.bind(on_press=self._next_month)
        month_row.add_widget(next_btn)
        layout.add_widget(month_row)
        
        # Contenu scrollable
        scroll = MDScrollView()
        content = MDBoxLayout(orientation='vertical', spacing=dp(15), padding=dp(15),
                              size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))
        
        # Totaux du mois
        revenues, expenses = db.get_monthly_totals(self.current_year, self.current_month)
        remaining = _clean_money(revenues - expenses)
        
        totals_card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            height=dp(100),
            padding=dp(15),
            radius=[dp(12)],
            elevation=2
        )
        totals_row = MDBoxLayout(spacing=dp(10))
        for label, value, color in [
            ('Revenus', revenues, "green"),
            ('Dépenses', expenses, "red"),
            ('Reste', remaining, "blue" if remaining >= 0 else "red")
        ]:
            col = MDBoxLayout(orientation='vertical')
            col.add_widget(MDLabel(text=label, font_style='Caption', theme_text_color='Secondary'))
            col.add_widget(MDLabel(
                text=format_mad(value),
                font_style='Body1',
                theme_text_color='Custom',
                text_color=self._get_theme_color(color),
                bold=True,
                halign='center'
            ))
            totals_row.add_widget(col)
        totals_card.add_widget(totals_row)
        content.add_widget(totals_card)
        
        # Liste des budgets
        content.add_widget(MDLabel(
            text='Budgets par catégorie',
            font_style='Subtitle1',
            bold=True,
            size_hint_y=None,
            height=dp(28)
        ))
        
        categories = db.get_category_spending(self.current_year, self.current_month)
        for cat in categories:
            content.add_widget(self._build_budget_card(cat))
        
        scroll.add_widget(content)
        layout.add_widget(scroll)
        
        # Bouton flottant +
        fab = MDFloatingActionButton(
            icon="plus",
            md_bg_color=MDApp.get_running_app().theme_cls.primary_color,
            pos_hint={'center_x': 0.5}
        )
        fab.bind(on_press=lambda x: self._open_add_screen())
        layout.add_widget(fab)
        
        self.add_widget(layout)
    
    def _get_theme_color(self, color_name):
        return THEME_COLORS.get(color_name, (0, 0, 0, 1))
    
    def _build_budget_card(self, cat):
        """Construit une carte de budget avec barre de progression."""
        card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            height=dp(100),
            padding=dp(15),
            radius=[dp(12)],
            elevation=2
        )
        
        # Ligne du haut
        top = MDBoxLayout(size_hint_y=None, height=dp(30))
        top.add_widget(MDLabel(
            text=f"{cat['icon']} {cat['name']}",
            font_style='Body1',
            bold=True
        ))
        
        if cat['budget_limit'] > 0:
            top.add_widget(MDLabel(
                text=f"{format_mad(cat['spent'])} / {format_mad(cat['budget_limit'])}",
                font_style='Body2',
                halign='right'
            ))
        else:
            top.add_widget(MDLabel(
                text=format_mad(cat['spent']),
                font_style='Body2',
                halign='right'
            ))
        card.add_widget(top)
        
        # Barre de progression
        status_color = None
        if cat['budget_limit'] > 0:
            ratio = cat['spent'] / cat['budget_limit']
            if ratio > 1.0:
                color = "red"
                status = f"Dépassé de {format_mad(cat['spent'] - cat['budget_limit'])}"
                status_color = self._get_theme_color("red")
            elif ratio >= 0.75:
                color = "orange"
                status = f"{ratio*100:.0f}% utilisé"
                status_color = self._get_theme_color("orange")
            else:
                color = "green"
                status = f"{ratio*100:.0f}% utilisé"
            
            progress = MDProgressBar(
                value=min(ratio * 100, 100),
                color=self._get_theme_color(color),
                size_hint_y=None,
                height=dp(10)
            )
            card.add_widget(progress)
        else:
            status = "Suivi libre"
        
        status_label = MDLabel(
            text=status,
            font_style='Caption',
            theme_text_color='Custom' if status_color else 'Secondary'
        )
        if status_color:
            status_label.text_color = status_color
        card.add_widget(status_label)
        
        return card
    
    def _prev_month(self, *args):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.on_enter()
    
    def _next_month(self, *args):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.on_enter()
    
    def _open_add_screen(self):
        add_screen = self.manager.get_screen('add')
        add_screen.editing = None
        add_screen.return_screen = 'budgets'
        self.manager.transition = SlideTransition(direction='up')
        self.manager.current = 'add'


# ============================================================
# ÉCRAN 4 : PARAMÈTRES
# ============================================================

class SettingsScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        
        layout = MDBoxLayout(orientation='vertical', spacing=dp(10))
        
        # Barre d'application
        toolbar = MDTopAppBar(
            title="⚙️ Paramètres",
            elevation=4
        )
        layout.add_widget(toolbar)
        
        # Contenu scrollable
        scroll = MDScrollView()
        content = MDBoxLayout(orientation='vertical', spacing=dp(15), padding=dp(15),
                              size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))
        
        # Section Catégories
        content.add_widget(MDLabel(
            text='CATÉGORIES',
            font_style='Subtitle2',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(24)
        ))
        
        categories = db.get_categories()
        for cat in categories:
            card = MDCard(
                size_hint_y=None,
                height=dp(70),
                padding=dp(15),
                radius=[dp(12)],
                elevation=2
            )
            
            row = MDBoxLayout(spacing=dp(10))
            
            info = MDBoxLayout(orientation='vertical')
            info.add_widget(MDLabel(
                text=f"{cat['icon']} {cat['name']}",
                font_style='Body1',
                bold=True
            ))
            limit_txt = f"Budget : {format_mad(cat['budget_limit'])}" if cat['budget_limit'] > 0 else "Budget : libre"
            info.add_widget(MDLabel(
                text=limit_txt,
                font_style='Caption',
                theme_text_color='Secondary'
            ))
            
            btn_box = MDBoxLayout(size_hint_x=None, width=dp(100), spacing=dp(5))
            edit_btn = MDIconButton(icon="pencil")
            edit_btn.cat = cat
            edit_btn.bind(on_press=self._edit_category)
            btn_box.add_widget(edit_btn)
            
            if not cat['fallback']:
                del_btn = MDIconButton(icon="delete", theme_text_color="Custom", text_color=THEME_COLORS["red"])
                del_btn.cat = cat
                del_btn.bind(on_press=self._delete_category)
                btn_box.add_widget(del_btn)
            
            row.add_widget(info)
            row.add_widget(btn_box)
            card.add_widget(row)
            content.add_widget(card)
        
        # Bouton ajouter
        add_btn = MDRaisedButton(
            text="+ AJOUTER UNE CATÉGORIE",
            md_bg_color=MDApp.get_running_app().theme_cls.primary_color,
            size_hint=(1, None),
            height=dp(50)
        )
        add_btn.bind(on_press=self._add_category)
        content.add_widget(add_btn)
       
        # Bouton Quitter l'application
        quit_btn = MDRaisedButton(
            text="🚪 QUITTER L'APPLICATION",
            md_bg_color=(0.4, 0.4, 0.4, 1),  # Gris foncé
            size_hint=(1, None),
            height=dp(50)
        )
        quit_btn.bind(on_press=lambda x: MDApp.get_running_app().stop())
        content.add_widget(quit_btn)
       
        # Section Données
        content.add_widget(MDLabel(
            text='DONNÉES',
            font_style='Subtitle2',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(24)
        ))
        
        export_btn = MDRaisedButton(
            text="📥 EXPORTER EN CSV",
            md_bg_color=THEME_COLORS["green"],
            size_hint=(1, None),
            height=dp(50)
        )
        export_btn.bind(on_press=self._export_csv)
        content.add_widget(export_btn)
        
        reset_btn = MDRaisedButton(
            text="🔄 RÉINITIALISER",
            md_bg_color=THEME_COLORS["red"],
            size_hint=(1, None),
            height=dp(50)
        )
        reset_btn.bind(on_press=self._reset_data)
        content.add_widget(reset_btn)
        
        scroll.add_widget(content)
        layout.add_widget(scroll)
        

        self.add_widget(layout)
        
    
    def _add_category(self, *args):
        content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(12),
            size_hint_y=None,
            height=dp(275)
        )
        
        name_field = MDTextField(hint_text='Nom', multiline=False, mode='rectangle')
        content.add_widget(name_field)
        
        icon_field = MDTextField(hint_text='Emoji (ex: 🍕)', text='📦', multiline=False, mode='rectangle')
        content.add_widget(icon_field)
        
        limit_field = MDTextField(hint_text='Budget (0 = libre)', multiline=False, text='0', mode='rectangle')
        content.add_widget(limit_field)
        
        selected_type = {'value': 'depense'}
        type_box = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))

        dep_btn = MDRaisedButton(text='Dépense', size_hint=(1, None), height=dp(42))
        rev_btn = MDRaisedButton(text='Revenu', size_hint=(1, None), height=dp(42))

        def set_type(kind):
            selected_type['value'] = kind
            if kind == 'depense':
                dep_btn.md_bg_color = THEME_COLORS["red"]
                dep_btn.text_color = (1, 1, 1, 1)
                rev_btn.md_bg_color = (0.85, 0.85, 0.85, 1)
                rev_btn.text_color = (0.3, 0.3, 0.3, 1)
            else:
                rev_btn.md_bg_color = THEME_COLORS["green"]
                rev_btn.text_color = (1, 1, 1, 1)
                dep_btn.md_bg_color = (0.85, 0.85, 0.85, 1)
                dep_btn.text_color = (0.3, 0.3, 0.3, 1)

        dep_btn.bind(on_release=lambda *_: set_type('depense'))
        rev_btn.bind(on_release=lambda *_: set_type('revenu'))
        set_type('depense')
        
        type_box.add_widget(dep_btn)
        type_box.add_widget(rev_btn)
        content.add_widget(type_box)
        
        dialog = MDDialog(
            title='Nouvelle catégorie',
            type="custom",
            content_cls=content,
            buttons=[
                MDRaisedButton(text="ANNULER", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text="ENREGISTRER",
                    md_bg_color=THEME_COLORS["green"],
                    on_release=lambda x: self._save_new_category(name_field, icon_field, limit_field, selected_type['value'], dialog)
                )
            ]
        )
        dialog.open()
    
    def _save_new_category(self, name_field, icon_field, limit_field, cat_type, dialog):
        name_field.error = False
        limit_field.error = False
        name = name_field.text.strip()
        if not name:
            name_field.helper_text = "Saisissez un nom de catégorie."
            name_field.helper_text_mode = "on_error"
            name_field.error = True
            return
        try:
            limit = parse_mad(limit_field.text.strip() or '0')
        except ValueError as error:
            limit_field.helper_text = str(error)
            limit_field.helper_text_mode = "on_error"
            limit_field.error = True
            return
        
        try:
            db.add_category(
                name=name,
                type_=cat_type,
                icon=icon_field.text.strip() or '📦',
                budget_limit=limit
            )
        except sqlite3.IntegrityError:
            name_field.helper_text = "Ce nom de catégorie existe déjà."
            name_field.helper_text_mode = "on_error"
            name_field.error = True
            return
        dialog.dismiss()
        self.on_enter()
    
    def _edit_category(self, instance):
        cat = instance.cat
        
        content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(12),
            size_hint_y=None,
            height=dp(245)
        )
        
        name_field = MDTextField(hint_text='Nom', text=cat['name'], multiline=False, mode='rectangle')
        content.add_widget(name_field)
        
        icon_field = MDTextField(hint_text='Emoji', text=cat['icon'], multiline=False, mode='rectangle')
        content.add_widget(icon_field)
        
        limit_field = MDTextField(
            hint_text='Budget mensuel (0 = libre)',
            text=format_amount_input(cat['budget_limit']),
            multiline=False,
            mode='rectangle'
        )
        content.add_widget(limit_field)
        
        dialog = MDDialog(
            title=f'Modifier {cat["name"]}',
            type="custom",
            content_cls=content,
            buttons=[
                MDRaisedButton(text="ANNULER", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text="ENREGISTRER",
                    md_bg_color=THEME_COLORS["green"],
                    on_release=lambda x: self._save_edit_category(cat, name_field, icon_field, limit_field, dialog)
                )
            ]
        )
        dialog.open()
    
    def _save_edit_category(self, cat, name_field, icon_field, limit_field, dialog):
        name_field.error = False
        limit_field.error = False
        name = name_field.text.strip()
        if not name:
            name_field.helper_text = "Saisissez un nom de catégorie."
            name_field.helper_text_mode = "on_error"
            name_field.error = True
            return
        try:
            limit = parse_mad(limit_field.text.strip() or '0')
        except ValueError as error:
            limit_field.helper_text = str(error)
            limit_field.helper_text_mode = "on_error"
            limit_field.error = True
            return
        
        try:
            db.update_category(cat['id'], name, icon_field.text.strip() or '📦', cat['color'], limit)
        except sqlite3.IntegrityError:
            name_field.helper_text = "Ce nom de catégorie existe déjà."
            name_field.helper_text_mode = "on_error"
            name_field.error = True
            return
        dialog.dismiss()
        self.on_enter()
    
    def _delete_category(self, instance):
        cat = instance.cat
        
        dialog = MDDialog(
            title='Confirmation',
            text=f"Supprimer '{cat['name']}' ?\n\nSes transactions resteront dans une catégorie du même type.",
            buttons=[
                MDRaisedButton(text="ANNULER", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text="SUPPRIMER",
                    md_bg_color=THEME_COLORS["red"],
                    on_release=lambda x: (db.delete_category(cat['id']), dialog.dismiss(), self.on_enter())
                )
            ]
        )
        dialog.open()
    
    export_request = 7031
    export_pending = False

    def _export_csv(self, *args):
        try:
            if platform == "android":
                self._choose_csv_document()
                return
            filepath = os.path.join(os.path.expanduser("~"), "budget_export.csv")
            count = db.export_to_csv(filepath)
            self._export_message("Export réussi", f"{count} transactions exportées vers {filepath}")
        except Exception as error:
            self._export_message("Erreur d’export", str(error))

    def _choose_csv_document(self):
        from android import activity
        from jnius import autoclass
        if self.export_pending:
            return
        intent_class = autoclass("android.content.Intent")
        intent = intent_class(intent_class.ACTION_CREATE_DOCUMENT)
        intent.addCategory(intent_class.CATEGORY_OPENABLE)
        intent.setType("text/csv")
        intent.putExtra(intent_class.EXTRA_TITLE, "budget_export.csv")
        current = autoclass("org.kivy.android.PythonActivity").mActivity
        activity.bind(on_activity_result=self._csv_result)
        self.export_pending = True
        try:
            current.startActivityForResult(intent, self.export_request)
        except Exception:
            activity.unbind(on_activity_result=self._csv_result)
            self.export_pending = False
            raise

    @mainthread
    def _csv_result(self, request, result, intent):
        if request != self.export_request or not self.export_pending:
            return
        from android import activity
        from jnius import autoclass
        activity.unbind(on_activity_result=self._csv_result)
        self.export_pending = False
        if result != autoclass("android.app.Activity").RESULT_OK or intent is None:
            return
        try:
            uri = intent.getData()
            if uri is None:
                raise OSError("Aucun document n’a été sélectionné.")
            current = autoclass("org.kivy.android.PythonActivity").mActivity
            resolver = current.getContentResolver()
            descriptor = resolver.openFileDescriptor(uri, "wt")
            if descriptor is None:
                raise OSError("Le document sélectionné est inaccessible.")
            fd = descriptor.detachFd()
            try:
                stream = os.fdopen(fd, "w", encoding="utf-8", newline="")
            except Exception:
                os.close(fd)
                raise
            with stream:
                count = db.write_csv(stream)
            self._export_message("Export réussi", f"{count} transactions exportées dans le document choisi.")
        except Exception as error:
            self._export_message("Erreur d’export", str(error))

    def _export_message(self, title, message):
        dialog = MDDialog(title=title, text=message,
                          buttons=[MDRaisedButton(text="OK", on_release=lambda *_: dialog.dismiss())])
        dialog.open()

    def _reset_data(self, *args):
        dialog = MDDialog(
            title='Réinitialisation',
            text='⚠️ ATTENTION ⚠️\n\nCette action supprimera TOUTES vos transactions.\nLes catégories seront conservées.',
            buttons=[
                MDRaisedButton(text="ANNULER", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text="TOUT SUPPRIMER",
                    md_bg_color=THEME_COLORS["red"],
                    on_release=lambda x: self._do_reset(dialog)
                )
            ]
        )
        dialog.open()
    
    def _do_reset(self, dialog):
        db.reset_transactions()
        dialog.dismiss()
        self.on_enter()


# ============================================================
# BARRE DE NAVIGATION EN BAS
# ============================================================

class BottomNavBar(MDBoxLayout):
    """Barre de navigation simple avec 3 onglets."""
    def __init__(self, screen_manager, **kwargs):
        super().__init__(**kwargs)
        self.sm = screen_manager
        self.size_hint_y = None
        self.height = dp(60)
        self.padding = 0
        self.spacing = 0
        self.md_bg_color = (1, 1, 1, 1)
        self.elevation = 8
        
        tabs = [
            ('Accueil',  'home',         'dashboard'),
            ('Budgets',  'chart-donut',  'budgets'),
            ('Réglages', 'cog',          'settings'),
        ]
        
        for text, icon, screen_name in tabs:
            btn = MDIconButton(
                icon=icon,
                theme_text_color="Custom",
                text_color=THEME_COLORS["blue"] if screen_name == 'dashboard' else (0.5, 0.5, 0.5, 1),
                icon_size=dp(28)
            )
            btn.screen_name = screen_name
            btn.bind(on_press=self._switch_tab)
            self.add_widget(btn)

        self.sm.bind(current=self._sync_active_tab)
        self._sync_active_tab(self.sm, self.sm.current)
    
    def _switch_tab(self, instance):
        if self.sm.current == instance.screen_name:
            return
        self.sm.transition = SlideTransition(direction='left')
        self.sm.current = instance.screen_name

    def _sync_active_tab(self, manager, screen_name):
        active = 'dashboard' if screen_name == 'history' else screen_name
        for child in self.children:
            if child.screen_name == active:
                child.text_color = THEME_COLORS["blue"]
            else:
                child.text_color = (0.5, 0.5, 0.5, 1)


# ============================================================
# CONTENEUR PRINCIPAL
# ============================================================

class RootLayout(MDBoxLayout):
    """Zone d'écrans + barre d'onglets fixée en bas."""
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        
        # 1) La zone qui affiche les écrans
        self.manager = MDScreenManager()
        self.manager.add_widget(DashboardScreen(name='dashboard'))
        self.manager.add_widget(AddTransactionScreen(name='add'))
        self.manager.add_widget(BudgetsScreen(name='budgets'))
        self.manager.add_widget(HistoryScreen(name='history'))
        self.manager.add_widget(SettingsScreen(name='settings'))
        self.add_widget(self.manager)
        
        # 2) La barre d'onglets, toujours visible en bas
        self.nav_bar = BottomNavBar(self.manager)
        self.add_widget(self.nav_bar)


# ============================================================
# APPLICATION PRINCIPALE
# ============================================================

class BudgetApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        self.title = "Gestion Budget - MAD"
        return RootLayout()


if __name__ == '__main__':
    BudgetApp().run()