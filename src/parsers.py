# Logic for parsing Swagger, Postman, and cURL
import json
import re
import yaml
import io
import os
from pypdf import PdfReader
from docx import Document

def get_gemini_client():
    """Initializes the Gemini client if the API key is present."""
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        from google import genai
        return genai.Client(api_key=api_key)
    return None

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts all text lines from an uploaded PDF file."""
    pdf_file = io.BytesIO(file_bytes)
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
        text += "\n"
    return text

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extracts all text paragraphs from an uploaded Word document."""
    docx_file = io.BytesIO(file_bytes)
    doc = Document(docx_file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

def parse_unstructured_text_with_ai(raw_text: str) -> list:
    """
    Uses Gemini AI to scan raw unstructured document text 
    and extract API details into a clean list of dictionaries.
    """
    client = get_gemini_client()
    if not client:
        print("Gemini API key missing. Cannot parse unstructured document.")
        return []

    prompt = f"""
    You are an expert Performance Engineer. Analyze the following raw text extracted from an API documentation document.
    Identify and extract all API endpoints, paths, HTTP methods, headers, and any example JSON request bodies.

    Format the final output strictly as a valid JSON array of objects. Do not include markdown blocks like ```json.
    Each object in the array MUST have this exact schema:
    [
      {{
        "path": "/api/v1/resource",
        "method": "POST",
        "summary": "Short descriptive name for the sampler",
        "headers": {{"Content-Type": "application/json", "Accept": "application/json"}},
        "body": {{"key": "value"}} or null if no body,
        "spec_status_code": "200"
      }}
    ]

    Raw Document Text:
    {raw_text}
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        clean_json_str = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_json_str)
    except Exception as e:
        print(f"AI parsing error: {e}")
        return []

def generate_mock_payload(schema: dict, all_schemas: dict) -> dict:
    """Recursively builds a structured mockup payload block."""
    if not isinstance(schema, dict):
        return {}
        
    if "properties" not in schema:
        if schema.get("type") == "array":
            items_schema = schema.get("items", {})
            if "$ref" in items_schema:
                ref_name = items_schema["$ref"].split("/")[-1]
                return [generate_mock_payload(all_schemas.get(ref_name, {}), all_schemas)]
            return []
        return {}
        
    mock_obj = {}
    for prop_name, prop_details in schema["properties"].items():
        if not isinstance(prop_details, dict):
            continue
            
        if "$ref" in prop_details:
            ref_name = prop_details["$ref"].split("/")[-1]
            mock_obj[prop_name] = generate_mock_payload(all_schemas.get(ref_name, {}), all_schemas)
        else:
            prop_type = prop_details.get("type", "string")
            defaults = {
                "string": "string_placeholder",
                "integer": 0,
                "number": 0.0,
                "boolean": True,
                "array": []
            }
            mock_obj[prop_name] = defaults.get(prop_type, "value_placeholder")
            
    return mock_obj

def parse_openapi_spec(file_content: str, is_yaml: bool = False) -> list:
    """
    Parses a Swagger/OpenAPI spec and extracts paths, methods, headers, 
    body parameters, AND the explicit response codes defined in the document.
    """
    try:
        if is_yaml:
            spec = yaml.safe_load(file_content)
        else:
            spec = json.loads(file_content)
    except Exception as e:
        print(f"Error parsing specification file: {e}")
        return []

    if not isinstance(spec, dict):
        return []

    normalized_endpoints = []
    paths = spec.get("paths", {})
    components = spec.get("components", {}).get("schemas", spec.get("definitions", {}))

    for path, path_node in paths.items():
        if not isinstance(path_node, dict):
            continue
            
        for method, method_node in path_node.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                continue
                
            summary = method_node.get("summary") or method_node.get("operationId") or f"{method.upper()} {path}"
            
            responses_node = method_node.get("responses", {})
            spec_status_code = "200"
            
            for response_key in responses_node.keys():
                if response_key.startswith("2"):
                    spec_status_code = response_key
                    break

            endpoint_info = {
                "path": path,
                "method": method.upper(),
                "summary": summary,
                "headers": {},
                "body": None,
                "spec_status_code": spec_status_code
            }
            
            request_body_node = method_node.get("requestBody")
            if request_body_node and isinstance(request_body_node, dict):
                content_types = request_body_node.get("content", {})
                if content_types:
                    preferred_ct = list(content_types.keys())[0]
                    endpoint_info["headers"]["Content-Type"] = preferred_ct
                    
                    schema_info = content_types[preferred_ct].get("schema", {})
                    if "$ref" in schema_info:
                        ref_name = schema_info["$ref"].split("/")[-1]
                        endpoint_info["body"] = generate_mock_payload(components.get(ref_name, {}), components)
                    elif schema_info.get("type") == "object":
                        endpoint_info["body"] = generate_mock_payload(schema_info, components)

            elif "parameters" in method_node:
                for param in method_node["parameters"]:
                    if isinstance(param, dict) and param.get("in") == "body":
                        schema_info = param.get("schema", {})
                        if "$ref" in schema_info:
                            ref_name = schema_info["$ref"].split("/")[-1]
                            endpoint_info["body"] = generate_mock_payload(components.get(ref_name, {}), components)
                        else:
                            endpoint_info["body"] = generate_mock_payload(schema_info, components)
                        endpoint_info["headers"]["Content-Type"] = "application/json"

            if "responses" in method_node:
                endpoint_info["headers"]["Accept"] = "application/json"

            normalized_endpoints.append(endpoint_info)
            
    return normalized_endpoints

def apply_standard_defaults(endpoints: list) -> list:
    """
    Applies standard JMeter best-practice defaults to endpoints when AI enrichment is not used.
    """
    ENTITY_ASSERTION_FIELDS = {
        "book": "title", "user": "id", "author": "name", "product": "name", "order": "id",
        "customer": "id", "item": "id", "article": "title", "post": "title", "comment": "id",
    }

    COMMON_DYNAMIC_FIELDS = {
        "title", "description", "username", "password", "firstname", "lastname", "email", "name"
    }

    for ep in endpoints:
        path = ep.get("path", "/")
        method = ep.get("method", "GET").upper()
        body = ep.get("body")
        spec_status_code = ep.get("spec_status_code", "200")

        ep["ai_assert_code"] = spec_status_code
        segments = [s for s in path.split("/") if s and "{" not in s]
        entity_name = segments[-1].lower().rstrip("s") if segments else "entity"
        ep["ai_assert_text"] = ENTITY_ASSERTION_FIELDS.get(entity_name, "id")
        ep["ai_think_min"] = "1000"
        ep["ai_think_range"] = "2000"

        path_params = re.findall(r"\{(\w+)\}", path)
        correlation_parts = []
        if method == "POST":
            correlation_parts.append(f"Extract 'id' via JSON Extractor into variable '${{{entity_name}_id}}'.")
        if path_params:
            for pname in path_params:
                correlation_parts.append(f"Path parameter '{{{pname}}}' replaced with ${{{pname}}}.")
        ep["ai_correlation"] = " | ".join(correlation_parts) if correlation_parts else "None"

        if body and isinstance(body, dict):
            dynamic_fields = [k for k in body.keys() if k.lower() in COMMON_DYNAMIC_FIELDS]
            ep["ai_parameterization"] = f"Parameterize '{', '.join(dynamic_fields)}' via CSV." if dynamic_fields else "None"
        else:
            ep["ai_parameterization"] = "None"

    return endpoints


def _call_ai_api(prompt: str, ai_config: dict) -> str:
    """
    Calls the configured AI provider and returns the raw response text.
    Handles fallbacks for structured JSON schema validation parameters across systems.
    """
    provider = ai_config.get("provider", "Google Gemini")
    model = ai_config.get("model", "gemini-2.5-flash")
    api_key = ai_config.get("api_key", "")
    base_url = ai_config.get("base_url", "").strip()

    if provider == "Google Gemini":
        from google import genai
        from google.genai import types

        if not api_key:
            raise ValueError("❌ **Google Gemini API key is missing.**")

        client = genai.Client(api_key=api_key)
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return response.text.strip()
        except Exception as e:
            raise ValueError(f"❌ **Google Gemini API error:** {e}")

    elif provider == "Anthropic":
        from anthropic import Anthropic
        if not api_key:
            raise ValueError("❌ **Anthropic API Key is missing.**")

        client = Anthropic(api_key=api_key)
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system="You are a Principal Performance Engineer. You MUST respond with a valid JSON array only. No Markdown wrapper text.",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            return response.content[0].text.replace("```json", "").replace("```", "").strip()
        except Exception as e:
            raise ValueError(f"❌ **Anthropic API error:** {e}")

    else:
        # Catch-all unified route for all OpenAI-compatible frameworks
        from openai import OpenAI
        client_kwargs = {"api_key": api_key if api_key else "not-needed"}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = OpenAI(**client_kwargs)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a Principal Performance Engineer. You MUST respond with a valid JSON array only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a Principal Performance Engineer. You MUST respond with a valid JSON array only. Return pure JSON text without markdown wraps."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1
                )
                clean_text = response.choices[0].message.content.strip()
                return clean_text.replace("```json", "").replace("```", "").strip()
            except Exception as context_error:
                raise ValueError(f"❌ **Connection Error via ({base_url or 'OpenAI Default'}):** {context_error}")


def enrich_endpoints_with_ai(endpoints: list, ai_config: dict = None) -> list:
    """
    Uses AI to analyze the complete lifecycle of API endpoints.
    """
    from dotenv import load_dotenv
    if ai_config is None:
        load_dotenv()
        ai_config = {
            "provider": "Google Gemini",
            "model": os.getenv("AI_MODEL", "gemini-2.5-flash"),
            "api_key": os.getenv("GEMINI_API_KEY"),
            "base_url": os.getenv("CUSTOM_BASE_URL", "")
        }

    provider = ai_config.get("provider", "Google Gemini")
    
    ENV_VAR_MAPPING = {
        "Google Gemini": "GEMINI_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "OpenAI Compatible / Custom": "AI_API_KEY"
    }

    active_key = ai_config.get("api_key", "").strip()
    if not active_key and provider in ENV_VAR_MAPPING:
        active_key = os.getenv(ENV_VAR_MAPPING[provider], "").strip()

    # Fallback to alternative custom keys if standard layout variant is present
    if not active_key:
        active_key = os.getenv("GROQ_API_KEY", "").strip() or os.getenv("CUSTOM_API_KEY", "").strip()
    
    # Local Ollama doesn't require a strict cloud credential validation check
    is_local_engine = (provider == "OpenAI Compatible / Custom" and "localhost" in ai_config.get("base_url", "").lower())
    
    if not is_local_engine and not active_key:
        raise ValueError(f"❌ **API Key missing for selection category: {provider}**")

    ai_config["api_key"] = active_key

    analysis_payload = [
        {
            "path": ep["path"], 
            "method": ep["method"], 
            "summary": ep["summary"],
            "body_payload": ep.get("body"),
            "spec_status_code": ep.get("spec_status_code", "200")
        }
        for ep in endpoints
    ]

    prompt = f"""
    You are a Principal Performance Engineer. Analyze these API endpoints.
    You MUST return a pure JSON array of objects with absolutely no markdown formatting backticks or wrappers. 
    Each object in the array MUST match the exact index order of the inputs and use these specific key names:
    - "response_code": string (matches spec_status_code)
    - "text_pattern": string (e.g., "title", "firstName", "id")
    - "think_min_ms": string
    - "think_range_ms": string
    - "correlation_strategy": string
    - "parameterization_strategy": string

    Sequence of Endpoints to Analyze:
    {json.dumps(analysis_payload, indent=2)}
    """

    try:
        response_text = _call_ai_api(prompt, ai_config)
        ai_predictions = json.loads(response_text)

        # Handle object wrappers safely 
        if isinstance(ai_predictions, dict):
            found_list = False
            for key, val in ai_predictions.items():
                if isinstance(val, list):
                    ai_predictions = val
                    found_list = True
                    break
            
            if not found_list:
                reconstructed = []
                for i in range(len(endpoints)):
                    str_idx = str(i)
                    if str_idx in ai_predictions:
                        reconstructed.append(ai_predictions[str_idx])
                if reconstructed:
                    ai_predictions = reconstructed

        if not isinstance(ai_predictions, list):
            print("⚠️ AI did not return a valid list structure. Falling back to standard defaults.")
            return apply_standard_defaults(endpoints)

        for idx, ep in enumerate(endpoints):
            if idx < len(ai_predictions):
                pred = ai_predictions[idx]
                assert_text = str(pred.get("text_pattern") or "id").strip()
                if not assert_text or assert_text in ["{", "}", "[", "]", "{}"]:
                    assert_text = "id"
                
                ep["ai_assert_code"] = str(pred.get("response_code") or ep.get("spec_status_code", "200"))
                ep["ai_assert_text"] = assert_text
                ep["ai_think_min"] = str(pred.get("think_min_ms") or "1000")
                ep["ai_think_range"] = str(pred.get("think_range_ms") or "2000")
                ep["ai_correlation"] = str(pred.get("correlation_strategy") or "None")
                ep["ai_parameterization"] = str(pred.get("parameterization_strategy") or "None")
        return endpoints

    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"❌ **AI Processing Failed ({provider}):** {e}")