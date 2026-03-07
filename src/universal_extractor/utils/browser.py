"""Detect the default browser on macOS for yt-dlp cookie extraction."""

from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)

# Map macOS bundle IDs to yt-dlp browser names
_BUNDLE_TO_BROWSER: dict[str, str] = {
    "com.apple.safari": "safari",
    "com.google.chrome": "chrome",
    "org.mozilla.firefox": "firefox",
    "com.brave.browser": "brave",
    "com.microsoft.edgemac": "edge",
    "com.operasoftware.opera": "opera",
    "com.vivaldi.vivaldi": "vivaldi",
}

# Fallback order when default browser is not supported by yt-dlp
# Chrome first since it's most commonly used for YouTube auth
_FALLBACK_BROWSERS = ["chrome", "safari", "firefox"]

# App paths to check if a browser is installed
_BROWSER_APPS: dict[str, str] = {
    "safari": "/Applications/Safari.app",
    "chrome": "/Applications/Google Chrome.app",
    "firefox": "/Applications/Firefox.app",
}


def _parse_default_browser_bundle() -> str | None:
    """Read macOS LaunchServices to find the default HTTP handler bundle ID."""
    try:
        result = subprocess.run(
            [
                "defaults", "read",
                "com.apple.LaunchServices/com.apple.launchservices.secure",
                "LSHandlers",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            logger.debug("defaults read failed: %s", result.stderr.strip())
            return None

        # Parse the plist-style output to find http handler
        output = result.stdout
        lines = output.splitlines()
        for i, line in enumerate(lines):
            if "LSHandlerURLScheme" in line and "http" in line.lower():
                # Check this isn't "https" only — we want the "http" entry
                stripped = line.strip().rstrip(";").strip('"')
                if stripped.endswith('"'):
                    stripped = stripped[:-1]
                # Extract the value after '='
                val = stripped.split("=")[-1].strip().strip('"').strip("';").lower()
                if val != "http":
                    continue
                # Search nearby lines for LSHandlerRoleAll
                for j in range(max(0, i - 5), min(len(lines), i + 5)):
                    if "LSHandlerRoleAll" in lines[j]:
                        bundle = lines[j].split("=")[-1].strip().strip('";').strip()
                        logger.debug("Found default browser bundle: %s", bundle)
                        return bundle.lower()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug("Failed to detect default browser: %s", e)
    return None


def _find_installed_fallback() -> str | None:
    """Find the first installed browser from the fallback list."""
    import os

    for browser in _FALLBACK_BROWSERS:
        app_path = _BROWSER_APPS.get(browser)
        if app_path and os.path.isdir(app_path):
            logger.debug("Fallback browser found: %s", browser)
            return browser
    return None


def detect_default_browser() -> str | None:
    """Detect the default browser and return a yt-dlp compatible browser name.

    Returns None if detection fails or no supported browser is found.
    """
    # Only works on macOS
    if not shutil.which("defaults"):
        logger.debug("Not macOS or 'defaults' not available, skipping browser detection")
        return None

    bundle_id = _parse_default_browser_bundle()
    if bundle_id:
        browser = _BUNDLE_TO_BROWSER.get(bundle_id)
        if browser:
            logger.debug("Default browser detected: %s", browser)
            return browser
        logger.debug(
            "Default browser bundle '%s' not supported by yt-dlp, trying fallbacks",
            bundle_id,
        )

    # Default browser not supported (e.g. Comet) or detection failed — try fallbacks
    fallback = _find_installed_fallback()
    if fallback:
        logger.debug("Using fallback browser: %s", fallback)
    else:
        logger.debug("No supported browser found")
    return fallback
