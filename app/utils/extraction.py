

def get_group_extraction_prompt(full_text: str) -> str:
    group_extraction_prompt = """
    Task: Extract the Product Groups from the German LV-Liste text.
    Output: Return only JSON that matches the schema below—no prose.

    Input format: You will receive raw text from a PDF (German), possibly with page numbers.

    Your job:
    1.	Find the Product Groups.
    2.	Extract the title, page range, and product group number.
    3.	Normalize trivial whitespace; keep German umlauts.

    Return only JSON matching the schema below.

    {
    "type": "object",
    "properties": {
        "document_title": { "type": ["string", "null"] },
        "groups": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
            "group_no": { "type": ["string", "null"] },
            "title": { "type": "string" },
            "page_from": { "type": ["integer", "null"] },
            "page_to": { "type": ["integer", "null"] },
            },
            "required": ["title", "page_from", "page_to"]
        }
        }
    },
    "required": ["groups"]
    }
    """

    return f"""
    {group_extraction_prompt}

    Input:
    {full_text}
    """

def get_variant_extraction_prompt(prod_group_nr: str, prod_group_title: str) -> str:
    json_schema = """
    {
    "type": "object",
    "properties": {
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "variant_no": { "type": ["string", "null"] },
                    "title": { "type": "string" },
                    "page_from": { "type": ["integer", "null"] },
                    "page_to": { "type": ["integer", "null"] },
                    "text": { "type": "string" }
                    },
                "required": ["title", "page_from", "page_to"^]
            }
        }
    }
    """
    return f"""
    Task: Extract the Product Variants for the product group {prod_group_nr} {prod_group_title} from the German LV-Liste text.
    Output: Return only JSON that matches the schema below—no prose.

    Input format: You will receive raw text from a PDF (German) with the necessary information.

    Your job:
    1.	Find the Product Variants.
    2.	Extract the title, page range, product variant number, and text. The title (kurztext) is a short description of the product variant and the text is the product variant description (langtext).
    3.	Normalize trivial whitespace; keep German umlauts.

    Return only JSON matching the schema below.

    {json_schema}
    """

def get_required_components_prompt(prod_group_nr: str, prod_group_title: str, variant_nos: list[str], variant_titles: list[str], variant_texts: list[str]) -> str:
    json_schema = """
    {
    "type": "object",
    "properties": {
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "component_description": { "type": "string" },
                    "variant_nos": { "type": "array", "items": { "type": "string" } }
                },
                "required": ["component_description", "variant_nos"]
            }
        }
    }
    """

    variants_str = "\n".join([f"{v_no}: {v_title} text: {v_text}" for v_no, v_title, v_text in zip(variant_nos, variant_titles, variant_texts)])

    return f"""
    Task: Extract the required components for the product group {prod_group_nr} {prod_group_title} from the German LV-Liste text. 
    The components are the parts that are required to assemble the product. Severals variants can require the same component. 
    Output: Return only JSON that matches the schema below—no prose.

    Input format: You will receive the product variants for the product group from a PDF (German) with the necessary information.

    Your job:
    1.	Find the required components.
    2.	Extract the title, page range, and text for each required component.
    3.	Normalize trivial whitespace; keep German umlauts.

    Return only JSON matching the schema below.

    {json_schema}

    Product variants:
    {variants_str}
    """