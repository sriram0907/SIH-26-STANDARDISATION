"""
Step 4 — Canonical Description Generator
==========================================
Builds standardized descriptions from extracted attributes.
"""

import logging

logger = logging.getLogger(__name__)


def generate_canonical_bolt(attributes: dict) -> str:
    """
    Generate a canonical description for a bolt item.

    Template: "{TYPE}, {MATERIAL}, {DIAMETER} x {LENGTH}, {STANDARD}"
    Example:  "HEX BOLT, STAINLESS STEEL 316, M10 x 50 mm, DIN 933"
    """
    parts = []

    bolt_type = attributes.get("type") or "BOLT"
    parts.append(bolt_type)

    material = attributes.get("material")
    if material:
        parts.append(material.upper())

    diameter = attributes.get("diameter")
    length = attributes.get("length")
    if diameter and length:
        parts.append(f"{diameter} x {length}")
    elif diameter:
        parts.append(diameter)

    standard = attributes.get("standard")
    if standard:
        parts.append(standard)

    thread = attributes.get("thread")
    if thread:
        parts.append(thread)

    canonical = ", ".join(parts)
    logger.info(f"  📝 Canonical bolt: {canonical}")
    return canonical


def generate_canonical_valve(attributes: dict) -> str:
    """
    Generate a canonical description for a valve item.

    Template: "{TYPE} VALVE, {BODY_MATERIAL}, {SIZE}, {PRESSURE_RATING}, {END_CONNECTION}"
    Example:  "GATE VALVE, CARBON STEEL, 2\", 150#, FLANGED"
    """
    parts = []

    valve_type = attributes.get("type") or "VALVE"
    parts.append(f"{valve_type.upper()} VALVE")

    material = attributes.get("body_material")
    if material:
        parts.append(material.upper())

    size = attributes.get("size")
    if size:
        parts.append(size)

    pressure = attributes.get("pressure_rating")
    if pressure:
        parts.append(pressure)

    connection = attributes.get("end_connection")
    if connection:
        parts.append(connection.upper())

    canonical = ", ".join(parts)
    logger.info(f"  📝 Canonical valve: {canonical}")
    return canonical


def generate_canonical(attributes: dict, category: str) -> str:
    """Route to the correct generator based on category."""
    if category == "Bolt":
        return generate_canonical_bolt(attributes)
    elif category == "Valve":
        return generate_canonical_valve(attributes)
    else:
        logger.warning(f"  ⚠️  No canonical generator for category: {category}")
        return ""
