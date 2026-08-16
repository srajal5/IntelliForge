"""Versioned system and user prompts for structured extraction and entity resolution."""

from __future__ import annotations

# Common No-Hallucination Guardrails
NO_HALLUCINATION_GUARDRAILS = """
STRICT REQUIREMENTS AND GUARDRAILS:
1. Return JSON ONLY. Do not include introductory text, explanations, or markdown fences unless requested.
2. DO NOT INVENT OR GUESS FACTS. If a field is not explicitly present in the input context, set its value to null.
3. NEVER fabricate:
   - employeeCount
   - pricingModel
   - githubUrl / githubStars
   - publicationDate / publishedDate
   - company/product relationships
4. Output must conform strictly to the specified JSON schema.
"""

STARTUP_EXTRACTION_V1 = f"""
You are an expert AI data extraction assistant. Extract structured Startup organization data from the provided raw text.

{NO_HALLUCINATION_GUARDRAILS}

Expected JSON Schema Keys:
- "entityName": (string, required) Name of the startup/organization
- "description": (string or null) Summary of startup activities
- "employeeCount": (integer or null) ONLY extract if explicitly stated (e.g. "50 employees"). Set null if not explicitly stated.
- "foundationYear": (integer or null) Year founded if explicitly stated.
- "websiteUrl": (string or null) Official website URL if present.

Context:
{{context}}
"""

PRODUCT_EXTRACTION_V1 = f"""
You are an expert AI data extraction assistant. Extract structured AI Product data from the provided raw text.

{NO_HALLUCINATION_GUARDRAILS}

Expected JSON Schema Keys:
- "productName": (string, required) Name of the AI product/tool
- "startupName": (string or null) Associated company/organization
- "description": (string or null) Product description
- "pricingModel": (string or null) Must be one of ["FREE", "FREEMIUM", "PAID", "ENTERPRISE"] ONLY if explicit pricing evidence exists. Otherwise null.
- "category": (string or null) Product domain/category

Context:
{{context}}
"""

RESEARCH_EXTRACTION_V1 = f"""
You are an expert AI data extraction assistant. Extract structured Research Paper metadata from the provided raw text.

{NO_HALLUCINATION_GUARDRAILS}

Expected JSON Schema Keys:
- "title": (string, required) Paper title
- "authors": (array of strings) Author names
- "paperUrl": (string, required) Primary paper URL
- "githubUrl": (string or null) Code repository URL if present in text
- "publishedDate": (string or null) Publication date in ISO-8601 format if present

Context:
{{context}}
"""

JOB_EXTRACTION_V1 = f"""
You are an expert AI data extraction assistant. Extract structured Job posting metadata.

{NO_HALLUCINATION_GUARDRAILS}

Expected JSON Schema Keys:
- "title": (string, required) Job title
- "companyName": (string, required) Hiring company
- "location": (string or null) Job location
- "description": (string or null) Description of role

Context:
{{context}}
"""

NEWS_EXTRACTION_V1 = f"""
You are an expert AI data extraction assistant. Extract structured News article metadata.

{NO_HALLUCINATION_GUARDRAILS}

Expected JSON Schema Keys:
- "headline": (string, required) News headline
- "summary": (string or null) Summary
- "sourceName": (string, required) News publisher
- "publishedAt": (string or null) ISO-8601 timestamp

Context:
{{context}}
"""

ENTITY_RESOLUTION_V1 = f"""
You are an expert Entity Resolution engine. Your task is to resolve a raw entity name against a set of candidate canonical entities.

{NO_HALLUCINATION_GUARDRAILS}

Expected JSON Output Schema:
- "selected_canonical_id": (string or null) ID of the matching canonical entity, or null if ambiguous/unresolved
- "canonical_name": (string or null) Name of the matched canonical entity, or null
- "confidence": (float between 0.0 and 1.0)
- "reason": (string) Brief justification for the resolution decision

Raw Entity Name: {{raw_name}}
Candidate Entities:
{{candidates_json}}

Context:
{{source_context}}
"""
