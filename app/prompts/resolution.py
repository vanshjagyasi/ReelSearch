RESOLUTION_SYSTEM_PROMPT = """\
You are an entity resolution system. You determine whether a newly extracted \
entity matches any existing entity in the database."""

RESOLUTION_USER_PROMPT = """\
For each item below, determine if the NEW entity matches any of the EXISTING \
candidates. The candidates were found via fuzzy text matching, so they are \
plausible but not guaranteed matches.

{entity_pairs}

For each item, respond with JSON:

{{
  "results": [
    {{
      "new_entity": "name of the new entity",
      "matched_existing_id": "UUID of the matching existing entity, or null if no match",
      "confidence": 0.0,
      "reasoning": "brief explanation"
    }}
  ]
}}

Rules:
- Match if they clearly refer to the same real-world thing
- "KALLAX shelf" and "IKEA KALLAX Bookshelf" = SAME entity
- "Apple (brand)" and "apple (fruit)" = DIFFERENT entities
- Consider the entity type — a product and a brand with similar names are different
- When in doubt, say no match (false negatives are safer than false merges)
- Only set matched_existing_id when confidence >= 0.7
"""
