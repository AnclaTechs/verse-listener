"""
core/easyworship.py
Automates EasyWorship to display Bible verses using PyAutoGUI.
Supports window detection, calibration, and configurable delays.
"""

import logging
import os
import subprocess
import sys
import time
import threading
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)
WINDOW_BACKEND_ENV = "VERSE_LISTENER_EW_WINDOW_BACKEND"
SUPPORTED_WINDOW_BACKENDS = {
    "auto",
    "pygetwindow",
    "pywinctl",
    "wmctrl",
    "xlib",
}


def _try_pyautogui():
    try:
        import pyautogui
        return pyautogui
    except Exception as exc:
        logger.debug("pyautogui unavailable: %s", exc)
        return None


def _try_pygetwindow():
    try:
        import pygetwindow as gw
        return gw
    except Exception as exc:
        logger.debug("pygetwindow unavailable: %s", exc)
        return None


def _try_pywinctl():
    try:
        import pywinctl as pwc
        return pwc
    except Exception as exc:
        logger.debug("pywinctl unavailable: %s", exc)
        return None


def _try_xlib():
    try:
        from Xlib import X, display, protocol
        return X, display, protocol
    except Exception as exc:
        logger.debug("python-xlib unavailable: %s", exc)
        return None


def _try_wmctrl():
    """Linux: use wmctrl to find/focus EasyWorship window."""
    try:
        result = subprocess.run(
            ["wmctrl", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout
    except Exception as exc:
        logger.debug("wmctrl unavailable: %s", exc)
        return ""


def _normalize_window_backend(value: Optional[str]) -> str:
    backend = (value or "auto").strip().lower()
    if backend not in SUPPORTED_WINDOW_BACKENDS:
        logger.warning(
            "Unsupported %s=%r; falling back to 'auto'. Supported values: %s",
            WINDOW_BACKEND_ENV,
            value,
            ", ".join(sorted(SUPPORTED_WINDOW_BACKENDS)),
        )
        return "auto"
    return backend


def _get_default_window_backend() -> str:
    return os.getenv(WINDOW_BACKEND_ENV, "auto")


@dataclass
class EasyWorshipConfig:
    # Delays (seconds) between automation steps
    delay_focus:    float = 0.5
    delay_type:     float = 0.05   # per character
    delay_enter:    float = 0.3
    delay_live:     float = 0.5
    # Coordinates (set via calibration)
    search_x: Optional[int] = None
    search_y: Optional[int] = None
    live_x:   Optional[int] = None
    live_y:   Optional[int] = None
    # Bible translation name as configured in EasyWorship
    translation: str = "NIV"
    # Whether to click the "Live" / "Put on Screen" button after loading
    click_live: bool = False
    # EasyWorship window title fragment
    window_title_fragment: str = "EasyWorship"
    # Window-focus backend. Override with VERSE_LISTENER_EW_WINDOW_BACKEND.
    window_backend: str = field(default_factory=_get_default_window_backend)


class EasyWorshipController:
    """
    Controls EasyWorship via PyAutoGUI mouse/keyboard automation.

    Usage:
        ctrl = EasyWorshipController(config)
        ctrl.send_verse("Romans 8:28")
    """

    def __init__(self, config: Optional[EasyWorshipConfig] = None):
        self.config = config or EasyWorshipConfig()
        self._lock = threading.Lock()
        self._connected = False
        self._pag = _try_pyautogui()
        self._window_backend = _normalize_window_backend(self.config.window_backend)

        if self._pag:
            self._pag.FAILSAFE = True   # move mouse to corner to abort
            self._pag.PAUSE = 0.05

    # ── Window management ─────────────────────────────────────────────────────

    def _get_window_backends(self) -> list[str]:
        if self._window_backend != "auto":
            return [self._window_backend]
        if sys.platform.startswith("linux"):
            return ["pywinctl", "wmctrl", "xlib", "pygetwindow"]
        return ["pygetwindow", "pywinctl", "wmctrl", "xlib"]

    def _find_window_pygetwindow(self, fragment: str):
        gw = _try_pygetwindow()
        if not gw:
            return None
        wins = gw.getWindowsWithTitle(fragment)
        return wins[0] if wins else None

    def _find_window_pywinctl(self, fragment: str):
        pwc = _try_pywinctl()
        if not pwc:
            return None
        wins = pwc.getWindowsWithTitle(fragment)
        return wins[0] if wins else None

    def _find_window_wmctrl(self, fragment: str) -> Optional[str]:
        for line in _try_wmctrl().splitlines():
            if fragment.lower() in line.lower():
                return line
        return None

    def _get_xlib_window_title(self, display_obj, window_obj) -> str:
        xlib = _try_xlib()
        if not xlib:
            return ""
        X, _, _ = xlib
        for atom_name, atom_type in (
            ("_NET_WM_NAME", display_obj.intern_atom("UTF8_STRING")),
            ("WM_NAME", X.AnyPropertyType),
        ):
            try:
                prop = window_obj.get_full_property(
                    display_obj.intern_atom(atom_name),
                    atom_type,
                )
                if prop and prop.value:
                    value = prop.value
                    if isinstance(value, bytes):
                        return value.decode("utf-8", errors="ignore")
                    return str(value)
            except Exception:
                continue
        try:
            return window_obj.get_wm_name() or ""
        except Exception:
            return ""

    def _find_window_xlib(self, fragment: str):
        xlib = _try_xlib()
        if not xlib:
            return None

        X, display_mod, _ = xlib
        display_obj = None
        try:
            display_obj = display_mod.Display()
            root = display_obj.screen().root
            client_list_atom = display_obj.intern_atom("_NET_CLIENT_LIST")
            prop = root.get_full_property(client_list_atom, X.AnyPropertyType)
            if not prop:
                display_obj.close()
                return None

            for window_id in prop.value:
                try:
                    window_obj = display_obj.create_resource_object("window", window_id)
                    title = self._get_xlib_window_title(display_obj, window_obj)
                    if title and fragment.lower() in title.lower():
                        return display_obj, window_obj, title
                except Exception as exc:
                    logger.debug("xlib window inspection failed: %s", exc)
            display_obj.close()
            return None
        except Exception as exc:
            logger.debug("xlib window lookup failed: %s", exc)
            if display_obj is not None:
                try:
                    display_obj.close()
                except Exception:
                    pass
            return None

    def _focus_with_pygetwindow(self, fragment: str) -> bool:
        win = self._find_window_pygetwindow(fragment)
        if not win:
            return False
        if hasattr(win, "restore"):
            win.restore()
        win.activate()
        time.sleep(self.config.delay_focus)
        logger.info("Focused EasyWorship via pygetwindow: %s", getattr(win, "title", fragment))
        return True

    def _focus_with_pywinctl(self, fragment: str) -> bool:
        win = self._find_window_pywinctl(fragment)
        if not win:
            return False
        if hasattr(win, "restore"):
            win.restore()
        win.activate()
        time.sleep(self.config.delay_focus)
        logger.info("Focused EasyWorship via pywinctl: %s", getattr(win, "title", fragment))
        return True

    def _focus_with_wmctrl(self, fragment: str) -> bool:
        line = self._find_window_wmctrl(fragment)
        if not line:
            return False
        win_id = line.split()[0]
        subprocess.run(["wmctrl", "-ia", win_id], timeout=3, check=False)
        time.sleep(self.config.delay_focus)
        logger.info("Focused EasyWorship via wmctrl: %s", line)
        return True

    def _focus_with_xlib(self, fragment: str) -> bool:
        match = self._find_window_xlib(fragment)
        if not match:
            return False

        xlib = _try_xlib()
        if not xlib:
            display_obj, _, _ = match
            try:
                display_obj.close()
            except Exception:
                pass
            return False

        X, _, protocol = xlib
        display_obj, window_obj, title = match
        try:
            root = display_obj.screen().root
            active_atom = display_obj.intern_atom("_NET_ACTIVE_WINDOW")
            event = protocol.event.ClientMessage(
                window=window_obj,
                client_type=active_atom,
                data=(32, [1, X.CurrentTime, 0, 0, 0]),
            )
            root.send_event(
                event,
                event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask,
            )
            try:
                window_obj.set_input_focus(X.RevertToParent, X.CurrentTime)
            except Exception:
                pass
            display_obj.sync()
            time.sleep(self.config.delay_focus)
            logger.info("Focused EasyWorship via xlib: %s", title)
            return True
        finally:
            try:
                display_obj.close()
            except Exception:
                pass

    def _window_exists_with_backend(self, backend: str, fragment: str) -> bool:
        if backend == "pygetwindow":
            return self._find_window_pygetwindow(fragment) is not None
        if backend == "pywinctl":
            return self._find_window_pywinctl(fragment) is not None
        if backend == "wmctrl":
            return self._find_window_wmctrl(fragment) is not None
        if backend == "xlib":
            match = self._find_window_xlib(fragment)
            if not match:
                return False
            display_obj, _, _ = match
            try:
                return True
            finally:
                try:
                    display_obj.close()
                except Exception:
                    pass
        return False

    def _focus_with_backend(self, backend: str, fragment: str) -> bool:
        if backend == "pygetwindow":
            return self._focus_with_pygetwindow(fragment)
        if backend == "pywinctl":
            return self._focus_with_pywinctl(fragment)
        if backend == "wmctrl":
            return self._focus_with_wmctrl(fragment)
        if backend == "xlib":
            return self._focus_with_xlib(fragment)
        logger.warning("Unsupported focus backend requested: %s", backend)
        return False

    def _focus_window(self) -> bool:
        """Try to bring the EasyWorship window to focus. Returns True on success."""
        fragment = self.config.window_title_fragment.strip()
        if not fragment:
            logger.warning("EasyWorship window title fragment is empty")
            return False
        for backend in self._get_window_backends():
            try:
                if self._focus_with_backend(backend, fragment):
                    return True
            except Exception as exc:
                logger.debug("%s focus failed: %s", backend, exc)

        logger.warning(
            "Could not find EasyWorship window using backend '%s'",
            self._window_backend,
        )
        return False

    def is_easyworship_running(self) -> bool:
        """Check whether EasyWorship is currently running."""
        fragment = self.config.window_title_fragment.strip()
        if not fragment:
            return False
        for backend in self._get_window_backends():
            try:
                if self._window_exists_with_backend(backend, fragment):
                    return True
            except Exception as exc:
                logger.debug("%s status check failed: %s", backend, exc)
        return False

    # ── Calibration ───────────────────────────────────────────────────────────

    def calibrate_from_screenshot(self) -> bool:
        """
        Auto-detect the EasyWorship search field by looking for a
        distinctive image region (if template images are provided).
        Falls back to asking the user to click the field manually.
        Returns True if calibration succeeded.
        """
        if not self._pag:
            logger.error("PyAutoGUI not available – cannot calibrate")
            return False

        logger.info("Starting EasyWorship calibration – please click the Bible search field")
        # We wait 3 seconds for the user to position their cursor
        for i in range(3, 0, -1):
            logger.info("Capturing cursor position in %d…", i)
            time.sleep(1)
        x, y = self._pag.position()
        self.config.search_x = x
        self.config.search_y = y
        logger.info("Search field calibrated to (%d, %d)", x, y)
        return True

    # ── Core action ───────────────────────────────────────────────────────────

    def send_verse(self, reference: str) -> bool:
        """
        Send *reference* (e.g. "Romans 8:28") to EasyWorship.
        Returns True on success.
        """
        if not self._pag:
            logger.error("PyAutoGUI not installed – install it with: pip install pyautogui")
            return False

        with self._lock:
            return self._do_send_verse(reference)

    def _do_send_verse(self, reference: str) -> bool:
        pag = self._pag
        cfg = self.config

        # 1. Focus EasyWorship
        focused = self._focus_window()
        if not focused:
            logger.warning("Sending without confirmed window focus")

        time.sleep(cfg.delay_focus)

        # 2. Click search field (if coordinates are calibrated)
        if cfg.search_x is not None and cfg.search_y is not None:
            pag.click(cfg.search_x, cfg.search_y)
            logger.debug("Clicked search field at (%d, %d)", cfg.search_x, cfg.search_y)
        else:
            # Fall back: Ctrl+F or Ctrl+B (EasyWorship Bible search shortcut)
            pag.hotkey("ctrl", "b")
            logger.debug("Sent Ctrl+B to open Bible search")

        time.sleep(0.2)

        # 3. Clear existing text and type the reference
        pag.hotkey("ctrl", "a")
        time.sleep(0.1)
        pag.typewrite(reference, interval=cfg.delay_type)
        logger.info("Typed verse reference: %s", reference)

        time.sleep(cfg.delay_enter)

        # 4. Press Enter to search/load
        pag.press("enter")
        logger.info("Pressed Enter to load verse")

        # 5. Optionally click "Live / Put on Screen" button
        if cfg.click_live and cfg.live_x is not None and cfg.live_y is not None:
            time.sleep(cfg.delay_live)
            pag.click(cfg.live_x, cfg.live_y)
            logger.info("Clicked Live button at (%d, %d)", cfg.live_x, cfg.live_y)

        return True

    # ── Status ────────────────────────────────────────────────────────────────

    def status_text(self) -> str:
        if not self._pag:
            return "PyAutoGUI not installed"
        if self.is_easyworship_running():
            return "EasyWorship: connected"
        return "EasyWorship: not detected"
