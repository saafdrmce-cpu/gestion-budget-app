[app]
title = Gestion Budget MAD
package.name = gestionbudget
package.domain = org.monapp

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

# FORCER PYTHON 3.11.6 POUR ÉVITER LE BUG AVEC 3.14
requirements = hostpython3==3.11.6, python3==3.11.6, kivy==2.2.1, kivymd==1.1.1, pyjnius, android

orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 33
android.ndk_api = 21
android.minapi = 21
android.accept_sdk_license = True

p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 0