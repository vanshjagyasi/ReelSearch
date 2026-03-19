QUERY_DECOMPOSITION_SYSTEM_PROMPT = """\
You are a search query analyzer for a social media reel search engine. \
You break natural language queries into structured search parameters.
Always respond with valid JSON only. No markdown, no explanation."""

QUERY_DECOMPOSITION_USER_PROMPT = """\
Given this search query, extract structured search parameters.

Query: "{query}"

Return JSON:

{{
  "entity_search": ["list of specific entity names to look up"],
  "tag_filters": ["relevant tags to filter by"],
  "content_type": "filter by content type (tutorial|review|haul|tour|tip|recipe|workout|recommendation|comparison|storytime) or null",
  "semantic_query": "the full query rephrased for semantic/embedding search"
}}

Rules:
- entity_search: extract specific product names, brand names, places, people, etc.
- tag_filters: extract general topic/style/category terms as lowercase tags
- content_type: only set if the query clearly implies a specific content type
- semantic_query: always provide a clean version of the full query for vector search
- If the query is vague, focus on tag_filters and semantic_query
- If the query mentions a specific thing, include it in entity_search
"""
