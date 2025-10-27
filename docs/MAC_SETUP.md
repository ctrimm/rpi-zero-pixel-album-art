# Quick Setup Guide for Mac Development

**Fix for "externally-managed-environment" error on Mac**

Modern macOS with Homebrew-managed Python requires using virtual environments. This is actually better practice anyway!

## One-Time Setup (5 minutes)

### Easy Way (Recommended)

```bash
# Run the automated setup script
bash setup_mac.sh
```

This will:
- Create a virtual environment (`venv/`)
- Install all Python dependencies
- Set everything up for you

### Manual Way

If you prefer to do it manually:

```bash
# 1. Create virtual environment
python3 -m venv venv

# 2. Activate it
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Every Time You Work

**You need to activate the virtual environment each time you start a new terminal session:**

```bash
# Activate virtual environment
source venv/bin/activate

# You'll see (venv) in your prompt:
# (venv) corytrimm@Cory's Macbook rpi-zero-pixel-album-art %

# Now you can run the app
python3 dev_run.py
```

### Even Easier: Use the run script

```bash
# This activates venv automatically
bash run_mac.sh
```

---

## Complete Workflow

### First Time Setup

```bash
# 1. Clone repository
git clone https://github.com/ctrimm/rpi-zero-pixel-album-art.git
cd rpi-zero-pixel-album-art

# 2. Run setup (creates venv and installs dependencies)
bash setup_mac.sh

# 3. Configure Spotify
cp config.example.json config.json
nano config.json  # Add your Spotify API credentials

# 4. Activate venv (do this every time you start a new terminal)
source venv/bin/activate

# 5. Authenticate with Spotify
python3 src/spotify_auth.py

# 6. Run simulator
python3 dev_run.py
```

### Daily Development

```bash
# Open terminal, navigate to project
cd rpi-zero-pixel-album-art

# Quick run (activates venv automatically)
bash run_mac.sh

# OR manually:
source venv/bin/activate
python3 dev_run.py
```

---

## Auto-Activate Virtual Environment

Add this to your `~/.zshrc` (or `~/.bashrc`):

```bash
# Auto-activate venv when entering project directory
cd() {
  builtin cd "$@"
  if [[ -f "venv/bin/activate" ]]; then
    source venv/bin/activate
  fi
}
```

Now the venv activates automatically when you `cd` into the project!

---

## Troubleshooting

### "command not found: pip"

You're not in the virtual environment. Run:
```bash
source venv/bin/activate
```

### "No module named 'tkinter'"

Tkinter comes with Python on Mac. If missing:
```bash
brew install python-tk@3.11
```

### "Permission denied: setup_mac.sh"

Make it executable:
```bash
chmod +x setup_mac.sh run_mac.sh
```

### Delete and start over

```bash
rm -rf venv
bash setup_mac.sh
```

---

## What Gets Installed?

The virtual environment (`venv/`) contains:
- All Python packages from `requirements.txt`
- Isolated from your system Python
- Safe to delete and recreate

**Do NOT commit `venv/` to git!** (It's already in `.gitignore`)

---

## Why Virtual Environments?

✅ Isolated dependencies per project
✅ No conflicts with system Python
✅ Easy to reproduce on other machines
✅ Can use different Python versions
✅ Homebrew Python stays clean

This is Python best practice for all projects!

---

## Quick Reference

```bash
# Activate venv
source venv/bin/activate

# Deactivate venv
deactivate

# Check if in venv (should see (venv) in prompt)
which python

# Run app
python3 dev_run.py

# Or use convenience script
bash run_mac.sh
```

---

**Now you're ready to develop on Mac!** 🚀
