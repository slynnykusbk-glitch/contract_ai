# Sample environment variables for LLM providers
# OpenAI
setx AI_PROVIDER "openai"
setx OPENAI_API_KEY ""
setx OPENAI_BASE "https://api.openai.com/v1"

# Azure OpenAI
setx AI_PROVIDER "azure"
setx AZURE_OPENAI_API_KEY ""
setx AZURE_OPENAI_ENDPOINT ""
setx AZURE_OPENAI_DEPLOYMENT ""

# Anthropic
setx AI_PROVIDER "anthropic"
setx ANTHROPIC_API_KEY ""
setx ANTHROPIC_BASE "https://api.anthropic.com/v1"

# OpenRouter
setx AI_PROVIDER "openrouter"
setx OPENROUTER_API_KEY ""
setx OPENROUTER_BASE "https://openrouter.ai/api/v1"

# Mock (default)
setx AI_PROVIDER "mock"
