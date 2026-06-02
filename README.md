# PerfBlueprint: AI-Augmented JMX Test Plan Generator

**PerfBlueprint** is a clean, lightweight Streamlit web application designed to accelerate performance testing workflows. It transforms API documentation—such as Swagger/OpenAPI specifications, raw text, PDFs, or Word documents—directly into structured Apache JMeter (`.jmx`) test plans.


### AI Model Selection

With optional built-in AI augmentation capabilities, it goes beyond basic parsing to auto-generate smart assertions, realistic think times, and dynamic variable correlation strategies.

The accuracy of the generated performance test script depends on your choice of provider. Selecting a more advanced AI model will produce a higher-quality test plan with cleaner correlation strategies, smart think-times, and realistic test data parameterization.

---

##  Key Features

* **Flexible Ingestion:** Upload local files (`.json`, `.yaml`, `.pdf`, `.docx`) or fetch an OpenAPI spec directly using a live URL.
* **JMeter Test Plan Generation:** Instantly outputs production-ready `.jmx` structures complete with Thread Groups, HTTP Request Defaults, and Header Managers.
* **Custom Load Profiles:** Easily configure concurrent users (threads), ramp-up cycles, pacing rates, and loop frequencies from a simple UI.
* **AI-Augmented Engineering:** Optionally integrate with major AI models (Google Gemini, OpenAI, DeepSeek, Anthropic, etc.) to inject intelligent status code checks, response verifications, and parameter handling.
* **Persistent Preferences:** Automatically saves layout state and configuration parameters locally so you never lose your workspace setup.

---

## 🛠️ Prerequisites

Before launching the tool, ensure you have the following installed on your machine:

* **Python 3.9 or higher**
* **pip** (Python package installer)

---

## 📦 Installation & Setup

1. **Clone or copy** the project files into a local directory on your machine.
2. Rename `env.example` to `env` or `env` file in the project root directory (if you skip this step `.env` file will be automatically created in the project root directory)  
---

## 🖥️ How to Run the App

### On Windows:

Simply double-click the `run.bat` file inside project root directory.

---


### On Mac / Linux:

1. Open your Terminal inside your project directory.
2. Use one of the below option to start the application

 Option 1: Grant execution permissions and run the script using this command:

```bash
chmod +x run.sh && ./run.sh
```

 Option 2: Start application using bash command

```bash
bash run.sh
```
---

## 📖 How to Use PerfBlueprint

1. **Provide API Specification:** Upload your API specification file or paste a live Swagger JSON/YAML URL link and click **Fetch Specification from URL**.
2. **Configure JMeter Parameters:** * Set your target environment details (Server Hostname, Protocol, and Port).
* Define your performance testing profile (Concurrent Users, Ramp-up, and Lifecycle options).


3. **AI-Powered Enhancements (Optional):** Check the box to enable AI-Augmented Engineering. Choose your favorite AI provider from the dropdown, supply your API key, and specify the model name.
4. **Build and Export:** Click **Build JMX Test Plan Structure**. Once the build finishes successfully, click the download button to grab your fully-formed `.jmx` file, ready to open directly inside Apache JMeter.




Here is the AI configuration table for all the providers supported in your application.

## Table A:

| AI Provider | *AI Model Name  | Base URL (Auto-populated or Default) | API Key |
| --- | --- | --- | --- |
| **Google Gemini** | `gemini-2.5-flash` | *Not applicable (Uses native SDK)* | Get API key from [Google AI Studio](https://aistudio.google.com/) |
| **Anthropic** | `claude-3-5-sonnet-latest` | *Not applicable (Uses native SDK)* | Get API key from [Anthropic Console](https://console.anthropic.com/) |
| **OpenAI Compatible / Custom** | Refer to Table B below. | Refer to Table B below. | Refer to Table B below. |

**Note** : *AI Model Name: You may use other available models from selected provider as well.


Below table details the setup requirements for various third-party and custom backends when using the OpenAI Compatible / Custom option in the dropdown layout configuration.

### Table B: OpenAI Compatible / Custom Models

This table details the setup requirements for various third-party and custom backends when using the **OpenAI Compatible / Custom** option in the dropdown layout configuration:

| Provider | AI Provider Dropdown Value | *AI Model Name  | Base URL | API Key |
| --- | --- | --- | --- | --- |
| **GroqCloud** | `OpenAI Compatible / Custom` | `llama-3.3-70b-versatile` | `https://api.groq.com/openai/v1` | Get API key from GroqCloud Console |
| **DeepSeek** | `OpenAI Compatible / Custom` | `deepseek-v4-flash` | `https://api.deepseek.com/v1` | Get API key from DeepSeek Platform |
| **OpenRouter** | `OpenAI Compatible / Custom` | `openrouter/free` | `https://openrouter.ai/api/v1` | Get API key from OpenRouter Dashboard |
| **Local Ollama** | `OpenAI Compatible / Custom` | `qwen2.5-coder:7b` | `http://localhost:11434/v1` | *Not required (Runs locally)* |
| **OpenAI** | `OpenAI Compatible / Custom` | `gpt-4o` / `gpt-4o-mini` | `https://api.openai.com/v1` | Get API key from OpenAI Platform |
| **xAI Grok** | `OpenAI Compatible / Custom` | `grok-4.3` | `https://api.x.ai/v1` | Get API key from xAI Cloud Console |

**Note** : *AI Model Name: You may use other available models from selected provider as well.



---

<p align="center">
  An initiative by <a href="https://github.com/vthebbar" target="_blank"><b>Vishwanatha Hebbar</b></a> <br>
  <b>Powered by AI</b> • Built with 💙 |• Built for performance engineers |
</p>