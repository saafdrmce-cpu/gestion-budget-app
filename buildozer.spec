[app]
title = Gestion Budget MAD
package.name = gestionbudget
package.domain = org.monapp

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

source.exclude_patterns = compile_android.py

version = 1.1

requirements = python3,android,sqlite3,kivy==2.3.1,kivymd==1.1.1,chardet==5.2.0,pyjnius
orientation = portrait
fullscreen = 0
android.api = 36
android.archs = arm64-v8a
android.add_src = android_src
android.entrypoint = org.monapp.gestionbudget.BudgetActivity
android.activity_class_name = org.monapp.gestionbudget.BudgetActivity
android.ndk = 28c
android.ndk_api = 21
android.minapi = 21
android.accept_sdk_license = True

p4a.branch = v2026.05.09

[buildozer]
log_level = 2
warn_on_root = 0
