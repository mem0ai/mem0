"use client";

import { useState, useEffect, FC, ReactNode } from "react";
import { motion } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import { Key, Plus, Trash2, Copy, AlertTriangle, X } from 'lucide-react';

// --- Type Definitions ---

interface ApiKey {
  id: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
}

interface ModalProps {
  children: ReactNode;
  onClose: () => void;
}

interface ButtonProps {
  children: ReactNode;
  onClick?: (e?: React.MouseEvent<HTMLButtonElement>) => void;
  variant?: 'primary' | 'danger' | 'secondary';
  [key: string]: any; // for other props like type, disabled
}

// --- Helper Components ---

const Modal: FC<ModalProps> = ({ children, onClose }) => (
  <div className="fixed inset-0 bg-black bg-opacity-70 z-50 flex justify-center items-center p-4">
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className="bg-zinc-900 rounded-lg shadow-xl p-6 border border-zinc-700 w-full max-w-md relative"
    >
      <button onClick={onClose} className="absolute top-4 right-4 text-zinc-500 hover:text-white">
        <X size={20} />
      </button>
      {children}
    </motion.div>
  </div>
);

const Button: FC<ButtonProps> = ({ children, onClick, variant = 'primary', ...props }) => {
  const baseClasses = "px-4 py-2 rounded-md font-semibold flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const variants = {
    primary: "bg-indigo-600 hover:bg-indigo-700 text-white",
    danger: "bg-red-600 hover:bg-red-700 text-white",
    secondary: "bg-zinc-700 hover:bg-zinc-600 text-white",
  };
  return (
    <button onClick={onClick} className={`${baseClasses} ${variants[variant]}`} {...props}>
      {children}
    </button>
  );
};

// --- Main Page Component ---

export default function ApiKeysPage() {
  const { user, accessToken } = useAuth();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // State for modals
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [isNewKeyModalOpen, setIsNewKeyModalOpen] = useState(false);
  
  // State for key management
  const [newKeyName, setNewKeyName] = useState("");
  const [newlyGeneratedKey, setNewlyGeneratedKey] = useState<{key: string, info: ApiKey} | null>(null);
  const [keyToRevoke, setKeyToRevoke] = useState<ApiKey | null>(null);

  const fetchKeys = async () => {
    if (!accessToken) {
      setError("Authentication token not available.");
      setIsLoading(false);
      return;
    }
    try {
      setIsLoading(true);
      const response = await fetch("/api/v1/keys/", {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to fetch API keys.");
      }
      const data = await response.json();
      setKeys(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (user && accessToken) {
      fetchKeys();
    }
  }, [user, accessToken]);

  const handleGenerateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim() || !accessToken) return;

    try {
      const response = await fetch("/api/v1/keys/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ name: newKeyName }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to generate key.");
      }
      
      const data = await response.json();
      setNewlyGeneratedKey(data);
      setIsGenerateModalOpen(false);
      setIsNewKeyModalOpen(true);
      setNewKeyName("");
      fetchKeys(); // Refresh the list
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleRevokeKey = async () => {
    if (!keyToRevoke || !accessToken) return;

    try {
      const response = await fetch(`/api/v1/keys/${keyToRevoke.id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to revoke key.");
      }

      setKeys(keys.filter(k => k.id !== keyToRevoke.id));
      setIsConfirmModalOpen(false);
      setKeyToRevoke(null);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    // Maybe show a "Copied!" toast/message
  };

  return (
    <div className="min-h-screen bg-black text-white">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex justify-between items-center mb-8"
        >
          <div>
            <h1 className="text-3xl font-bold text-white mb-2 flex items-center"><Key className="mr-3" /> API Keys</h1>
            <p className="text-zinc-400">
              Manage your API keys for connecting applications and agents to Jean.
            </p>
          </div>
          <Button onClick={() => setIsGenerateModalOpen(true)}>
            <Plus size={20} className="mr-2" />
            Generate New Key
          </Button>
        </motion.div>

        {isLoading && <p>Loading keys...</p>}
        {error && <p className="text-red-500">{error}</p>}

        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-zinc-900 border border-zinc-800 rounded-lg shadow-md"
        >
          <ul className="divide-y divide-zinc-800">
            {keys.map((key) => (
              <li key={key.id} className="p-4 flex justify-between items-center">
                <div>
                  <p className="font-semibold text-lg">{key.name}</p>
                  <p className="text-sm text-zinc-400">
                    Created on: {new Date(key.created_at).toLocaleDateString()}
                  </p>
                </div>
                <Button variant="danger" onClick={() => { setKeyToRevoke(key); setIsConfirmModalOpen(true); }}>
                  <Trash2 size={16} className="mr-2" />
                  Revoke
                </Button>
              </li>
            ))}
            {!isLoading && keys.length === 0 && (
              <p className="p-4 text-zinc-400">No API keys found. Generate one to get started.</p>
            )}
          </ul>
        </motion.div>
      </div>

      {isGenerateModalOpen && (
        <Modal onClose={() => setIsGenerateModalOpen(false)}>
          <h2 className="text-2xl font-bold mb-4">Generate New API Key</h2>
          <form onSubmit={handleGenerateKey}>
            <label htmlFor="keyName" className="block text-zinc-400 mb-2">Key Name</label>
            <input
              id="keyName"
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="e.g., My Personal Agent"
              className="w-full bg-zinc-800 border border-zinc-600 rounded-md px-3 py-2 mb-4 focus:ring-indigo-500 focus:border-indigo-500"
            />
            <div className="flex justify-end gap-3">
              <Button type="button" variant="secondary" onClick={() => setIsGenerateModalOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={!newKeyName.trim()}>Generate</Button>
            </div>
          </form>
        </Modal>
      )}

      {isNewKeyModalOpen && newlyGeneratedKey && (
        <Modal onClose={() => setIsNewKeyModalOpen(false)}>
          <h2 className="text-2xl font-bold mb-4">API Key Generated</h2>
          <div className="bg-yellow-900/30 border border-yellow-700 text-yellow-300 p-3 rounded-md mb-4 flex items-center">
            <AlertTriangle className="mr-3 flex-shrink-0" />
            <p>Please copy this key and store it securely. You will not be able to see it again.</p>
          </div>
          <div className="bg-zinc-800 p-3 rounded-md flex items-center justify-between">
            <pre className="text-sm overflow-x-auto"><code>{newlyGeneratedKey.key}</code></pre>
            <Button variant="secondary" onClick={() => copyToClipboard(newlyGeneratedKey.key)}>
              <Copy size={16} />
            </Button>
          </div>
        </Modal>
      )}
      
      {isConfirmModalOpen && keyToRevoke && (
        <Modal onClose={() => setIsConfirmModalOpen(false)}>
          <h2 className="text-2xl font-bold mb-4">Confirm Revoke</h2>
          <p className="text-zinc-300 mb-6">
            Are you sure you want to revoke the key "{keyToRevoke.name}"? This action cannot be undone.
          </p>
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={() => setIsConfirmModalOpen(false)}>Cancel</Button>
            <Button type="button" variant="danger" onClick={handleRevokeKey}>Revoke Key</Button>
          </div>
        </Modal>
      )}
    </div>
  );
} 