"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { AlertCircle, CheckCircle2 } from "lucide-react"
import { Alert, AlertDescription } from "./ui/alert"
import { Button } from "./ui/button"
import { Textarea } from "./ui/textarea"

interface JsonEditorProps {
  value: any
  onChange: (value: any) => void
}

export function JsonEditor({ value, onChange }: JsonEditorProps) {
  const [jsonString, setJsonString] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isValid, setIsValid] = useState(true)

  useEffect(() => {
    try {
      setJsonString(JSON.stringify(value, null, 2))
      setIsValid(true)
      setError(null)
    } catch (err) {
      setError("Invalid JSON object")
      setIsValid(false)
    }
  }, [value])

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setJsonString(e.target.value)
    try {
      JSON.parse(e.target.value)
      setIsValid(true)
      setError(null)
    } catch (err) {
      setError("Invalid JSON syntax")
      setIsValid(false)
    }
  }

  const handleApply = () => {
    try {
      const parsed = JSON.parse(jsonString)
      onChange(parsed)
      setIsValid(true)
      setError(null)
    } catch (err) {
      setError("Failed to apply changes: Invalid JSON")
    }
  }

  return (
    <div className="space-y-4">
      <div className="relative">
        <Textarea value={jsonString} onChange={handleTextChange} className="font-mono h-[600px] resize-none" />
        <div className="absolute top-3 right-3">
          {isValid ? (
            <CheckCircle2 className="h-5 w-5 text-green-500" />
          ) : (
            <AlertCircle className="h-5 w-5 text-red-500" />
          )}
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Button onClick={handleApply} disabled={!isValid} className="w-full">
        Apply Changes
      </Button>
    </div>
  )
} 