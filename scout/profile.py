"""Which person this run is for.

The default (no SCOUT_PROFILE) is the original setup: files in data/, settings in
scout/settings.py. SCOUT_PROFILE=<name> makes a run use profiles/<name>/ instead:
  settings.json     changes to the default settings (null removes a setting)
  profile.txt       the candidate evidence for the AI
  prompt.txt        the AI fit prompt (optional; {profile} and {jobs} are filled in)
  title_prompt.txt  the AI title-check prompt (optional; {titles} is filled in)
  companies.csv     the company list (optional; Company,Website)
Each person has their own Google Sheet (their own SHEET_ID), so nothing is shared.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = os.getenv("SCOUT_PROFILE", "").strip()


def folder(name=None):
    name = NAME if name is None else name
    return os.path.join(ROOT, "profiles", name) if name else ""


def path(filename, default_dir="data", name=None):
    """profiles/<name>/<filename> when it exists, else data/<filename> (or None for prompts)."""
    here = folder(name)
    if here and os.path.exists(os.path.join(here, filename)):
        return os.path.join(here, filename)
    return os.path.join(ROOT, default_dir, filename) if default_dir else None


def read(filename, name=None):
    """Text of a profile-only file, or None when the profile has none."""
    found = path(filename, default_dir=None, name=name)
    if not found:
        return None
    with open(found, encoding="utf-8") as handle:
        return handle.read()


def settings_changes(name=None):
    here = folder(name)
    file = os.path.join(here, "settings.json") if here else ""
    if not file or not os.path.exists(file):
        return {}
    with open(file, encoding="utf-8") as handle:
        return {k: v for k, v in json.load(handle).items() if not k.startswith("#")}
