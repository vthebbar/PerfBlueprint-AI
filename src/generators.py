# Logic for building and writing the JMX XML structure
import json
import xml.sax.saxutils as saxutils
import re

def escape_xml(data: str) -> str:
    if not data:
        return ""
    return saxutils.escape(data)

def get_entity_var_name(path: str) -> str:
    """Contextually derives a clean entity-bound variable suffix from the path."""
    segments = [s for s in path.split("/") if s and "{" not in s]
    if segments:
        return segments[-1].lower().rstrip('s') + "_id"
    return "entity_id"

def build_header_manager_xml(headers: dict) -> str:
    #  FIXED: Changed from returning "<hashTree/>" to "" so it doesn't corrupt the pairing sequence when empty
    if not headers:
        return ""
    header_items_xml = ""
    for name, value in headers.items():
        header_items_xml += f"""          <elementProp name="" elementType="Header">
            <stringProp name="Header.name">{escape_xml(name)}</stringProp>
            <stringProp name="Header.value">{escape_xml(value)}</stringProp>
          </elementProp>\n"""
    return f"""<HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="HTTP Header Manager" enabled="true">
        <collectionProp name="HeaderManager.headers">
{header_items_xml}        </collectionProp>
      </HeaderManager>
      <hashTree/>"""

def build_sampler_xml(endpoint: dict) -> str:
    path = endpoint.get("path", "/")
    method = endpoint.get("method", "GET")
    summary = endpoint.get("summary", f"{method} {path}")
    body = endpoint.get("body")
    headers = endpoint.get("headers", {})

    assert_code = endpoint.get("ai_assert_code", "200")
    assert_text = endpoint.get("ai_assert_text", "")
    think_min = endpoint.get("ai_think_min", "1000")
    think_range = endpoint.get("ai_think_range", "2000")
    ai_correlation = endpoint.get("ai_correlation", "None")

    var_name = get_entity_var_name(path)
    path_cleaned = path
    if "{" in path:
        path_cleaned = re.sub(r'\{.*?\}', f"${{{var_name}}}", path)

    is_post_body_raw = "true" if body else "false"
    arguments_xml = ""
    if body:
        if isinstance(body, dict):
            parameterized_body = {}
            for k, v in body.items():
                if k.lower() in ["title", "description", "username", "password", "firstname", "lastname", "email"]:
                    parameterized_body[k] = f"${{{k}}}"
                else:
                    parameterized_body[k] = v
            json_body_str = json.dumps(parameterized_body, indent=2)
        else:
            json_body_str = json.dumps(body, indent=2)

        arguments_xml = f"""          <elementProp name="" elementType="HTTPArgument">
            <boolProp name="HTTPArgument.always_encode">false</boolProp>
            <stringProp name="Argument.value">{escape_xml(json_body_str)}</stringProp>
            <stringProp name="Argument.metadata">=</stringProp>
          </elementProp>"""

    header_manager_block = build_header_manager_xml(headers)

    # 🛠️ FIXED: Changed name="Assertion.test_strings" to name="Asserion.test_strings" (JMeter core typo requirement)
    code_assertion_xml = f"""      <ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="Verify Status Code: {assert_code}" enabled="true">
        <collectionProp name="Asserion.test_strings">
          <stringProp name="">{assert_code}</stringProp>
        </collectionProp>
        <stringProp name="Assertion.custom_message"></stringProp>
        <stringProp name="Assertion.test_field">Assertion.response_code</stringProp>
        <boolProp name="Assertion.assume_success">false</boolProp>
        <intProp name="Assertion.test_type">8</intProp> </ResponseAssertion>
      <hashTree/>"""

    text_assertion_xml = ""
    if assert_text:
        # 🛠️ FIXED: Changed name="Assertion.test_strings" to name="Asserion.test_strings" (JMeter core typo requirement)
        text_assertion_xml = f"""      <ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="Verify Body Text contains: {escape_xml(assert_text)}" enabled="true">
        <collectionProp name="Asserion.test_strings">
          <stringProp name="">{escape_xml(assert_text)}</stringProp>
        </collectionProp>
        <stringProp name="Assertion.custom_message"></stringProp>
        <stringProp name="Assertion.test_field">Assertion.response_data</stringProp>
        <boolProp name="Assertion.assume_success">false</boolProp>
        <intProp name="Assertion.test_type">16</intProp> </ResponseAssertion>
      <hashTree/>"""

    # Automatic JSON extraction fallback for POST requests
    correlation_extractor_xml = ""
    if method == "POST":
        correlation_extractor_xml = f"""      <JSONPostProcessor guiclass="JSONPostProcessorGui" testclass="JSONPostProcessor" testname="JSON Extractor - Extract {var_name}" enabled="true">
        <stringProp name="JSONPostProcessor.referenceNames">{var_name}</stringProp>
        <stringProp name="JSONPostProcessor.jsonPathExprs">$.id</stringProp>
        <stringProp name="JSONPostProcessor.match_numbers">1</stringProp>
        <stringProp name="JSONPostProcessor.default_values">{var_name}_NOT_FOUND</stringProp>
      </JSONPostProcessor>
      <hashTree/>\n"""

    think_timer_xml = f"""      <UniformRandomTimer guiclass="UniformRandomTimerGui" testclass="UniformRandomTimer" testname="Think Time" enabled="true">
        <stringProp name="ConstantTimer.delay">{think_min}</stringProp>
        <stringProp name="RandomTimer.range">{think_range}</stringProp>
      </UniformRandomTimer>
      <hashTree/>"""

    return f"""      <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="{escape_xml(summary)}" enabled="true">
        <stringProp name="HTTPSampler.path">{escape_xml(path_cleaned)}</stringProp>
        <stringProp name="HTTPSampler.method">{method}</stringProp>
        <boolProp name="HTTPSampler.follow_redirects">true</boolProp>
        <boolProp name="HTTPSampler.use_keepalive">true</boolProp>
        <boolProp name="HTTPSampler.postBodyRaw">{is_post_body_raw}</boolProp>
        <elementProp name="HTTPsampler.Arguments" elementType="Arguments" guiclass="HTTPArgumentsPanel" testclass="Arguments" enabled="true">
          <collectionProp name="Arguments.arguments">
{arguments_xml}
          </collectionProp>
        </elementProp>
      </HTTPSamplerProxy>
      <hashTree>
        {header_manager_block}
        {code_assertion_xml}
        {text_assertion_xml}
        {correlation_extractor_xml}
        {think_timer_xml}
      </hashTree>\n"""

def generate_jmx_contents(endpoints: list, config: dict) -> str:
    if config["loop_count"] == -1:
        loop_controller_xml = """<boolProp name="LoopController.continue_forever">false</boolProp>
        <stringProp name="LoopController.loops">-1</stringProp>"""
    else:
        loop_controller_xml = f"""<boolProp name="LoopController.continue_forever">false</boolProp>
        <stringProp name="LoopController.loops">{config['loop_count']}</stringProp>"""

    scheduler_bool = "true" if config["use_duration"] else "false"

    all_samplers_xml = ""
    for endpoint in endpoints:
        all_samplers_xml += build_sampler_xml(endpoint)

    needs_csv = any(
        ep.get("ai_parameterization", "None").lower() != "none" or ep.get("body") is not None 
        for ep in endpoints
    )
    
    csv_config_xml = ""
    if needs_csv:
        csv_config_xml = """      <CSVDataSet guiclass="TestBeanGUI" testclass="CSVDataSet" testname="CSV Data Set Config - Dynamic Test Data Pool" enabled="true">
        <stringProp name="delimiter">,</stringProp>
        <stringProp name="fileEncoding">UTF-8</stringProp>
        <stringProp name="filename">test_data.csv</stringProp>
        <boolProp name="ignoreFirstLine">false</boolProp>
        <boolProp name="quotedData">false</boolProp>
        <boolProp name="recycle">true</boolProp>
        <stringProp name="shareMode">shareMode.all</stringProp>
        <boolProp name="stopThread">false</boolProp>
        <stringProp name="variableNames">title,description,userName,password,firstName,lastName,email</stringProp>
      </CSVDataSet>
      <hashTree/>\n"""

    pacing_xml = ""
    pacing_val = float(config.get("pacing", 0.0))
    if pacing_val > 0:
        pacing_xml = f"""      <ConstantThroughputTimer guiclass="TestBeanGUI" testclass="ConstantThroughputTimer" testname="Global Pacing Timer" enabled="true">
        <intProp name="calcMode">0</intProp>
        <stringProp name="throughput">{pacing_val}</stringProp>
      </ConstantThroughputTimer>
      <hashTree/>\n"""

    jmx_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Test Plan Created By PerfBlueprint" enabled="true">
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <boolProp name="TestPlan.tearDown_on_shutdown">false</boolProp>
      <boolProp name="TestPlan.serialize_threadgroups">false</boolProp>
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">
        <collectionProp name="Arguments.arguments"/>
      </elementProp>
    </TestPlan>
    <hashTree>
      <ConfigTestElement guiclass="HttpDefaultsGui" testclass="ConfigTestElement" testname="HTTP Request Defaults" enabled="true">
        <stringProp name="HTTPSampler.domain">{escape_xml(config['server'])}</stringProp>
        <stringProp name="HTTPSampler.port">{escape_xml(config['port'])}</stringProp>
        <stringProp name="HTTPSampler.protocol">{config['protocol']}</stringProp>
        <elementProp name="HTTPsampler.Arguments" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">
          <collectionProp name="Arguments.arguments"/>
        </elementProp>
      </ConfigTestElement>
      <hashTree/>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="Thread Group" enabled="true">
        <intProp name="ThreadGroup.num_threads">{config['threads']}</intProp>
        <intProp name="ThreadGroup.ramp_time">{config['ramp_up']}</intProp>
        <longProp name="ThreadGroup.duration">{config['duration']}</longProp>
        <boolProp name="ThreadGroup.scheduler">{scheduler_bool}</boolProp>
        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="Loop Controller" enabled="true">
          {loop_controller_xml}
        </elementProp>
      </ThreadGroup>
      <hashTree>
{csv_config_xml}{pacing_xml}{all_samplers_xml}      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>"""

    return jmx_template