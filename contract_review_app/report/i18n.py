from __future__ import annotations
from typing import Callable, Dict
import logging

try:
    from .messages_en import MESSAGES as EN
except Exception:  # pragma: no cover - defensive
    EN: Dict[str, str] = {}

try:
    from .messages_uk import MESSAGES as UK
except Exception:  # pragma: no cover - defensive
    UK: Dict[str, str] = {}

logger = logging.getLogger(__name__)


def get_translator(lang: str) -> Callable[[str], str]:
    """
    Returns a translator function t(key, **kwargs) with:
    - Primary table by lang ("uk" -> UK, otherwise EN)
    - Fallback to EN
    - Logs a warning if key absent in both
    - Deterministic formatting via str.format(**kwargs)
    """
    primary = UK if (lang or "").lower().startswith("uk") else EN

    def t(key: str, **kwargs) -> str:
        msg = primary.get(key)
        if msg is None:
            # Fallback to EN
            msg = EN.get(key)
            if msg is None:
                # Log missing keys once per call
                logger.warning("i18n: missing key '%s' for lang='%s'", key, lang)
                # As a last resort, return the key itself (visible for debugging)
                msg = key
        try:
            return msg.format(**kwargs) if kwargs else msg
        except Exception as ex:  # pragma: no cover - defensive
            logger.warning("i18n: format error for key '%s': %s", key, ex)
            return msg

    return t
