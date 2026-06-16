from __future__ import annotations
from xml.etree import ElementTree as ET

def extract_plain_text(el: ET.Element) -> str:
    """<formatted-texts> 配下の <arbitrary-text> を連結して返す。"""
    parts = [a.text or "" for a in el.iter("arbitrary-text")]
    return "".join(parts).strip()
