"use client"

import { useState } from "react"
import { Eye, EyeOff, Download, Upload } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card"
import { Input } from "./ui/input"
import { Label } from "./ui/label"
import { Slider } from "./ui/slider"
import { Switch } from "./ui/switch"
import { Button } from "./ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select"
import { Textarea } from "./ui/textarea"
import { useRef, useState as useReactState } from "react"
import { useSelector } from "react-redux"
import { RootState } from "@/store/store"

interface FormViewProps {
  settings: any
  onChange: (settings: any) => void
}

export function FormView({ settings, onChange }: FormViewProps) {
  const [showLlmAdvanced, setShowLlmAdvanced] = useState(false)
  const [showLlmApiKey, setShowLlmApiKey] = useState(false)
  const [showEmbedderApiKey, setShowEmbedderApiKey] = useState(false)
  const [isUploading, setIsUploading] = useReactState(false)
  const [selectedImportFileName, setSelectedImportFileName] = useReactState("")
  const fileInputRef = useRef<HTMLInputElement>(null)
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765"
  const userId = useSelector((state: RootState) => state.profile.userId)

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

  const needsLlmApiKey = settings.mem0?.llm?.provider?.toLowerCase() !== "ollama"
  const needsEmbedderApiKey = settings.mem0?.embedder?.provider?.toLowerCase() !== "ollama"
  const isLlmOllama = settings.mem0?.llm?.provider?.toLowerCase() === "ollama"
  const isEmbedderOllama = settings.mem0?.embedder?.provider?.toLowerCase() === "ollama"

  const LLM_PROVIDERS = {
    "OpenAI": "openai",
    "Anthropic": "anthropic", 
    "Azure OpenAI": "azure_openai",
    "Ollama": "ollama",
    "Together": "together",
    "Groq": "groq",
    "Litellm": "litellm",
    "Mistral AI": "mistralai",
    "Google AI": "google_ai",
    "AWS Bedrock": "aws_bedrock",
    "Gemini": "gemini",
    "DeepSeek": "deepseek",
    "xAI": "xai",
    "LM Studio": "lmstudio",
    "LangChain": "langchain",
  }

  const EMBEDDER_PROVIDERS = {
    "OpenAI": "openai",
    "Azure OpenAI": "azure_openai", 
    "Ollama": "ollama",
    "Hugging Face": "huggingface",
    "Vertex AI": "vertexai",
    "Gemini": "gemini",
    "LM Studio": "lmstudio",
    "Together": "together",
    "LangChain": "langchain",
    "AWS Bedrock": "aws_bedrock",
  }

  return (
    <div className="space-y-8">
      {/* OpenMemory Settings */}
      <Card>
        <CardHeader>
          <CardTitle>OpenMemory Settings</CardTitle>
          <CardDescription>Configure your OpenMemory instance settings</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="custom-instructions">Custom Instructions</Label>
            <Textarea
              id="custom-instructions"
              placeholder="Enter custom instructions for memory management..."
              value={settings.openmemory?.custom_instructions || ""}
              onChange={(e) => handleOpenMemoryChange("custom_instructions", e.target.value)}
              className="min-h-[100px]"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Custom instructions that will be used to guide memory processing and fact extraction.
            </p>
          </div>
        </CardContent>
      </Card>

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
                {Object.entries(LLM_PROVIDERS).map(([provider, value]) => (
                  <SelectItem key={value} value={value}>
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

          {isLlmOllama && (
            <div className="space-y-2">
              <Label htmlFor="llm-ollama-url">Ollama Base URL</Label>
              <Input
                id="llm-ollama-url"
                placeholder="http://host.docker.internal:11434"
                value={settings.mem0?.llm?.config?.ollama_base_url || ""}
                onChange={(e) => handleLlmConfigChange("ollama_base_url", e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Leave empty to use default: http://host.docker.internal:11434
              </p>
            </div>
          )}

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
                {Object.entries(EMBEDDER_PROVIDERS).map(([provider, value]) => (
                  <SelectItem key={value} value={value}>
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

          {isEmbedderOllama && (
            <div className="space-y-2">
              <Label htmlFor="embedder-ollama-url">Ollama Base URL</Label>
              <Input
                id="embedder-ollama-url"
                placeholder="http://host.docker.internal:11434"
                value={settings.mem0?.embedder?.config?.ollama_base_url || ""}
                onChange={(e) => handleEmbedderConfigChange("ollama_base_url", e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Leave empty to use default: http://host.docker.internal:11434
              </p>
            </div>
          )}

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
        </CardContent>
      </Card>

      {/* Vector Store Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Vector Store Settings</CardTitle>
          <CardDescription>Configure your Vector Database provider and settings</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="vector-store-provider">Vector Store Provider</Label>
            <Select 
              value={settings.mem0?.vector_store?.provider || "qdrant"} 
              onValueChange={(value) => {
                onChange({
                  ...settings,
                  mem0: {
                    ...settings.mem0,
                    llm: settings.mem0?.llm,
                    embedder: settings.mem0?.embedder,
                    graph_store: settings.mem0?.graph_store,
                    vector_store: {
                      provider: value,
                      config: {
                        collection_name: "openmemory",
                        host: value === "qdrant" ? "qdrant.root.svc.cluster.local" : "",
                        port: value === "qdrant" ? 6333 : undefined,
                        api_key: "",
                      }
                    }
                  }
                })
              }}
            >
              <SelectTrigger id="vector-store-provider">
                <SelectValue placeholder="Select a provider" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="qdrant">Qdrant</SelectItem>
                <SelectItem value="chroma">Chroma</SelectItem>
                <SelectItem value="weaviate">Weaviate</SelectItem>
                <SelectItem value="redis">Redis</SelectItem>
                <SelectItem value="pgvector">PGVector</SelectItem>
                <SelectItem value="milvus">Milvus</SelectItem>
                <SelectItem value="elasticsearch">Elasticsearch</SelectItem>
                <SelectItem value="opensearch">OpenSearch</SelectItem>
                <SelectItem value="faiss">FAISS</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {true && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="vector-collection-name">Collection Name</Label>
                <Input
                  id="vector-collection-name"
                  value={settings.mem0?.vector_store?.config?.collection_name || "openmemory"}
                  onChange={(e) => {
                    onChange({
                      ...settings,
                      mem0: {
                        ...settings.mem0,
                        vector_store: {
                          ...settings.mem0?.vector_store,
                          config: {
                            ...settings.mem0?.vector_store?.config,
                            collection_name: e.target.value
                          }
                        }
                      }
                    })
                  }}
                  placeholder="openmemory"
                />
              </div>

              {["qdrant", "chroma", "weaviate", "redis", "pgvector", "milvus", "elasticsearch", "opensearch"].includes(settings.mem0?.vector_store?.provider) && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="vector-host">Host</Label>
                    <Input
                      id="vector-host"
                      value={settings.mem0?.vector_store?.config?.host || ""}
                      onChange={(e) => {
                        onChange({
                          ...settings,
                          mem0: {
                            ...settings.mem0,
                            vector_store: {
                              ...settings.mem0?.vector_store,
                              config: {
                                ...settings.mem0?.vector_store?.config,
                                host: e.target.value
                              }
                            }
                          }
                        })
                      }}
                      placeholder="localhost or env:VECTOR_HOST"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="vector-port">Port</Label>
                    <Input
                      id="vector-port"
                      type="number"
                      value={settings.mem0?.vector_store?.config?.port || ""}
                      onChange={(e) => {
                        onChange({
                          ...settings,
                          mem0: {
                            ...settings.mem0,
                            vector_store: {
                              ...settings.mem0?.vector_store,
                              config: {
                                ...settings.mem0?.vector_store?.config,
                                port: e.target.value ? parseInt(e.target.value) : undefined
                              }
                            }
                          }
                        })
                      }}
                      placeholder="6333 or env:VECTOR_PORT"
                    />
                  </div>
                </>
              )}

              <div className="space-y-2">
                <Label htmlFor="vector-api-key">API Key (Optional)</Label>
                <Input
                  id="vector-api-key"
                  type="password"
                  value={settings.mem0?.vector_store?.config?.api_key || ""}
                  onChange={(e) => {
                    onChange({
                      ...settings,
                      mem0: {
                        ...settings.mem0,
                        vector_store: {
                          ...settings.mem0?.vector_store,
                          config: {
                            ...settings.mem0?.vector_store?.config,
                            api_key: e.target.value
                          }
                        }
                      }
                    })
                  }}
                  placeholder="env:VECTOR_API_KEY"
                />
                <p className="text-xs text-muted-foreground">
                  Use "env:API_KEY" to load from environment variable, or enter directly
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Graph Store Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Graph Store Settings</CardTitle>
          <CardDescription>Configure your Graph Database provider and settings</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="graph-store-provider">Graph Store Provider</Label>
            <Select 
              value={settings.mem0?.graph_store?.provider || "neo4j"} 
              onValueChange={(value) => {
                onChange({
                  ...settings,
                  mem0: {
                    ...settings.mem0,
                    vector_store: settings.mem0?.vector_store,
                    embedder: settings.mem0?.embedder,
                    llm: settings.mem0?.llm,
                    graph_store: {
                      provider: value,
                      config: {
                        url: value === "neo4j" ? "neo4j://neo4j" : "",
                        username: value === "neo4j" ? "neo4j" : "",
                        password: "",
                        database: value === "neo4j" ? "neo4j" : "",
                      },
                      llm: null,
                      custom_prompt: null
                    }
                  }
                })
              }}
            >
              <SelectTrigger id="graph-store-provider">
                <SelectValue placeholder="Select a provider" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="neo4j">Neo4j</SelectItem>
                <SelectItem value="memgraph">Memgraph</SelectItem>
                <SelectItem value="neptune">Neptune</SelectItem>
                <SelectItem value="kuzu">Kuzu</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {true && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="graph-url">URL</Label>
                <Input
                  id="graph-url"
                  value={settings.mem0?.graph_store?.config?.url || ""}
                  onChange={(e) => {
                    onChange({
                      ...settings,
                      mem0: {
                        ...settings.mem0,
                        graph_store: {
                          ...settings.mem0?.graph_store,
                          config: {
                            ...settings.mem0?.graph_store?.config,
                            url: e.target.value
                          }
                        }
                      }
                    })
                  }}
                  placeholder="neo4j://localhost:7687 or env:NEO4J_URL"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="graph-username">Username</Label>
                <Input
                  id="graph-username"
                  value={settings.mem0?.graph_store?.config?.username || ""}
                  onChange={(e) => {
                    onChange({
                      ...settings,
                      mem0: {
                        ...settings.mem0,
                        graph_store: {
                          ...settings.mem0?.graph_store,
                          config: {
                            ...settings.mem0?.graph_store?.config,
                            username: e.target.value
                          }
                        }
                      }
                    })
                  }}
                  placeholder="neo4j or env:NEO4J_USERNAME"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="graph-password">Password</Label>
                <Input
                  id="graph-password"
                  type="password"
                  value={settings.mem0?.graph_store?.config?.password || ""}
                  onChange={(e) => {
                    onChange({
                      ...settings,
                      mem0: {
                        ...settings.mem0,
                        graph_store: {
                          ...settings.mem0?.graph_store,
                          config: {
                            ...settings.mem0?.graph_store?.config,
                            password: e.target.value
                          }
                        }
                      }
                    })
                  }}
                  placeholder="env:NEO4J_PASSWORD"
                />
                <p className="text-xs text-muted-foreground">
                  Use "env:PASSWORD" to load from environment variable, or enter directly
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="graph-database">Database</Label>
                <Input
                  id="graph-database"
                  value={settings.mem0?.graph_store?.config?.database || ""}
                  onChange={(e) => {
                    onChange({
                      ...settings,
                      mem0: {
                        ...settings.mem0,
                        graph_store: {
                          ...settings.mem0?.graph_store,
                          config: {
                            ...settings.mem0?.graph_store?.config,
                            database: e.target.value
                          }
                        }
                      }
                    })
                  }}
                  placeholder="neo4j or env:NEO4J_DB"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="graph-custom-prompt">Custom Prompt (Optional)</Label>
                <Textarea
                  id="graph-custom-prompt"
                  value={settings.mem0?.graph_store?.custom_prompt || ""}
                  onChange={(e) => {
                    onChange({
                      ...settings,
                      mem0: {
                        ...settings.mem0,
                        graph_store: {
                          ...settings.mem0?.graph_store,
                          custom_prompt: e.target.value
                        }
                      }
                    })
                  }}
                  placeholder="Custom prompt for graph store operations..."
                  className="min-h-[80px]"
                />
                <p className="text-xs text-muted-foreground">
                  Optional custom prompt for graph store operations and entity extraction.
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Backup (Export / Import) */}
      <Card>
        <CardHeader>
          <CardTitle>Backup</CardTitle>
          <CardDescription>Export or import your memories</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Export Section */}
          <div className="p-4 border border-zinc-800 rounded-lg space-y-2">
            <div className="text-sm font-medium">Export</div>
            <p className="text-xs text-muted-foreground">Download a ZIP containing your memories.</p>
            <div>
              <Button
                type="button"
                className="bg-zinc-800 hover:bg-zinc-700"
                onClick={async () => {
                  try {
                    const res = await fetch(`${API_URL}/api/v1/backup/export`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json", Accept: "application/zip" },
                      body: JSON.stringify({ user_id: userId }),
                    })
                    if (!res.ok) throw new Error(`Export failed with status ${res.status}`)
                    const blob = await res.blob()
                    const url = window.URL.createObjectURL(blob)
                    const a = document.createElement("a")
                    a.href = url
                    a.download = `memories_export.zip`
                    document.body.appendChild(a)
                    a.click()
                    a.remove()
                    window.URL.revokeObjectURL(url)
                  } catch (e) {
                    console.error(e)
                    alert("Export failed. Check console for details.")
                  }
                }}
              >
                <Download className="h-4 w-4 mr-2" /> Export Memories
              </Button>
            </div>
          </div>

          {/* Import Section */}
          <div className="p-4 border border-zinc-800 rounded-lg space-y-2">
            <div className="text-sm font-medium">Import</div>
            <p className="text-xs text-muted-foreground">Upload a ZIP exported by OpenMemory. Default settings will be used.</p>
            <div className="flex items-center gap-3 flex-wrap">
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip"
                className="hidden"
                onChange={(evt) => {
                  const f = evt.target.files?.[0]
                  if (!f) return
                  setSelectedImportFileName(f.name)
                }}
              />
              <Button
                type="button"
                className="bg-zinc-800 hover:bg-zinc-700"
                onClick={() => {
                  if (fileInputRef.current) fileInputRef.current.click()
                }}
              >
                <Upload className="h-4 w-4 mr-2" /> Choose ZIP
              </Button>
              <span className="text-xs text-muted-foreground truncate max-w-[220px]">
                {selectedImportFileName || "No file selected"}
              </span>
              <div className="ml-auto">
                <Button
                  type="button"
                  disabled={isUploading || !fileInputRef.current}
                  className="bg-primary hover:bg-primary/80 disabled:opacity-50"
                  onClick={async () => {
                    const file = fileInputRef.current?.files?.[0]
                    if (!file) return
                    try {
                      setIsUploading(true)
                      const form = new FormData()
                      form.append("file", file)
                      form.append("user_id", String(userId))
                      const res = await fetch(`${API_URL}/api/v1/backup/import`, { method: "POST", body: form })
                      if (!res.ok) throw new Error(`Import failed with status ${res.status}`)
                      await res.json()
                      if (fileInputRef.current) fileInputRef.current.value = ""
                      setSelectedImportFileName("")
                    } catch (e) {
                      console.error(e)
                      alert("Import failed. Check console for details.")
                    } finally {
                      setIsUploading(false)
                    }
                  }}
                >
                  {isUploading ? "Uploading..." : "Import"}
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
} 