import os
import json
import re
import streamlit as st
import requests
from pathlib import Path
from dotenv import load_dotenv

# --- App Initialization ---
load_dotenv(override=True)
if os.path.exists(".env"):
    load_dotenv(dotenv_path=".env", override=True)
elif os.path.exists("env"):
    load_dotenv(dotenv_path="env", override=True)

from src.parsers import (
    parse_openapi_spec, 
    extract_text_from_pdf, 
    extract_text_from_docx, 
    parse_unstructured_text_with_ai,
    enrich_endpoints_with_ai,
    apply_standard_defaults
)
from src.generators import generate_jmx_contents

# --- Streamlined Provider-to-env-var mapping ---
PROVIDER_ENV_MAP = {
    "Google Gemini": "GEMINI_API_KEY",
    "Anthropic": "ANTHROPIC_API_KEY",
    "OpenAI Compatible / Custom": "AI_API_KEY",
}

PROVIDER_BASE_URL_ENV_MAP = {
    "OpenAI Compatible / Custom": "CUSTOM_BASE_URL",
}

PROVIDER_MODEL_ENV_MAP = {
    "Google Gemini": "GEMINI_MODEL",
    "Anthropic": "ANTHROPIC_MODEL",
    "OpenAI Compatible / Custom": "AI_MODEL",
}


def _get_env_file_path() -> Path:
    for name in (".env", "env"):
        p = Path(name)
        if p.exists():
            return p
    return Path(".env")


# --- Persistent config ---
CONFIG_DIR = Path.home() / ".perfblueprint"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_ai_config_to_env(provider: str, api_key: str = "", model: str = "", base_url: str = ""):
    env_path = _get_env_file_path()
    updates = {"AI_PROVIDER": provider}
    
    api_key_var = PROVIDER_ENV_MAP.get(provider)
    if api_key_var and api_key:
        updates[api_key_var] = api_key
        
    model_var = PROVIDER_MODEL_ENV_MAP.get(provider)
    if model_var and model:
        updates[model_var] = model
        
    base_url_var = PROVIDER_BASE_URL_ENV_MAP.get(provider)
    if base_url_var and base_url:
        updates[base_url_var] = base_url

    lines = []
    if env_path.exists():
        raw = env_path.read_text()
        lines = raw.splitlines()

    new_lines = []
    seen_vars = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
            
        parts = stripped.split("=", 1)
        if len(parts) == 2:
            var_name = parts[0].strip()
            if var_name in updates:
                new_lines.append(f"{var_name}={updates[var_name]}")
                seen_vars.add(var_name)
                continue
        
        new_lines.append(line)

    for var_name, value in updates.items():
        if var_name not in seen_vars:
            new_lines.append(f"{var_name}={value}")

    env_path.write_text("\n".join(new_lines) + "\n")
    try:
        env_path.chmod(0o600)
    except OSError:
        pass

    load_dotenv(env_path, override=True)


def _save_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = _load_config()
    
    persistent_keys = [
        "use_ai_enhancement",
        "ai_provider",
        "url_text_input",
        "server_url",
        "protocol",
        "port",
        "num_threads",
        "ramp_time",
        "loop_option",
        "loop_count",
        "duration",
        "pacing_rate"
    ]
    
    for key in persistent_keys:
        if key in st.session_state:
            config[key] = st.session_state[key]
            
    for key in st.session_state:
        if key.startswith(("ai_model_", "ai_api_key_", "ai_base_url_")) and not key.startswith("widget_"):
            config[key] = st.session_state[key]
            
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    try:
        CONFIG_FILE.chmod(0o600)
    except OSError:
        pass

    provider = st.session_state.get("ai_provider")
    if provider:
        api_key = st.session_state.get(f"ai_api_key_{provider}", "")
        model = st.session_state.get(f"ai_model_{provider}", "")
        base_url = st.session_state.get(f"ai_base_url_{provider}", "")
        _save_ai_config_to_env(provider, api_key, model, base_url)


def _update_ai_setting(provider, field):
    widget_key = f"widget_{field}_{provider}"
    master_key = f"ai_{field}_{provider}"
    if widget_key in st.session_state:
        st.session_state[master_key] = st.session_state[widget_key]
        _save_config()


def _extract_basic_endpoints(text: str) -> list:
    """Extracts raw endpoints programmatically from unstructured text using regex."""
    endpoints = []
    seen = set()
    
    pattern_method_path = r'\b(GET|POST|PUT|DELETE|PATCH)\b\s+([\w\-\.\/\{\}]+)'
    for match in re.finditer(pattern_method_path, text, re.IGNORECASE):
        method = match.group(1).upper()
        path = match.group(2).strip()
        
        if path.startswith('/') and len(path) > 1:
            path = re.sub(r'[.,;:\"\')\]\s]+$', '', path)
            if (method, path) not in seen:
                seen.add((method, path))
                endpoints.append({
                    "method": method,
                    "path": path,
                    "summary": f"Discovered endpoint ({method} {path})",
                    "description": "Programmatically extracted baseline from document text."
                })
                
    if not endpoints:
        pattern_standalone_path = r'(/\b(?:api|v\d+)\b[\w\-\.\/\{\}]+)'
        for match in re.finditer(pattern_standalone_path, text, re.IGNORECASE):
            path = match.group(1).strip()
            path = re.sub(r'[.,;:\"\')\]\s]+$', '', path)
            if len(path) > 1 and ("GET", path) not in seen:
                seen.add(("GET", path))
                endpoints.append({
                    "method": "GET",
                    "path": path,
                    "summary": f"Discovered path ({path})",
                    "description": "Programmatically extracted baseline path route."
                })
                
    return endpoints


# Restore saved preferences into session state
saved_config = _load_config()
for key, value in saved_config.items():
    if key == "use_ai_enhancement":
        continue
    if key not in st.session_state:
        st.session_state[key] = value

if "use_ai_enhancement" not in st.session_state:
    st.session_state["use_ai_enhancement"] = False

# --- Auto-populate AI settings from environment ---
INVALID_PLACEHOLDERS = ["your_", "placeholder", "api_key_here"]

if "ai_provider" not in st.session_state or not st.session_state["ai_provider"]:
    # Fallback legacy selection mappings into the unified framework cleanly
    legacy_provider = os.getenv("AI_PROVIDER", "Google Gemini")
    if legacy_provider in ["OpenAI", "xAI Grok", "DeepSeek", "OpenRouter", "Local Ollama", "Custom (OpenAI-Compatible)"]:
        st.session_state["ai_provider"] = "OpenAI Compatible / Custom"
    else:
        st.session_state["ai_provider"] = legacy_provider

all_providers = set(list(PROVIDER_ENV_MAP.keys()) + list(PROVIDER_MODEL_ENV_MAP.keys()) + list(PROVIDER_BASE_URL_ENV_MAP.keys()))

for provider in all_providers:
    model_var = PROVIDER_MODEL_ENV_MAP.get(provider)
    model_session_key = f"ai_model_{provider}"
    if model_var and (model_session_key not in st.session_state or not st.session_state[model_session_key]):
        env_model = os.getenv(model_var, "") or os.getenv("AI_MODEL") or os.getenv("GROQ_MODEL")
        if env_model:
            st.session_state[model_session_key] = env_model

    key_var = PROVIDER_ENV_MAP.get(provider)
    key_session_key = f"ai_api_key_{provider}"
    if key_var and (key_session_key not in st.session_state or not st.session_state[key_session_key]):
        env_key = os.getenv(key_var, "") or os.getenv("GROQ_API_KEY") or os.getenv("CUSTOM_API_KEY") or os.getenv("OPENAI_API_KEY")
        if env_key and not any(p in env_key.lower() for p in INVALID_PLACEHOLDERS):
            st.session_state[key_session_key] = env_key

    url_var = PROVIDER_BASE_URL_ENV_MAP.get(provider)
    url_session_key = f"ai_base_url_{provider}"
    if url_var and (url_session_key not in st.session_state or not st.session_state[url_session_key]):
        env_url = os.getenv(url_var, "") or os.getenv("CUSTOM_BASE_URL") or os.getenv("GROQ_BASE_URL")
        if env_url:
            st.session_state[url_session_key] = env_url

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="PerfBlueprint - JMX Test Plan Creator",
    page_icon="🛠️",
    layout="wide"
)

st.markdown("""
<style>
    .block-container { padding-top: 1.2rem !important; }
    h1 { font-size: 1.5rem !important; color: #1565C0 !important; margin-bottom: 0.1rem !important; padding-bottom: 0 !important; }
    h2 { font-size: 1.15rem !important; color: #212121 !important; }
    h3 { font-size: 1rem !important; color: #212121 !important; }
    .stMarkdown p { font-size: 0.85rem !important; color: #212121 !important; margin-bottom: 0 !important; }
    .stCaption { font-size: 0.7rem !important; color: #616161 !important; }
    hr { margin-top: 0.5rem !important; margin-bottom: 0.5rem !important; }
    div[data-testid="stCheckbox"] label div[role="checkbox"] {
        border: 2px solid #1565C0 !important;
        border-radius: 4px !important;
        background-color: #E3F2FD !important;
        transform: scale(1.3) !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛠️ PerfBlueprint : AI-Augmented JMX Test Plan Generator")
st.subheader("Transform Swagger/OpenAPI/Doc/PDF API Specifications into JMeter Test Plans")
st.caption("An open-source initiative by **Vishwanatha Hebbar** • View on [GitHub](https://github.com/vthebbar/PerfBlueprint-AI) | Built with 💙 | Built for performance engineers")
st.markdown("---")

if "extracted_endpoints" not in st.session_state:
    st.session_state.extracted_endpoints = None
if "active_source" not in st.session_state:
    st.session_state.active_source = None
if "parsing_error" not in st.session_state:
    st.session_state.parsing_error = None

# --- Step 1: Ingestion Zone ---
st.header("1. Provide API Specification")
col_file, col_url = st.columns(2)

with col_file:
    st.markdown("### Option A: Upload Local File")
    uploaded_file = st.file_uploader("Choose an API Spec or Document", type=["json", "yaml", "yml", "pdf", "docx"], key="file_uploader_input")
    if uploaded_file is not None:
        file_ext = uploaded_file.name.split(".")[-1].lower()
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        
        if st.session_state.get("last_file_id") != file_id:
            st.session_state.extracted_endpoints = None
            st.session_state.last_file_id = file_id
            st.session_state.active_source = "file"
            st.session_state.parsing_error = None
            
        if st.session_state.extracted_endpoints is None and st.session_state.parsing_error is None:
            if file_ext in ["json", "yaml", "yml"]:
                with st.spinner("Parsing OpenAPI specification..."):
                    try:
                        raw_content = uploaded_file.read().decode("utf-8")
                        res = parse_openapi_spec(raw_content, is_yaml=file_ext in ["yaml", "yml"])
                        if res:
                            st.session_state.extracted_endpoints = res
                        else:
                            st.session_state.parsing_error = "OpenAPI mapping turned up empty or unreadable."
                    except Exception as e:
                        st.session_state.parsing_error = f"OpenAPI Parsing failure: {e}"
                st.rerun()
            else:
                with st.spinner("Extracting basic endpoints from document text..."):
                    try:
                        if file_ext == "pdf":
                            raw_text = extract_text_from_pdf(uploaded_file.read())
                        else:
                            raw_text = extract_text_from_docx(uploaded_file.read())
                        
                        res = _extract_basic_endpoints(raw_text)
                        if res and len(res) > 0:
                            st.session_state.extracted_endpoints = res
                            st.toast("Document text parsed programmatically!", icon="✅")
                        else:
                            st.session_state.extracted_endpoints = [{
                                "method": "GET",
                                "path": "/api/v1/placeholder",
                                "summary": "Default Baseline Endpoint",
                                "description": "No explicit routes discovered via regex scanning. Use Step 3 to enhance or map details manually."
                            }]
                            st.toast("Read text, but no explicit endpoints discovered. Used default placeholder route.", icon="ℹ️")
                    except Exception as e:
                        st.session_state.parsing_error = f"Failed to parse document text: {e}"
                st.rerun()

with col_url:
    st.markdown("### Option B: Provide Swagger Link")
    swagger_url = st.text_input("Paste your Swagger/OpenAPI URL here", placeholder="https://api.example.com/v2/api-docs", key="url_text_input", on_change=_save_config)
    
    if st.button("Fetch Specification from URL", width="stretch"):
        if not swagger_url or not swagger_url.strip():
            st.error("⚠️ Please enter a valid Swagger/OpenAPI URL before fetching.")
        else:
            with st.spinner("Connecting to remote server..."):
                try:
                    response = requests.get(swagger_url, timeout=10)
                    if response.status_code == 200:
                        raw_content = response.text
                        is_yaml = swagger_url.lower().endswith(("yaml", "yml")) or "yaml" in response.headers.get("Content-Type", "").lower()
                        st.session_state.extracted_endpoints = parse_openapi_spec(raw_content, is_yaml=is_yaml)
                        st.session_state.active_source = "url"
                        st.session_state.parsing_error = None
                        saved_config["url_text_input"] = swagger_url
                        _save_config()
                        st.toast("Successfully retrieved and parsed API details!", icon="✅")
                        st.rerun()
                    else:
                        st.error(f"Failed to pull content. Server status code: {response.status_code}")
                except Exception as e:
                    st.error(f"Could not connect to URL destination link: {e}")

if st.session_state.parsing_error:
    st.error(f"⚠️ {st.session_state.parsing_error}")

if st.session_state.extracted_endpoints:
    source_label = "📄 Uploaded File" if st.session_state.active_source == "file" else "🔗 Remote URL Link"
    st.info(f"**Active Data Source:** Currently processing specification loaded via {source_label}")
    st.success(f"Successfully processed {len(st.session_state.extracted_endpoints)} endpoints from your API specification!")
    with st.expander("🔍 View Parsed API Endpoints"):
        st.dataframe(st.session_state.extracted_endpoints, width="stretch")

# --- Step 2 & 3: Configuration Zone ---
if st.session_state.extracted_endpoints:
    st.markdown("---")
    st.header("2. Configure JMeter Parameters")
    
    st.markdown("### Target Environment Details")
    col1, col2, col3 = st.columns(3)
    with col1:
        server_url = st.text_input("Server Hostname / IP", value="api.example.com" if "server_url" not in st.session_state else st.session_state.server_url, key="server_url", on_change=_save_config)
    with col2:
        protocol = st.selectbox("Protocol", options=["https", "http"], index=0 if "protocol" not in st.session_state else ["https", "http"].index(st.session_state.protocol), key="protocol", on_change=_save_config)
    with col3:
        port = st.text_input("Port Number", value="" if "port" not in st.session_state else st.session_state.port, placeholder="e.g., 443", key="port", on_change=_save_config)

    st.markdown("### Load Simulation Profile")
    col4, col5, col6, col7 = st.columns(4)
    with col4:
        num_threads = st.number_input("Concurrent Users (Threads)", min_value=1, value=10 if "num_threads" not in st.session_state else st.session_state.num_threads, step=1, key="num_threads", on_change=_save_config)
    with col5:
        ramp_time = st.number_input("Ramp-Up Period (seconds)", min_value=0, value=20 if "ramp_time" not in st.session_state else st.session_state.ramp_time, step=1, key="ramp_time", on_change=_save_config)
    with col6:
        loop_option = st.selectbox("Execution Lifecycle (Loops)", options=["Run Once", "Specify Count", "Run Continuously (Duration Based)"], index=0 if "loop_option" not in st.session_state else ["Run Once", "Specify Count", "Run Continuously (Duration Based)"].index(st.session_state.loop_option), key="loop_option", on_change=_save_config)
    with col7:
        pacing_rate = st.number_input("Target Pacing (Loops / Min per Thread)", min_value=0.0, value=0.0 if "pacing_rate" not in st.session_state else st.session_state.pacing_rate, step=0.5, key="pacing_rate", on_change=_save_config)
    
    loop_count = 1
    duration = 0
    if st.session_state.loop_option == "Specify Count":
        loop_count = st.number_input("Loop Count Iterations", min_value=1, value=5 if "loop_count" not in st.session_state else st.session_state.loop_count, step=1, key="loop_count", on_change=_save_config)
    elif st.session_state.loop_option == "Run Continuously (Duration Based)":
        loop_count = -1
        duration = st.number_input("Target Duration Runtime (seconds)", min_value=1, value=300 if "duration" not in st.session_state else st.session_state.duration, step=10, key="duration", on_change=_save_config)

    # --- Step 3: Generation & Export Management ---
    st.markdown("---")
    st.header("3. AI-Powered Test Plan Enhancer")
    
    use_ai_enhancement = st.checkbox(
        "✨ Enable AI-Augmented Engineering (Auto-generate Smart Assertions, Think Times, Correlation & Parameterization Hints)", 
        key="use_ai_enhancement",
        on_change=_save_config
    )

    # Simplified streamlined dictionary properties maps
    provider_defaults = {
        "Google Gemini": {"models": ["gemini-2.5-flash", "gemini-2.5-pro"], "needs_key": True, "needs_url": False, "default_url": "", "key_help": "Enter your Google Gemini API key"},
        "Anthropic": {"models": ["claude-3-5-sonnet-latest", "claude-3-opus-latest"], "needs_key": True, "needs_url": False, "default_url": "", "key_help": "Enter your Anthropic API key"},
        "OpenAI Compatible / Custom": {"models": ["llama-3.3-70b-versatile", "deepseek-chat", "gpt-4o", "qwen2.5-coder:7b"], "needs_key": True, "needs_url": True, "default_url": "https://api.groq.com/openai/v1", "key_help": "Enter your custom endpoint API key (Leave blank for local Ollama)"}
    }
    
    ai_config = {}
    
    if use_ai_enhancement:
        st.markdown("#### AI Service Configuration")
        
        provider_options = list(provider_defaults.keys())
        last_provider = st.session_state.get("ai_provider") or saved_config.get("ai_provider", "Google Gemini")
        if last_provider not in provider_options:
            last_provider = "Google Gemini"
        default_provider_idx = provider_options.index(last_provider)

        col_p, col_m = st.columns(2)
        with col_p:
            ai_provider = st.selectbox("AI Provider", options=provider_options, index=default_provider_idx, key="ai_provider", on_change=_save_config)

        defaults = provider_defaults[ai_provider]
        master_model_key = f"ai_model_{ai_provider}"
        master_key_name = f"ai_api_key_{ai_provider}"
        master_url_name = f"ai_base_url_{ai_provider}"

        if master_model_key in st.session_state and st.session_state[master_model_key]:
            current_model_val = st.session_state[master_model_key]
        elif master_model_key in saved_config and saved_config[master_model_key]:
            current_model_val = saved_config[master_model_key]
        elif PROVIDER_MODEL_ENV_MAP.get(ai_provider) and os.getenv(PROVIDER_MODEL_ENV_MAP[ai_provider]):
            current_model_val = os.getenv(PROVIDER_MODEL_ENV_MAP[ai_provider])
        else:
            current_model_val = defaults["models"][0]
        st.session_state[master_model_key] = current_model_val

        if master_key_name in st.session_state and st.session_state[master_key_name]:
            current_key_val = st.session_state[master_key_name]
        elif master_key_name in saved_config and saved_config[master_key_name]:
            current_key_val = saved_config[master_key_name]
        elif PROVIDER_ENV_MAP.get(ai_provider) and os.getenv(PROVIDER_ENV_MAP[ai_provider]):
            env_key = os.getenv(PROVIDER_ENV_MAP[ai_provider], "").strip()
            if not any(p in env_key.lower() for p in INVALID_PLACEHOLDERS):
                current_key_val = env_key
            else:
                current_key_val = ""
        else:
            current_key_val = ""
        st.session_state[master_key_name] = current_key_val

        if master_url_name in st.session_state and st.session_state[master_url_name]:
            current_url_val = st.session_state[master_url_name]
        elif master_url_name in saved_config and saved_config[master_url_name]:
            current_url_val = saved_config[master_url_name]
        elif PROVIDER_BASE_URL_ENV_MAP.get(ai_provider) and os.getenv(PROVIDER_BASE_URL_ENV_MAP[ai_provider]):
            current_url_val = os.getenv(PROVIDER_BASE_URL_ENV_MAP[ai_provider])
        else:
            current_url_val = defaults.get("default_url", "")
        st.session_state[master_url_name] = current_url_val

        with col_m:
            ai_model = st.text_input(
                "AI Model Name",
                value=current_model_val,
                key=f"widget_model_{ai_provider}",
                help="Type the precise target model identifier deployment name string.",
                on_change=_update_ai_setting,
                args=(ai_provider, "model")
            )
            st.caption(f"💡 Common choices: {', '.join(defaults['models'])}")

        col_k, col_u = st.columns(2)
        with col_k:
            ai_api_key = st.text_input(
                "API Key", 
                type="password", 
                value=current_key_val, 
                key=f"widget_api_key_{ai_provider}", 
                help=defaults["key_help"], 
                on_change=_update_ai_setting, 
                args=(ai_provider, "api_key")
            )

        with col_u:
            if defaults["needs_url"]:
                ai_base_url = st.text_input("Target Base URL Mapping Connection Point", value=current_url_val, key=f"widget_base_url_{ai_provider}", on_change=_update_ai_setting, args=(ai_provider, "base_url"), placeholder="e.g., https://api.groq.com/openai/v1")
            else:
                st.caption("Uses standard platform connection layer endpoint systems configuration route natively.")
                ai_base_url = current_url_val

        ai_config = {"provider": ai_provider, "model": ai_model, "api_key": ai_api_key, "base_url": ai_base_url}
    
    def _validate_ai_config(ai_config: dict) -> list:
        errors = []
        provider = ai_config.get("provider", "")
        model = ai_config.get("model", "").strip()
        api_key = ai_config.get("api_key", "").strip()
        base_url = ai_config.get("base_url", "").strip()

        if not model:
            errors.append("**AI Model Name** field validation is required.")
        
        is_local_engine = "localhost" in base_url.lower() or "127.0.0.1" in base_url.lower()
        if not is_local_engine and not api_key:
            errors.append(f"**API Key** validation parameter is required for remote executions via provider ({provider}).")
            
        if provider == "OpenAI Compatible / Custom" and not base_url:
            errors.append("**Target Base URL Configuration Route** is required for OpenAI generic proxies compatibility models.")
        return errors

    if st.button("Build JMX Test Plan Structure", type="primary"):
        if use_ai_enhancement:
            validation_errors = _validate_ai_config(ai_config)
            if validation_errors:
                for err in validation_errors:
                    st.error(f"⚠️ {err}")
                st.stop()

        with st.spinner("Compiling JMX structure maps..."):
            try:
                final_endpoints = list(st.session_state.extracted_endpoints)
                if use_ai_enhancement:
                    final_endpoints = enrich_endpoints_with_ai(final_endpoints, ai_config)
                else:
                    final_endpoints = apply_standard_defaults(final_endpoints)

                jmeter_config = {
                    "server": server_url, "protocol": protocol, "port": port,
                    "threads": num_threads, "ramp_up": ramp_time, "loop_count": loop_count,
                    "duration": duration, "use_duration": True if loop_count == -1 else False, "pacing": pacing_rate
                }
                
                jmx_output_data = generate_jmx_contents(final_endpoints, jmeter_config)
                _save_config()
                
                st.success("🎉 Your JMeter Test Plan has been generated successfully!")
                
                # 🛠️ FIXED Layout warning parameter here: changed use_container_width=True to width="stretch"
                st.download_button(
                    label="⬇️ Download Generated .jmx File", 
                    data=jmx_output_data, 
                    file_name="perf_blueprint_ai_test_plan.jmx", 
                    mime="application/xml", 
                    width="stretch"
                )
            except Exception as e:
                st.error(f"⚠️ An unexpected error occurred: {e}")