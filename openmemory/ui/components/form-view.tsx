"use client"

import { useState } from "react"
import { PlusCircle, Trash2, Eye, EyeOff } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card"
import { Input } from "./ui/input"
import { Label } from "./ui/label"
import { Slider } from "./ui/slider"
import { Switch } from "./ui/switch"
import { Button } from "./ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select"

interface FormViewProps {
  settings: any
  onChange: (settings: any) => void
}

export function FormView({ settings, onChange }: FormViewProps) {
  const [showLlmAdvanced, setShowLlmAdvanced] = useState(false)
  const [showLlmApiKey, setShowLlmApiKey] = useState(false)
  const [showEmbedderApiKey, setShowEmbedderApiKey] = useState(false)

  const handleOpenMemoryChange = (key: string, value: any) => {
    onChange({
      ...settings,
      openmemory: {
        ...settings.openmemory,
        [key]: value,
      },
    })
  }

  const handleLlmProviderChange = (value: string) => {
    onChange({
      ...settings,
      mem0: {
        ...settings.mem0,
        llm: {
          ...settings.mem0.llm,
          provider: value,
        },
      },
    })
  }

  const handleLlmConfigChange = (key: string, value: any) => {
    onChange({
      ...settings,
      mem0: {
        ...settings.mem0,
        llm: {
          ...settings.mem0.llm,
          config: {
            ...settings.mem0.llm.config,
            [key]: value,
          },
        },
      },
    })
  }

  const handleEmbedderProviderChange = (value: string) => {
    onChange({
      ...settings,
      mem0: {
        ...settings.mem0,
        embedder: {
          ...settings.mem0.embedder,
          provider: value,
        },
      },
    })
  }

  const handleEmbedderConfigChange = (key: string, value: any) => {
    onChange({
      ...settings,
      mem0: {
        ...settings.mem0,
        embedder: {
          ...settings.mem0.embedder,
          config: {
            ...settings.mem0.embedder.config,
            [key]: value,
          },
        },
      },
    })
  }

  const addCustomField = (section: string, configPath: string) => {
    const newField = { key: "", value: "", type: "string" }

    if (section === "openmemory") {
      onChange({
        ...settings,
        openmemory: {
          ...settings.openmemory,
          _customFields: [...(settings.openmemory._customFields || []), newField],
        },
      })
    } else if (section === "llm") {
      onChange({
        ...settings,
        mem0: {
          ...settings.mem0,
          llm: {
            ...settings.mem0.llm,
            config: {
              ...settings.mem0.llm.config,
              _customFields: [...(settings.mem0.llm.config._customFields || []), newField],
            },
          },
        },
      })
    } else if (section === "embedder") {
      onChange({
        ...settings,
        mem0: {
          ...settings.mem0,
          embedder: {
            ...settings.mem0.embedder,
            config: {
              ...settings.mem0.embedder.config,
              _customFields: [...(settings.mem0.embedder.config._customFields || []), newField],
            },
          },
        },
      })
    }
  }

  const updateCustomField = (section: string, index: number, field: string, value: any) => {
    if (section === "openmemory") {
      const customFields = [...(settings.openmemory._customFields || [])]
      customFields[index] = { ...customFields[index], [field]: value }

      onChange({
        ...settings,
        openmemory: {
          ...settings.openmemory,
          _customFields: customFields,
        },
      })
    } else if (section === "llm") {
      const customFields = [...(settings.mem0.llm.config._customFields || [])]
      customFields[index] = { ...customFields[index], [field]: value }

      onChange({
        ...settings,
        mem0: {
          ...settings.mem0,
          llm: {
            ...settings.mem0.llm,
            config: {
              ...settings.mem0.llm.config,
              _customFields: customFields,
            },
          },
        },
      })
    } else if (section === "embedder") {
      const customFields = [...(settings.mem0.embedder.config._customFields || [])]
      customFields[index] = { ...customFields[index], [field]: value }

      onChange({
        ...settings,
        mem0: {
          ...settings.mem0,
          embedder: {
            ...settings.mem0.embedder,
            config: {
              ...settings.mem0.embedder.config,
              _customFields: customFields,
            },
          },
        },
      })
    }
  }

  const removeCustomField = (section: string, index: number) => {
    if (section === "openmemory") {
      const customFields = [...(settings.openmemory._customFields || [])]
      customFields.splice(index, 1)

      onChange({
        ...settings,
        openmemory: {
          ...settings.openmemory,
          _customFields: customFields,
        },
      })
    } else if (section === "llm") {
      const customFields = [...(settings.mem0.llm.config._customFields || [])]
      customFields.splice(index, 1)

      onChange({
        ...settings,
        mem0: {
          ...settings.mem0,
          llm: {
            ...settings.mem0.llm,
            config: {
              ...settings.mem0.llm.config,
              _customFields: customFields,
            },
          },
        },
      })
    } else if (section === "embedder") {
      const customFields = [...(settings.mem0.embedder.config._customFields || [])]
      customFields.splice(index, 1)

      onChange({
        ...settings,
        mem0: {
          ...settings.mem0,
          embedder: {
            ...settings.mem0.embedder,
            config: {
              ...settings.mem0.embedder.config,
              _customFields: customFields,
            },
          },
        },
      })
    }
  }

  const needsLlmApiKey = settings.mem0?.llm?.provider?.toLowerCase() !== "ollama"
  const needsEmbedderApiKey = settings.mem0?.embedder?.provider?.toLowerCase() !== "ollama"

  const LLM_PROVIDERS = [
    "OpenAI",
    "Anthropic",
    "Azure OpenAI",
    "Ollama",
    "Together",
    "Groq",
    "Litellm",
    "Mistral AI",
    "Google AI",
    "AWS Bedrock",
    "Gemini",
    "DeepSeek",
    "xAI",
    "LM Studio",
    "LangChain",
  ]

  const EMBEDDER_PROVIDERS = [
    "OpenAI",
    "Azure OpenAI",
    "Ollama",
    "Hugging Face",
    "Vertexai",
    "Gemini",
    "Lmstudio",
    "Together",
    "LangChain",
    "AWS Bedrock",
  ]

  return (
    <div className="space-y-8">
      {/* LLM Settings */}
      <Card>
        <CardHeader>
          <CardTitle>LLM Settings</CardTitle>
          <CardDescription>Configure your Large Language Model provider and settings</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="llm-provider">LLM Provider</Label>
            <Select 
              value={settings.mem0?.llm?.provider || ""}
              onValueChange={handleLlmProviderChange}
            >
              <SelectTrigger id="llm-provider">
                <SelectValue placeholder="Select a provider" />
              </SelectTrigger>
              <SelectContent>
                {LLM_PROVIDERS.map((provider) => (
                  <SelectItem key={provider} value={provider.toLowerCase()}>
                    {provider}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="llm-model">Model</Label>
            <Input
              id="llm-model"
              placeholder="Enter model name"
              value={settings.mem0?.llm?.config?.model || ""}
              onChange={(e) => handleLlmConfigChange("model", e.target.value)}
            />
          </div>

          {needsLlmApiKey && (
            <div className="space-y-2">
              <Label htmlFor="llm-api-key">API Key</Label>
              <div className="relative">
                <Input
                  id="llm-api-key"
                  type={showLlmApiKey ? "text" : "password"}
                  placeholder="env:API_KEY"
                  value={settings.mem0?.llm?.config?.api_key || ""}
                  onChange={(e) => handleLlmConfigChange("api_key", e.target.value)}
                />
                <Button 
                  variant="ghost" 
                  size="icon" 
                  type="button" 
                  className="absolute right-2 top-1/2 transform -translate-y-1/2 h-7 w-7"
                  onClick={() => setShowLlmApiKey(!showLlmApiKey)}
                >
                  {showLlmApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Use "env:API_KEY" to load from environment variable, or enter directly
              </p>
            </div>
          )}

          <div className="flex items-center space-x-2 pt-2">
            <Switch id="llm-advanced-settings" checked={showLlmAdvanced} onCheckedChange={setShowLlmAdvanced} />
            <Label htmlFor="llm-advanced-settings">Show advanced settings</Label>
          </div>

          {showLlmAdvanced && (
            <div className="space-y-6 pt-2">
              <div className="space-y-2">
                <div className="flex justify-between">
                  <Label htmlFor="temperature">Temperature: {settings.mem0?.llm?.config?.temperature}</Label>
                </div>
                <Slider
                  id="temperature"
                  min={0}
                  max={1}
                  step={0.1}
                  value={[settings.mem0?.llm?.config?.temperature || 0.7]}
                  onValueChange={(value) => handleLlmConfigChange("temperature", value[0])}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="max-tokens">Max Tokens</Label>
                <Input
                  id="max-tokens"
                  type="number"
                  placeholder="2000"
                  value={settings.mem0?.llm?.config?.max_tokens || ""}
                  onChange={(e) => handleLlmConfigChange("max_tokens", Number.parseInt(e.target.value) || "")}
                />
              </div>
            </div>
          )}

          {/* Custom Fields for LLM */}
          {settings.mem0?.llm?.config?._customFields?.map((field: any, index: number) => (
            <div key={`llm-field-${index}`} className="grid grid-cols-[1fr,1fr,auto] gap-2 items-end">
              <div className="space-y-2">
                <Label htmlFor={`llm-key-${index}`}>Field Name</Label>
                <Input
                  id={`llm-key-${index}`}
                  placeholder="Field name"
                  value={field.key}
                  onChange={(e) => updateCustomField("llm", index, "key", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <Label htmlFor={`llm-value-${index}`}>Value</Label>
                  <Select value={field.type} onValueChange={(value) => updateCustomField("llm", index, "type", value)}>
                    <SelectTrigger className="w-24">
                      <SelectValue placeholder="Type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="string">String</SelectItem>
                      <SelectItem value="number">Number</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Input
                  id={`llm-value-${index}`}
                  placeholder="Value"
                  type={field.type === "number" ? "number" : "text"}
                  value={field.value}
                  onChange={(e) => {
                    const value = field.type === "number" ? Number(e.target.value) : e.target.value
                    updateCustomField("llm", index, "value", value)
                  }}
                />
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => removeCustomField("llm", index)}
                className="text-red-500 hover:text-red-700 hover:bg-red-50"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}

          <Button variant="outline" size="sm" onClick={() => addCustomField("llm", "")} className="mt-2">
            <PlusCircle className="mr-2 h-4 w-4" />
            Add Custom Field
          </Button>
        </CardContent>
      </Card>

      {/* Embedder Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Embedder Settings</CardTitle>
          <CardDescription>Configure your Embedding Model provider and settings</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="embedder-provider">Embedder Provider</Label>
            <Select 
              value={settings.mem0?.embedder?.provider || ""} 
              onValueChange={handleEmbedderProviderChange}
            >
              <SelectTrigger id="embedder-provider">
                <SelectValue placeholder="Select a provider" />
              </SelectTrigger>
              <SelectContent>
                {EMBEDDER_PROVIDERS.map((provider) => (
                  <SelectItem key={provider} value={provider.toLowerCase()}>
                    {provider}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="embedder-model">Model</Label>
            <Input
              id="embedder-model"
              placeholder="Enter model name"
              value={settings.mem0?.embedder?.config?.model || ""}
              onChange={(e) => handleEmbedderConfigChange("model", e.target.value)}
            />
          </div>

          {needsEmbedderApiKey && (
            <div className="space-y-2">
              <Label htmlFor="embedder-api-key">API Key</Label>
              <div className="relative">
                <Input
                  id="embedder-api-key"
                  type={showEmbedderApiKey ? "text" : "password"}
                  placeholder="env:API_KEY"
                  value={settings.mem0?.embedder?.config?.api_key || ""}
                  onChange={(e) => handleEmbedderConfigChange("api_key", e.target.value)}
                />
                <Button 
                  variant="ghost" 
                  size="icon" 
                  type="button" 
                  className="absolute right-2 top-1/2 transform -translate-y-1/2 h-7 w-7"
                  onClick={() => setShowEmbedderApiKey(!showEmbedderApiKey)}
                >
                  {showEmbedderApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Use "env:API_KEY" to load from environment variable, or enter directly
              </p>
            </div>
          )}

          {/* Custom Fields for Embedder */}
          {settings.mem0?.embedder?.config?._customFields?.map((field: any, index: number) => (
            <div key={`embedder-field-${index}`} className="grid grid-cols-[1fr,1fr,auto] gap-2 items-end">
              <div className="space-y-2">
                <Label htmlFor={`embedder-key-${index}`}>Field Name</Label>
                <Input
                  id={`embedder-key-${index}`}
                  placeholder="Field name"
                  value={field.key}
                  onChange={(e) => updateCustomField("embedder", index, "key", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <Label htmlFor={`embedder-value-${index}`}>Value</Label>
                  <Select
                    value={field.type}
                    onValueChange={(value) => updateCustomField("embedder", index, "type", value)}
                  >
                    <SelectTrigger className="w-24">
                      <SelectValue placeholder="Type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="string">String</SelectItem>
                      <SelectItem value="number">Number</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Input
                  id={`embedder-value-${index}`}
                  placeholder="Value"
                  type={field.type === "number" ? "number" : "text"}
                  value={field.value}
                  onChange={(e) => {
                    const value = field.type === "number" ? Number(e.target.value) : e.target.value
                    updateCustomField("embedder", index, "value", value)
                  }}
                />
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => removeCustomField("embedder", index)}
                className="text-red-500 hover:text-red-700 hover:bg-red-50"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}

          <Button variant="outline" size="sm" onClick={() => addCustomField("embedder", "")} className="mt-2">
            <PlusCircle className="mr-2 h-4 w-4" />
            Add Custom Field
          </Button>
        </CardContent>
      </Card>
    </div>
  )
} 