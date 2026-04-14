"""Knowledge base for the Text Agent.

Contains product information, warranty terms, troubleshooting guides,
and assembly instructions for customer service queries.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ProductInfo:
    sku: str
    name: str
    warranty_years: int
    warranty_coverage: str
    warranty_exclusions: str
    return_window_days: int
    notes: str = ""


@dataclass
class TroubleshootingEntry:
    error_code: str
    product_category: str
    description: str
    resolution_steps: list[str]
    requires_service: bool = False


PRODUCTS: dict[str, ProductInfo] = {
    "BM3K-2024": ProductInfo(
        sku="BM3K-2024",
        name="BlenderMax 3000",
        warranty_years=2,
        warranty_coverage="Manufacturing defects only",
        warranty_exclusions="Physical damage from drops, misuse",
        return_window_days=30,
        notes="Replacement parts: blade assembly ($29), motor unit ($59)",
    ),
    "BPP-500": ProductInfo(
        sku="BPP-500",
        name="BrewPerfect Pro",
        warranty_years=1,
        warranty_coverage="Manufacturing defects and damage on arrival",
        warranty_exclusions="User damage after initial setup",
        return_window_days=30,
        notes="Free replacement for DOA items within 7 days",
    ),
    "CMT-400": ProductInfo(
        sku="CMT-400",
        name="CrispMaster Toaster 4-Slice",
        warranty_years=1,
        warranty_coverage="Electrical defects, heating element failure",
        warranty_exclusions="Damage from improper cleaning",
        return_window_days=30,
        notes="Safety policy: Any sparking reports are escalated immediately",
    ),
    "ELP-200": ProductInfo(
        sku="ELP-200",
        name="ErgoLift Pro Stand",
        warranty_years=3,
        warranty_coverage="Structural defects, hinge mechanism",
        warranty_exclusions="Overloading beyond weight limit",
        return_window_days=30,
        notes="Weight limit: 20 lbs",
    ),
    "LTK-8": ProductInfo(
        sku="LTK-8",
        name="LearnTab Kids Tablet",
        warranty_years=2,
        warranty_coverage="Display failure, battery issues, software defects",
        warranty_exclusions="Water damage, drop damage",
        return_window_days=30,
        notes="Check moisture indicator for water damage",
    ),
    "CLP-12": ProductInfo(
        sku="CLP-12",
        name="ChefLine Pro Non-Stick Pan",
        warranty_years=2,
        warranty_coverage="Lifetime on construction, 2 years on coating degradation under normal use",
        warranty_exclusions="Metal utensil damage, dishwasher use, overheating above 500°F",
        return_window_days=30,
        notes="Care: Hand wash only, use plastic or wooden utensils",
    ),
    "SPP-22": ProductInfo(
        sku="SPP-22",
        name="SoundPods Pro",
        warranty_years=1,
        warranty_coverage="Battery and charging defects",
        warranty_exclusions="Physical damage, water damage",
        return_window_days=30,
        notes="Troubleshooting: Try different cable, clean port, reset 10s",
    ),
    "TPC-30": ProductInfo(
        sku="TPC-30",
        name="TrekPro Commuter Pack",
        warranty_years=99,
        warranty_coverage="Lifetime on stitching and zippers",
        warranty_exclusions="Cosmetic wear, cuts, burns",
        return_window_days=30,
        notes="Max load: 35 lbs, suitable for laptops up to 17 inches",
    ),
    "CBX1-24": ProductInfo(
        sku="CBX1-24",
        name="CleanBot X1",
        warranty_years=2,
        warranty_coverage="Motor, battery, sensor defects",
        warranty_exclusions="Damage from running over liquids",
        return_window_days=30,
        notes="Cloudy sensor dome = defect, dirty sensors = user maintenance",
    ),
    "ICP-8": ProductInfo(
        sku="ICP-8",
        name="InstaCook Pro 8Qt",
        warranty_years=2,
        warranty_coverage="Lid mechanism, heating element, electronics. Gasket: 6-month coverage",
        warranty_exclusions="Damage from overfilling",
        return_window_days=30,
        notes="Consumables: Gasket ($12), steam valve ($8)",
    ),
    "TPX-12": ProductInfo(
        sku="TPX-12",
        name="TechPhone X12",
        warranty_years=1,
        warranty_coverage="Manufacturing defects",
        warranty_exclusions="Water damage, screen cracks from drops",
        return_window_days=14,
        notes="IP67 rated but warranty does not cover water damage. Check LDI in SIM tray.",
    ),
    "RBK-17": ProductInfo(
        sku="RBK-17",
        name="RapidBoil Kettle 1.7L",
        warranty_years=2,
        warranty_coverage="Electrical defects, heating element",
        warranty_exclusions="Limescale damage from hard water",
        return_window_days=30,
        notes="Safety: Burning smell = immediate replacement, no repair attempts",
    ),
    "AME-400": ProductInfo(
        sku="AME-400",
        name="AudioMax Elite Headphones",
        warranty_years=2,
        warranty_coverage="Driver failure, Bluetooth connectivity defects, battery degradation below 50% capacity",
        warranty_exclusions="Physical damage, water/sweat damage beyond IPX4 rating, cable wear",
        return_window_days=30,
        notes="Troubleshooting: Reset by holding power 15s. Bluetooth: forget and re-pair. Driver imbalance = defect.",
    ),
    "CAP-6": ProductInfo(
        sku="CAP-6",
        name="CrispAir Pro 6Qt",
        warranty_years=2,
        warranty_coverage="Heating element, fan motor, digital controls, basket coating (1 year)",
        warranty_exclusions="Damage from overfilling, use of metal utensils on basket coating",
        return_window_days=30,
        notes="Common issues: E1=temp sensor, E2=fan stall, E3=overheating protection triggered. Basket coating is consumable after year 1.",
    ),
    "PA-500": ProductInfo(
        sku="PA-500",
        name="PureAir 500 Air Purifier",
        warranty_years=3,
        warranty_coverage="Motor defects, sensor failure, electronic controls. Filter: 6-month coverage",
        warranty_exclusions="Filter consumable replacement, damage from running without filter",
        return_window_days=30,
        notes="Filter replacement every 6 months ($35). Motor bearing noise after 1+ year = warranty defect. Sensor calibration drift = warranty covered.",
    ),
}


TROUBLESHOOTING: dict[str, TroubleshootingEntry] = {
    "router_no_internet": TroubleshootingEntry(
        error_code="WAN_DISCONNECTED",
        product_category="networking",
        description="Router shows WAN disconnected, no internet",
        resolution_steps=[
            "Check physical cable connection to modem",
            "Power cycle modem (unplug 30 seconds)",
            "If LAN active but no internet, issue is upstream",
            "Set manual DNS to 8.8.8.8 and 8.8.4.4 if DNS shows 0.0.0.0",
            "If all above fail, escalate to ISP support",
        ],
        requires_service=False,
    ),
    "washer_e3": TroubleshootingEntry(
        error_code="E3",
        product_category="appliances",
        description="Washing machine door lock failure",
        resolution_steps=[
            "Power off and wait 2 minutes",
            "Check door seal for obstructions",
            "Close door firmly until you hear a click",
            "If error persists, door lock actuator needs replacement",
        ],
        requires_service=True,
    ),
    "3d_printer_jam": TroubleshootingEntry(
        error_code="FILAMENT_JAM",
        product_category="electronics",
        description="3D printer filament tangled at feeder",
        resolution_steps=[
            "Cut filament above the tangle",
            "Manually unwind tangled filament",
            "Reduce feeder tension knob by 1/4 turn",
            "Clean gear teeth with brass brush (not steel)",
            "For extruder wrap: heat to 200°C, cool to 90°C, pull firmly",
        ],
        requires_service=False,
    ),
    "hvac_no_heat": TroubleshootingEntry(
        error_code="HEAT_NOT_RISING",
        product_category="hvac",
        description="Thermostat shows Heat On but temperature not rising",
        resolution_steps=[
            "Check and replace air filter if clogged",
            "Verify all vents are open and unobstructed",
            "Check if furnace is actually running (fan noise, warm air)",
            "For gas: check pilot light. For electric: check heating element",
            "Verify furnace power switch and circuit breaker",
        ],
        requires_service=True,
    ),
    "car_no_start_click": TroubleshootingEntry(
        error_code="RAPID_CLICKING",
        product_category="automotive",
        description="Car won't start, rapid clicking, dim lights",
        resolution_steps=[
            "Symptoms indicate weak/dead battery",
            "Jump start: red to positive, black to negative/ground",
            "Let donor car run 5 minutes before attempting start",
            "After starting, drive 20+ minutes to recharge",
            "Have battery tested - may need replacement if over 3 years old",
        ],
        requires_service=False,
    ),
    "earbuds_no_charge": TroubleshootingEntry(
        error_code="CHARGE_FAIL",
        product_category="audio",
        description="Wireless earbuds or headphones won't charge, case LED not lighting",
        resolution_steps=[
            "Try a different USB-C cable and power adapter",
            "Clean charging contacts with dry cotton swab",
            "Check for debris in charging port with flashlight",
            "Perform hard reset: hold power button 15 seconds",
            "If case LED never lights, charging circuit failure — warranty replacement",
        ],
        requires_service=True,
    ),
    "robot_vacuum_sensor": TroubleshootingEntry(
        error_code="SENSOR_DIRTY",
        product_category="appliances",
        description="Robot vacuum bumping into walls, not detecting obstacles or cliff edges",
        resolution_steps=[
            "Clean all sensors with dry microfiber cloth",
            "Check cliff sensors on bottom for dust or debris",
            "Inspect front bumper for stuck debris preventing retraction",
            "If sensor dome appears cloudy/milky (not dirty), this is a manufacturing defect",
            "Cloudy dome = warranty replacement; dirty sensors = user maintenance",
        ],
        requires_service=False,
    ),
    "air_purifier_motor": TroubleshootingEntry(
        error_code="MOTOR_NOISE",
        product_category="appliances",
        description="Air purifier making grinding, rattling, or high-pitched whining noise",
        resolution_steps=[
            "Remove and reseat the filter — incorrect seating causes vibration",
            "Check for foreign objects in fan intake",
            "Run on lowest speed: if noise persists, motor bearing issue",
            "Motor bearing noise after 1+ year of use = warranty-covered defect",
            "High-pitched resonance at specific speeds = known motor batch issue, warranty covered",
        ],
        requires_service=True,
    ),
    "headphone_audio_imbalance": TroubleshootingEntry(
        error_code="AUDIO_IMBALANCE",
        product_category="audio",
        description="Headphones with one side louder than the other, or Bluetooth audio cutting out",
        resolution_steps=[
            "Check audio balance in device accessibility settings",
            "Forget and re-pair Bluetooth connection",
            "Test with wired connection if available — isolates Bluetooth vs driver issue",
            "Clean ear mesh with soft brush to remove wax/debris buildup",
            "Persistent imbalance with wired connection = driver failure, warranty covered",
        ],
        requires_service=True,
    ),
    "air_fryer_error": TroubleshootingEntry(
        error_code="E1_E2_E3",
        product_category="appliances",
        description="Air fryer displaying error codes E1, E2, or E3",
        resolution_steps=[
            "E1 (temp sensor): Unplug for 5 minutes, replug. If persists, sensor defect",
            "E2 (fan stall): Check basket is properly seated, remove obstructions near fan",
            "E3 (overheat protection): Let unit cool 30 minutes, ensure ventilation clearance",
            "Recurring E1 or E2 after reset = warranty replacement",
            "E3 only during extended cook times = normal safety feature, not defect",
        ],
        requires_service=False,
    ),
}


WARRANTY_ACTIONS = {
    "approve_warranty": "Approve the warranty claim and proceed with repair or replacement",
    "deny_warranty": "Deny the warranty claim due to exclusions or expiration",
    "initiate_replacement": "Replace the product immediately under warranty",
    "initiate_return": "Process a return for refund",
    "order_part": "Order a replacement part under warranty",
    "escalate_to_specialist": "Escalate to a specialist for further review",
    "provide_instructions": "Provide guidance or instructions to resolve the issue",
    "troubleshoot_step": "Guide through troubleshooting steps",
}


def search_products(query: str) -> list[ProductInfo]:
    """Search products by name, SKU, or keywords in coverage."""
    query_lower = query.lower()
    results = []
    for product in PRODUCTS.values():
        if (
            query_lower in product.name.lower()
            or query_lower in product.sku.lower()
            or query_lower in product.warranty_coverage.lower()
            or query_lower in product.notes.lower()
        ):
            results.append(product)
    return results


def get_product_by_sku(sku: str) -> Optional[ProductInfo]:
    """Get product info by exact SKU match."""
    return PRODUCTS.get(sku.upper())


def search_troubleshooting(query: str) -> list[TroubleshootingEntry]:
    """Search troubleshooting entries by error code or description."""
    query_lower = query.lower()
    results = []
    for entry in TROUBLESHOOTING.values():
        if (
            query_lower in entry.error_code.lower()
            or query_lower in entry.description.lower()
            or query_lower in entry.product_category.lower()
        ):
            results.append(entry)
    return results


def format_product_info(product: ProductInfo) -> str:
    """Format product info for text response."""
    warranty_display = f"{product.warranty_years} year(s)" if product.warranty_years < 99 else "Lifetime"
    return f"""Product: {product.name} (SKU: {product.sku})
Warranty: {warranty_display}
Coverage: {product.warranty_coverage}
Exclusions: {product.warranty_exclusions}
Return Window: {product.return_window_days} days
Notes: {product.notes}"""


def format_troubleshooting(entry: TroubleshootingEntry) -> str:
    """Format troubleshooting entry for text response."""
    steps = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(entry.resolution_steps))
    service_note = " (Service may be required)" if entry.requires_service else ""
    return f"""Error: {entry.error_code} - {entry.description}{service_note}
Category: {entry.product_category}
Resolution Steps:
{steps}"""


def analyze_situation(
    voice_transcript: Optional[str] = None,
    image_description: Optional[str] = None,
    text_context: Optional[str] = None,
) -> dict:
    """Analyze a customer situation and recommend an action.

    Uses Gemini LLM for reasoning when available, with keyword fallback.
    The LLM can leverage rich multimodal context (voice sentiment, image
    defect analysis) that the keyword matcher cannot.
    """
    # Try LLM-backed reasoning first
    try:
        return _analyze_situation_llm(voice_transcript, image_description, text_context)
    except Exception as e:
        logger.warning(f"LLM analysis failed, falling back to keyword matcher: {e}")
        return _analyze_situation_keywords(voice_transcript, image_description, text_context)


def _analyze_situation_llm(
    voice_transcript: Optional[str] = None,
    image_description: Optional[str] = None,
    text_context: Optional[str] = None,
) -> dict:
    """Gemini-backed situation analysis.

    Builds a structured prompt from all available evidence and asks Gemini
    to select an action with reasoning.  This is the critical path that
    allows modality-native routing to show its advantage: richer voice and
    image context yields better decisions.
    """
    import json as _json
    import os

    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError("google-generativeai not installed")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    # --- Build product context from knowledge base ---
    product_context = ""
    combined_text = " ".join(filter(None, [voice_transcript, image_description, text_context]))
    for sku, product in PRODUCTS.items():
        if (sku.lower() in combined_text.lower()
                or product.name.lower() in combined_text.lower()
                or any(w in combined_text.lower() for w in product.name.lower().split() if len(w) > 4)):
            product_context += (
                f"\nProduct: {product.name} (SKU: {product.sku})\n"
                f"  Warranty: {product.warranty_years}yr | Coverage: {product.warranty_coverage}\n"
                f"  Exclusions: {product.warranty_exclusions}\n"
                f"  Return window: {product.return_window_days} days\n"
            )

    # --- Build troubleshooting context ---
    troubleshoot_context = ""
    for key, entry in TROUBLESHOOTING.items():
        if (entry.error_code.lower() in combined_text.lower()
                or any(w in combined_text.lower() for w in entry.description.lower().split() if len(w) > 5)):
            steps = "; ".join(entry.resolution_steps[:3])
            troubleshoot_context += (
                f"\nKnown issue: {entry.error_code} — {entry.description}\n"
                f"  Steps: {steps}\n"
                f"  Requires service: {entry.requires_service}\n"
            )

    valid_actions = list(WARRANTY_ACTIONS.keys())
    actions_desc = "\n".join(f"  - {k}: {v}" for k, v in WARRANTY_ACTIONS.items())

    prompt = f"""You are a customer-service decision engine for an electronics retailer.
Given the evidence below, choose exactly ONE action and provide concise reasoning.

=== VALID ACTIONS ===
{actions_desc}

=== EVIDENCE ===
Voice / Transcript:
{voice_transcript or "(none)"}

Image / Visual Analysis:
{image_description or "(none)"}

Text / Product Context:
{text_context or "(none)"}

=== MATCHING PRODUCT RECORDS ===
{product_context or "(none found)"}

=== RELEVANT TROUBLESHOOTING ===
{troubleshoot_context or "(none found)"}

=== INSTRUCTIONS ===
1. Consider ALL evidence holistically — voice tone/sentiment, visual defect
   severity, product warranty terms, and customer description.
2. If visual evidence shows physical damage AND warranty excludes drops/water,
   deny the claim.
3. If the product arrived defective (DOA/out-of-box), approve replacement.
4. Safety hazards (sparks, fire, swelling) always get immediate replacement.
5. Assembly or how-to questions get provide_instructions.
6. Technical issues with troubleshooting steps get troubleshoot_step.
7. When unsure, escalate_to_specialist.

Respond with ONLY a JSON object (no markdown fences):
{{"action": "<one of the valid actions>", "reasoning": "<1-2 sentences>", "confidence": <0.0-1.0>}}
"""

    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    parsed = _json.loads(raw)
    action = parsed.get("action", "escalate_to_specialist")
    if action not in valid_actions:
        action = "escalate_to_specialist"

    return {
        "recommended_action": action,
        "reasoning": parsed.get("reasoning", "LLM-generated decision."),
        "confidence": float(parsed.get("confidence", 0.75)),
    }


def _analyze_situation_keywords(
    voice_transcript: Optional[str] = None,
    image_description: Optional[str] = None,
    text_context: Optional[str] = None,
) -> dict:
    """Keyword-based fallback (original logic). Used when Gemini is unavailable."""
    situation_text = ""
    if voice_transcript:
        situation_text += f"Customer said: {voice_transcript}\n"
    if image_description:
        situation_text += f"Visual evidence: {image_description}\n"
    if text_context:
        situation_text += f"Context: {text_context}\n"

    situation_lower = situation_text.lower()

    if "drop" in situation_lower and ("damage" in situation_lower or "crack" in situation_lower or "bent" in situation_lower):
        return {
            "recommended_action": "deny_warranty",
            "reasoning": "Physical damage from drops is typically excluded from warranty coverage.",
            "confidence": 0.85,
        }

    if "out of the box" in situation_lower or "unbox" in situation_lower or "doa" in situation_lower:
        return {
            "recommended_action": "initiate_replacement",
            "reasoning": "Damage on arrival is covered. Product appears to have arrived defective.",
            "confidence": 0.95,
        }

    if "spark" in situation_lower or "fire" in situation_lower or "burning smell" in situation_lower or "swollen battery" in situation_lower:
        return {
            "recommended_action": "initiate_replacement",
            "reasoning": "Safety hazard identified. Immediate replacement required per safety protocol.",
            "confidence": 0.98,
        }

    if "warranty" in situation_lower and "expired" in situation_lower:
        return {
            "recommended_action": "escalate_to_specialist",
            "reasoning": "Warranty expired. Escalate to review goodwill extension options.",
            "confidence": 0.80,
        }

    if "water" in situation_lower and ("damage" in situation_lower or "wash" in situation_lower or "toilet" in situation_lower):
        return {
            "recommended_action": "deny_warranty",
            "reasoning": "Water damage is explicitly excluded from warranty coverage.",
            "confidence": 0.90,
        }

    if "assembly" in situation_lower or "step" in situation_lower or "instruction" in situation_lower:
        return {
            "recommended_action": "provide_instructions",
            "reasoning": "Customer needs assembly guidance.",
            "confidence": 0.90,
        }

    if "error" in situation_lower or "troubleshoot" in situation_lower or "not working" in situation_lower:
        return {
            "recommended_action": "troubleshoot_step",
            "reasoning": "Customer experiencing technical issue that may be resolved with troubleshooting.",
            "confidence": 0.85,
        }

    if any(x in situation_lower for x in ["month", "week", "year"]) and any(x in situation_lower for x in ["stopped", "broken", "failed", "dead"]):
        return {
            "recommended_action": "approve_warranty",
            "reasoning": "Product failure within warranty period with no exclusions identified.",
            "confidence": 0.80,
        }

    return {
        "recommended_action": "escalate_to_specialist",
        "reasoning": "Situation requires human review to determine appropriate action.",
        "confidence": 0.50,
    }
