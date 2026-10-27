[app]
title = Gestion Budget MAD
package.name = gestionbudget
package.domain = org.monapp

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

requirements = python3,kivy==2.3.0,kivymd==1.1.1

orientation = portrait

fullscreen = 0

android.permissions = INTERNET

android.api = 33
android.ndk_api = 21
android.minapi = 21

android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 0