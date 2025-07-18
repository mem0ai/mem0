# 自定义OpenAI API配置指南

Mem0现在支持使用自定义OpenAI API URL和API KEY，这使您可以连接到兼容OpenAI API的第三方服务，如Azure OpenAI、本地部署的模型（如ollama、LocalAI等）或其他服务提供商。

## 配置方法

### 方法1：环境变量

您可以通过设置以下环境变量来配置自定义API：

```bash
# 自定义OpenAI API URL
export CUSTOM_OPENAI_API_URL=https://your-custom-api-endpoint.com/v1

# 自定义OpenAI API KEY
export CUSTOM_OPENAI_API_KEY=your_custom_api_key_here
```

### 方法2：Docker环境变量

如果您使用Docker部署，可以在`docker-compose.yaml`文件中配置环境变量：

```yaml
services:
  mem0:
    # 其他配置...
    environment:
      - CUSTOM_OPENAI_API_URL=https://your-custom-api-endpoint.com/v1
      - CUSTOM_OPENAI_API_KEY=your_custom_api_key_here
```

或者在运行Docker容器时设置环境变量：

```bash
docker run -e CUSTOM_OPENAI_API_URL=https://your-custom-api-endpoint.com/v1 -e CUSTOM_OPENAI_API_KEY=your_custom_api_key_here mem0ai/mem0
```

### 方法3：.env文件

您还可以在`.env`文件中设置这些变量：

```
# 自定义OpenAI API 配置
CUSTOM_OPENAI_API_URL=https://your-custom-api-endpoint.com/v1
CUSTOM_OPENAI_API_KEY=your_custom_api_key_here
```

## 注意事项

1. 如果同时设置了标准的`OPENAI_API_KEY`和自定义的`CUSTOM_OPENAI_API_KEY`，系统将优先使用自定义的API KEY。

2. 如果您设置了自定义API URL，请确保该API实现了与OpenAI兼容的接口，包括：
   - 兼容的模型名称
   - 兼容的API请求和响应格式
   - 对应的嵌入模型支持

3. 一些常见的兼容OpenAI API的服务：
   - Azure OpenAI
   - LocalAI
   - Ollama
   - OpenRouter
   - TogetherAI
   - Anthropic Claude (通过适配器)

## 示例：连接到Azure OpenAI

```bash
export CUSTOM_OPENAI_API_URL=https://{your-resource-name}.openai.azure.com/openai/deployments/{deployment-id}
export CUSTOM_OPENAI_API_KEY={your-azure-api-key}
```

## 示例：连接到本地Ollama实例

```bash
export CUSTOM_OPENAI_API_URL=http://localhost:11434/v1
export CUSTOM_OPENAI_API_KEY=ollama
```

## 排错指南

如果您在使用自定义API时遇到问题，请检查：

1. API URL格式是否正确，特别是是否包含了`/v1`路径
2. API KEY是否正确设置
3. 您的自定义API服务是否正常运行且能够访问
4. 网络连接是否正常，防火墙是否允许相应端口的流量 