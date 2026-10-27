"""
Application de gestion de budget personnel avec KivyMD.
Design Material Design professionnel avec icônes.
"""
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
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.list import MDList, OneLineListItem, TwoLineListItem, ThreeLineListItem
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.selectioncontrol import MDCheckbox  # <-- Correction ici
from kivymd.uix.menu import MDDropdownMenu
from kivymd.icon_definitions import md_icons
from kivymd.uix.toolbar import MDTopAppBar  # Ajouté ici pour simplifier
from kivy.properties import ObjectProperty

from database import db

# ============================================================
# ÉCRAN 1 : TABLEAU DE BORD
# ============================================================

class DashboardScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        
        layout = MDBoxLayout(orientation='vertical', spacing=dp(10))
        
        # Barre d'application
        from kivymd.uix.toolbar import MDTopAppBar
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
        balance = db.get_global_balance()
        balance_color = "green" if balance >= 0 else "red"
        sign = '' if balance >= 0 else '-'
        
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
            text=f'{sign}{abs(balance):,.2f} MAD'.replace(',', ' '),
            font_style='H4',
            theme_text_color='Custom',
            text_color=MDApp.get_running_app().theme_cls.primary_color if balance >= 0 else (0.95, 0.26, 0.21, 1),
            bold=True,
            halign='center'
        ))
        content.add_widget(balance_card)
        
        # Carte Résumé du mois
        today = date.today()
        revenues, expenses = db.get_monthly_totals(today.year, today.month)
        remaining = revenues - expenses
        
        month_names = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                       'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        month_label = f'{month_names[today.month - 1]} {today.year}'
        
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
            ('Reste', remaining, "blue")
        ]:
            col = MDBoxLayout(orientation='vertical')
            col.add_widget(MDLabel(text=label, font_style='Caption', theme_text_color='Secondary'))
            col.add_widget(MDLabel(
                text=f'{value:,.2f} MAD'.replace(',', ' '),
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
                md_bg_color=(1, 0.6, 0, 1),
                size_hint_y=None,
                height=dp(50)
            )
            banner.bind(on_press=lambda x: self._show_recurring_dialog(pending))
            content.add_widget(banner)
        
        # Dernières transactions
        content.add_widget(MDLabel(
            text='Dernières transactions',
            font_style='Subtitle1',
            bold=True
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
        
        scroll.add_widget(content)
        layout.add_widget(scroll)
        
        # Bouton flottant +
        fab = MDFloatingActionButton(
            icon="plus",
            md_bg_color=MDApp.get_running_app().theme_cls.primary_color,
            pos_hint={'center_x': 0.5, 'center_y': 0.08}
        )
        fab.bind(on_press=lambda x: self._open_add_screen())
        layout.add_widget(fab)
        
        self.add_widget(layout)
    
    def _get_theme_color(self, color_name):
        """Retourne la couleur RGB pour un nom de couleur."""
        colors = {
            "green": (0.3, 0.7, 0.3, 1),
            "red": (0.95, 0.26, 0.21, 1),
            "blue": (0.13, 0.59, 0.95, 1)
        }
        return colors.get(color_name, (0, 0, 0, 1))
    
    def _open_add_screen(self):
        self.manager.transition = SlideTransition(direction='up')
        self.manager.current = 'add'
    
    def _show_recurring_dialog(self, pending):
        """Affiche la dialog de validation des récurrents."""
        from kivymd.uix.list import MDList
        
        content = MDScrollView()
        list_layout = MDList()
        
        for tx in pending:
            item = TwoLineListItem(
                text=f"{tx['category_name']}",
                secondary_text=f"{tx['amount']:,.2f} MAD".replace(',', ' ')
            )
            btn = MDIconButton(
                icon="check",
                theme_text_color="Custom",
                text_color=(0.3, 0.7, 0.3, 1)
            )
            btn.bind(on_press=lambda x, t=tx: self._validate_one(t))
            item.add_widget(btn)
            list_layout.add_widget(item)
        
        content.add_widget(list_layout)
        
        self.dialog = MDDialog(
            title='Paiements à valider',
            type="custom",
            content_cls=content,
            buttons=[
                MDRaisedButton(
                    text="TOUT VALIDER",
                    md_bg_color=(0.3, 0.7, 0.3, 1),
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
    
    def _validate_all(self, pending):
        today = date.today()
        for tx in pending:
            db.validate_recurring(tx['id'], today.year, today.month)
        self.dialog.dismiss()
        self.on_enter()


# ============================================================
# ÉCRAN 2 : AJOUT DE TRANSACTION
# ============================================================

class AddTransactionScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_category_id = None
        self.selected_category_name = None
    
    def on_enter(self):
        self.clear_widgets()
        self.selected_category_id = None
        self.selected_category_name = None
        
        layout = MDBoxLayout(orientation='vertical', spacing=dp(10), padding=dp(15))
        
        # Barre d'application
        from kivymd.uix.toolbar import MDTopAppBar
        toolbar = MDTopAppBar(
            title="Nouvelle Transaction",
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
            input_filter="float",
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
            theme_text_color='Secondary'
        ))
        
        self.depense_grid = MDGridLayout(cols=4, spacing=dp(10), size_hint_y=None)
        self.depense_grid.bind(minimum_height=self.depense_grid.setter('height'))
        content.add_widget(self.depense_grid)
        
        # Catégories de revenu
        content.add_widget(MDLabel(
            text='Catégories de revenu',
            font_style='Subtitle2',
            theme_text_color='Secondary'
        ))
        
        self.revenu_grid = MDGridLayout(cols=4, spacing=dp(10), size_hint_y=None)
        self.revenu_grid.bind(minimum_height=self.revenu_grid.setter('height'))
        content.add_widget(self.revenu_grid)
        
        # Date
        self.date_field = MDTextField(
            hint_text="Date (AAAA-MM-JJ)",
            text=date.today().strftime('%Y-%m-%d'),
            mode="rectangle",
            size_hint_y=None,
            height=dp(50)
        )
        content.add_widget(self.date_field)
        
        # Objet / Détail
        content.add_widget(MDLabel(
            text='Objet / Détail (ex: fruits, légumes, essence...)',
            font_style='Caption',
            theme_text_color='Secondary'
        ))
        self.desc_field = MDTextField(
            hint_text="Ex: pommes, pain, carburant...",
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
            md_bg_color=(0.3, 0.7, 0.3, 1),
            size_hint_y=None,
            height=dp(50),
            font_size=dp(16)
        )
        validate_btn.bind(on_press=self._validate)
        layout.add_widget(validate_btn)
        
        self.add_widget(layout)
        self._load_categories()
    
    def _load_categories(self):
        self.depense_grid.clear_widgets()
        self.revenu_grid.clear_widgets()
        
        categories = db.get_categories()
        for cat in categories:
            btn = MDRaisedButton(
                text=f"{cat['icon']}\n{cat['name'][:8]}",
                size_hint=(None, None),
                size=(dp(80), dp(80)),
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
            amount = float(self.amount_field.text.replace(',', '.'))
            if amount <= 0:
                raise ValueError()
        except ValueError:
            self._show_error('Montant invalide')
            return
        
        if self.selected_category_id is None:
            self._show_error('Sélectionnez une catégorie')
            return
        
        date_str = self.date_field.text.strip()
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            self._show_error('Format de date invalide')
            return
        
        db.add_transaction(
            amount=amount,
            category_id=self.selected_category_id,
            date_str=date_str,
            description=self.desc_field.text.strip(),
            is_recurring=self.recurring_check.active
        )
        
        # Alerte budget
        cat = db.get_category_by_id(self.selected_category_id)
        if cat and cat['type'] == 'depense' and cat['budget_limit'] > 0:
            today = date.today()
            spent = db.get_category_spending_for_category(
                self.selected_category_id, today.year, today.month
            )
            ratio = spent / cat['budget_limit']
            if ratio >= 1.0:
                self._show_info(f"🔴 Budget dépassé !\n{cat['name']} : {spent:,.2f} MAD / {cat['budget_limit']:,.2f} MAD".replace(',', ' '))
            elif ratio >= 0.75:
                self._show_info(f"🟠 Limite proche\n{cat['name']} : {spent:,.2f} MAD / {cat['budget_limit']:,.2f} MAD".replace(',', ' '))
        
        self._close()
    
    def _close(self, *args):
        self.manager.transition = SlideTransition(direction='down')
        self.manager.current = 'dashboard'
    
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
        from kivymd.uix.toolbar import MDTopAppBar
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
        
        month_names = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                       'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        self.month_label = MDLabel(
            text=f'{month_names[self.current_month - 1]} {self.current_year}',
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
        remaining = revenues - expenses
        
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
            ('Reste', remaining, "blue")
        ]:
            col = MDBoxLayout(orientation='vertical')
            col.add_widget(MDLabel(text=label, font_style='Caption', theme_text_color='Secondary'))
            col.add_widget(MDLabel(
                text=f'{value:,.2f} MAD'.replace(',', ' '),
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
            bold=True
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
            pos_hint={'center_x': 0.5, 'center_y': 0.08}
        )
        fab.bind(on_press=lambda x: self._open_add_screen())
        layout.add_widget(fab)
        
        self.add_widget(layout)
    
    def _get_theme_color(self, color_name):
        colors = {
            "green": (0.3, 0.7, 0.3, 1),
            "red": (0.95, 0.26, 0.21, 1),
            "blue": (0.13, 0.59, 0.95, 1)
        }
        return colors.get(color_name, (0, 0, 0, 1))
    
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
                text=f"{cat['spent']:,.2f} MAD / {cat['budget_limit']:,.2f} MAD".replace(',', ' '),
                font_style='Body2',
                halign='right'
            ))
        else:
            top.add_widget(MDLabel(
                text=f"{cat['spent']:,.2f} MAD".replace(',', ' '),
                font_style='Body2',
                halign='right'
            ))
        card.add_widget(top)
        
        # Barre de progression
        if cat['budget_limit'] > 0:
            ratio = cat['spent'] / cat['budget_limit']
            if ratio >= 1.0:
                color = "red"
                status = f"Dépassé de {cat['spent'] - cat['budget_limit']:,.2f} MAD".replace(',', ' ')
            elif ratio >= 0.75:
                color = "orange"
                status = f"{ratio*100:.0f}% utilisé"
            else:
                color = "green"
                status = f"{ratio*100:.0f}% utilisé"
            
            progress = MDProgressBar(
                value=min(ratio * 100, 100),
                size_hint_y=None,
                height=dp(10)
            )
            card.add_widget(progress)
        else:
            status = "Suivi libre"
        
        card.add_widget(MDLabel(
            text=status,
            font_style='Caption',
            theme_text_color='Secondary'
        ))
        
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
        from kivymd.uix.toolbar import MDTopAppBar
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
            theme_text_color='Secondary'
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
            limit_txt = f"Budget : {cat['budget_limit']:,.2f} MAD".replace(',', ' ') if cat['budget_limit'] > 0 else "Budget : libre"
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
            
            if cat['name'] != 'Divers':
                del_btn = MDIconButton(icon="delete", theme_text_color="Custom", text_color=(0.95, 0.26, 0.21, 1))
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
            size_hint_y=None,
            height=dp(50)
        )
        add_btn.bind(on_press=self._add_category)
        content.add_widget(add_btn)
       
        # Bouton Quitter l'application
        quit_btn = MDRaisedButton(
            text="🚪 QUITTER L'APPLICATION",
            md_bg_color=(0.4, 0.4, 0.4, 1),  # Gris foncé
            size_hint_y=None,
            height=dp(50)
        )
        quit_btn.bind(on_press=lambda x: MDApp.get_running_app().stop())
        content.add_widget(quit_btn)
       
        # Section Données
        content.add_widget(MDLabel(
            text='DONNÉES',
            font_style='Subtitle2',
            theme_text_color='Secondary'
        ))
        
        export_btn = MDRaisedButton(
            text="📥 EXPORTER EN CSV",
            md_bg_color=(0.3, 0.7, 0.3, 1),
            size_hint_y=None,
            height=dp(50)
        )
        export_btn.bind(on_press=self._export_csv)
        content.add_widget(export_btn)
        
        reset_btn = MDRaisedButton(
            text="🔄 RÉINITIALISER",
            md_bg_color=(0.95, 0.26, 0.21, 1),
            size_hint_y=None,
            height=dp(50)
        )
        reset_btn.bind(on_press=self._reset_data)
        content.add_widget(reset_btn)
        
        scroll.add_widget(content)
        layout.add_widget(scroll)
        

        self.add_widget(layout)
        
    
    def _add_category(self, *args):
        from kivymd.uix.textfield import MDTextField
        
        content = MDBoxLayout(orientation='vertical', spacing=dp(10))
        
        name_field = MDTextField(hint_text='Nom', mode='rectangle')
        content.add_widget(name_field)
        
        icon_field = MDTextField(hint_text='Emoji (ex: 🍕)', text='📦', mode='rectangle')
        content.add_widget(icon_field)
        
        limit_field = MDTextField(hint_text='Budget (0 = libre)', input_filter='float', text='0', mode='rectangle')
        content.add_widget(limit_field)
        
        type_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        type_label = MDLabel(text='depense')
        
        dep_btn = MDRaisedButton(text='Dépense', md_bg_color=(0.95, 0.26, 0.21, 1))
        dep_btn.bind(on_press=lambda x: setattr(type_label, 'text', 'depense'))
        rev_btn = MDRaisedButton(text='Revenu', md_bg_color=(0.3, 0.7, 0.3, 1))
        rev_btn.bind(on_press=lambda x: setattr(type_label, 'text', 'revenu'))
        
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
                    md_bg_color=(0.3, 0.7, 0.3, 1),
                    on_release=lambda x: self._save_new_category(name_field, icon_field, limit_field, type_label, dialog)
                )
            ]
        )
        dialog.open()
    
    def _save_new_category(self, name_field, icon_field, limit_field, type_label, dialog):
        name = name_field.text.strip()
        if not name:
            return
        try:
            limit = float(limit_field.text.replace(',', '.'))
        except ValueError:
            limit = 0.0
        
        db.add_category(
            name=name,
            type_=type_label.text,
            icon=icon_field.text or '📦',
            budget_limit=limit
        )
        dialog.dismiss()
        self.on_enter()
    
    def _edit_category(self, instance):
        cat = instance.cat
        
        content = MDBoxLayout(orientation='vertical', spacing=dp(10))
        
        name_field = MDTextField(text=cat['name'], mode='rectangle')
        content.add_widget(name_field)
        
        icon_field = MDTextField(text=cat['icon'], mode='rectangle')
        content.add_widget(icon_field)
        
        limit_field = MDTextField(text=str(cat['budget_limit']), input_filter='float', mode='rectangle')
        content.add_widget(MDLabel(text='Budget mensuel (0 = libre)', font_style='Caption'))
        content.add_widget(limit_field)
        
        dialog = MDDialog(
            title=f'Modifier {cat["name"]}',
            type="custom",
            content_cls=content,
            buttons=[
                MDRaisedButton(text="ANNULER", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text="ENREGISTRER",
                    md_bg_color=(0.3, 0.7, 0.3, 1),
                    on_release=lambda x: self._save_edit_category(cat, name_field, icon_field, limit_field, dialog)
                )
            ]
        )
        dialog.open()
    
    def _save_edit_category(self, cat, name_field, icon_field, limit_field, dialog):
        name = name_field.text.strip()
        if not name:
            return
        try:
            limit = float(limit_field.text.replace(',', '.'))
        except ValueError:
            limit = 0.0
        
        db.update_category(cat['id'], name, icon_field.text or '📦', cat['color'], limit)
        dialog.dismiss()
        self.on_enter()
    
    def _delete_category(self, instance):
        cat = instance.cat
        
        content = MDLabel(
            text=f"Supprimer '{cat['name']}' ?\n\nSes transactions seront transférées vers 'Divers'.",
            halign='center'
        )
        
        dialog = MDDialog(
            title='Confirmation',
            type="custom",
            content_cls=content,
            buttons=[
                MDRaisedButton(text="ANNULER", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text="SUPPRIMER",
                    md_bg_color=(0.95, 0.26, 0.21, 1),
                    on_release=lambda x: (db.delete_category(cat['id']), dialog.dismiss(), self.on_enter())
                )
            ]
        )
        dialog.open()
    
    def _export_csv(self, *args):
        import os
        filepath = os.path.join(os.path.expanduser('~'), 'budget_export.csv')
        try:
            count = db.export_to_csv(filepath)
            dialog = MDDialog(
                title='Export réussi',
                text=f'{count} transactions exportées vers :\n{filepath}',
                buttons=[
                    MDRaisedButton(text="OK", on_release=lambda x: dialog.dismiss())
                ]
            )
            dialog.open()
        except Exception as e:
            dialog = MDDialog(
                title='Erreur',
                text=f'Erreur : {e}',
                buttons=[
                    MDRaisedButton(text="OK", on_release=lambda x: dialog.dismiss())
                ]
            )
            dialog.open()
    
    def _reset_data(self, *args):
        content = MDLabel(
            text='⚠️ ATTENTION ⚠️\n\nCette action supprimera TOUTES vos transactions.\nLes catégories seront conservées.',
            halign='center'
        )
        
        dialog = MDDialog(
            title='Réinitialisation',
            type="custom",
            content_cls=content,
            buttons=[
                MDRaisedButton(text="ANNULER", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text="TOUT SUPPRIMER",
                    md_bg_color=(0.95, 0.26, 0.21, 1),
                    on_release=lambda x: self._do_reset(dialog)
                )
            ]
        )
        dialog.open()
    
    def _do_reset(self, dialog):
        db.cursor.execute('DELETE FROM transactions')
        db.cursor.execute('DELETE FROM recurring_validations')
        db.conn.commit()
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
                text_color=(0.13, 0.59, 0.95, 1) if screen_name == 'dashboard' else (0.5, 0.5, 0.5, 1),
                icon_size=dp(28)
            )
            btn.screen_name = screen_name
            btn.bind(on_press=self._switch_tab)
            self.add_widget(btn)
    
    def _switch_tab(self, instance):
        self.sm.current = instance.screen_name
        # Mettre à jour les couleurs
        for child in self.children:
            if child.screen_name == instance.screen_name:
                child.text_color = (0.13, 0.59, 0.95, 1)
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