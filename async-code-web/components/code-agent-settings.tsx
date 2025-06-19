"use client";

import React, { useState, useEffect } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { javascript } from "@codemirror/lang-javascript";
import { githubLight } from "@uiw/codemirror-theme-github";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, Save } from "lucide-react";
import { toast } from "sonner";
import { updateUserProfile } from "@/lib/supabase-service";
import { useUserProfile } from "@/hooks/useUserProfile";

interface CodeAgentConfig {
    claudeCode?: Record<string, string>;
    codexCLI?: Record<string, string>;
}

const DEFAULT_CLAUDE_ENV = {
    ANTHROPIC_API_KEY: "",
    // Add other Claude-specific env vars here if needed
};

const DEFAULT_CODEX_ENV = {
    OPENAI_API_KEY: "",
    DISABLE_SANDBOX: "yes",
    CONTINUE_ON_BROWSER: "no",
    // Add other Codex-specific env vars here if needed
};

export function CodeAgentSettings() {
    const { profile, refreshProfile } = useUserProfile();
    const [claudeEnv, setClaudeEnv] = useState("");
    const [codexEnv, setCodexEnv] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [errors, setErrors] = useState<{ claude?: string; codex?: string }>({});

    // Load settings from profile on mount
    useEffect(() => {
        if (profile?.preferences) {
            const prefs = profile.preferences as CodeAgentConfig;
            setClaudeEnv(JSON.stringify(prefs.claudeCode || DEFAULT_CLAUDE_ENV, null, 2));
            setCodexEnv(JSON.stringify(prefs.codexCLI || DEFAULT_CODEX_ENV, null, 2));
        } else {
            setClaudeEnv(JSON.stringify(DEFAULT_CLAUDE_ENV, null, 2));
            setCodexEnv(JSON.stringify(DEFAULT_CODEX_ENV, null, 2));
        }
    }, [profile]);

    const validateJSON = (value: string, agent: "claude" | "codex") => {
        try {
            JSON.parse(value);
            setErrors(prev => ({ ...prev, [agent]: undefined }));
            return true;
        } catch (e) {
            setErrors(prev => ({ ...prev, [agent]: "Invalid JSON format" }));
            return false;
        }
    };

    const handleSave = async () => {
        // Validate both JSONs
        const isClaudeValid = validateJSON(claudeEnv, "claude");
        const isCodexValid = validateJSON(codexEnv, "codex");

        if (!isClaudeValid || !isCodexValid) {
            toast.error("Please fix JSON errors before saving");
            return;
        }

        setIsLoading(true);
        try {
            const claudeConfig = JSON.parse(claudeEnv);
            const codexConfig = JSON.parse(codexEnv);

            const preferences: CodeAgentConfig = {
                claudeCode: claudeConfig,
                codexCLI: codexConfig,
            };

            // Merge with existing preferences if any
            const existingPrefs = (profile?.preferences || {}) as Record<string, any>;
            const mergedPrefs = {
                ...existingPrefs,
                ...preferences,
            };

            await updateUserProfile({ preferences: mergedPrefs });
            await refreshProfile();
            toast.success("Code agent settings saved successfully");
        } catch (error) {
            console.error("Failed to save settings:", error);
            toast.error("Failed to save settings");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Code Agent Settings</CardTitle>
                    <CardDescription>
                        Configure environment variables for each code agent. These settings will be used when creating containers.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <Alert>
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>
                            <strong>Important:</strong> Store sensitive API keys here instead of hardcoding them. Personal settings will override default environment variables.
                        </AlertDescription>
                    </Alert>

                    {/* Claude Code Settings */}
                    <div className="space-y-2">
                        <Label htmlFor="claude-env">Claude Code Environment Variables</Label>
                        <div className="border rounded-lg overflow-hidden">
                            <CodeMirror
                                id="claude-env"
                                value={claudeEnv}
                                height="200px"
                                extensions={[javascript({ jsx: false })]}
                                theme={githubLight}
                                onChange={(value) => {
                                    setClaudeEnv(value);
                                    validateJSON(value, "claude");
                                }}
                                placeholder={JSON.stringify(DEFAULT_CLAUDE_ENV, null, 2)}
                            />
                        </div>
                        {errors.claude && (
                            <p className="text-sm text-red-500 mt-1">{errors.claude}</p>
                        )}
                        <p className="text-sm text-muted-foreground">
                            Configure environment variables for Claude Code CLI (@anthropic-ai/claude-code)
                        </p>
                    </div>

                    {/* Codex CLI Settings */}
                    <div className="space-y-2">
                        <Label htmlFor="codex-env">Codex CLI Environment Variables</Label>
                        <div className="border rounded-lg overflow-hidden">
                            <CodeMirror
                                id="codex-env"
                                value={codexEnv}
                                height="200px"
                                extensions={[javascript({ jsx: false })]}
                                theme={githubLight}
                                onChange={(value) => {
                                    setCodexEnv(value);
                                    validateJSON(value, "codex");
                                }}
                                placeholder={JSON.stringify(DEFAULT_CODEX_ENV, null, 2)}
                            />
                        </div>
                        {errors.codex && (
                            <p className="text-sm text-red-500 mt-1">{errors.codex}</p>
                        )}
                        <p className="text-sm text-muted-foreground">
                            Configure environment variables for Codex CLI (@openai/codex)
                        </p>
                    </div>

                    <Button
                        onClick={handleSave}
                        disabled={isLoading || !!errors.claude || !!errors.codex}
                        className="w-full"
                    >
                        <Save className="w-4 h-4 mr-2" />
                        {isLoading ? "Saving..." : "Save Settings"}
                    </Button>
                </CardContent>
            </Card>
        </div>
    );
}