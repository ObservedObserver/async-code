"use client";

import { useState, useEffect } from "react";
import { Github, CheckCircle, ArrowLeft, Settings, Key, Shield, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

import Link from "next/link";

export default function SettingsPage() {
    const [githubToken, setGithubToken] = useState("");
    const [tokenValidation, setTokenValidation] = useState<{status: string; user?: string; repo?: {name?: string; permissions?: {read?: boolean; write?: boolean; create_branches?: boolean; admin?: boolean}}; error?: string} | null>(null);
    const [isValidatingToken, setIsValidatingToken] = useState(false);
    const [repoUrl, setRepoUrl] = useState("https://github.com/ObservedObserver/streamlit-react");

    const API_BASE = typeof window !== 'undefined' && window.location.hostname === 'localhost' 
        ? 'http://localhost:5000' 
        : '/api';

    // Initialize GitHub token from localStorage
    useEffect(() => {
        if (typeof window !== 'undefined') {
            const savedToken = localStorage.getItem('github-token');
            if (savedToken) {
                setGithubToken(savedToken);
            }
        }
    }, []);

    // Save GitHub token to localStorage whenever it changes
    useEffect(() => {
        if (typeof window !== 'undefined') {
            if (githubToken.trim()) {
                localStorage.setItem('github-token', githubToken);
            } else {
                localStorage.removeItem('github-token');
            }
        }
    }, [githubToken]);

    const handleValidateToken = async () => {
        if (!githubToken.trim() || !repoUrl.trim()) {
            toast.error('Please provide both GitHub token and repository URL');
            return;
        }

        setIsValidatingToken(true);
        try {
            const response = await fetch(`${API_BASE}/validate-token`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    github_token: githubToken,
                    repo_url: repoUrl
                })
            });

            const data = await response.json();
            setTokenValidation(data);
            
            if (data.status === 'success') {
                const permissions = data.repo?.permissions || {};
                const permissionSummary = [
                    `User: ${data.user}`,
                    `Repo: ${data.repo?.name || 'N/A'}`,
                    `Read: ${permissions.read ? 'Yes' : 'No'}`,
                    `Write: ${permissions.write ? 'Yes' : 'No'}`,
                    `Create Branches: ${permissions.create_branches ? 'Yes' : 'No'}`,
                    `Admin: ${permissions.admin ? 'Yes' : 'No'}`
                ].join('\n');
                
                if (permissions.create_branches) {
                    toast.success(`✅ Token is fully valid for PR creation!\n\n${permissionSummary}`);
                } else {
                    toast.warning(`⚠️ Token validation partial success!\n\n${permissionSummary}\n\n❌ Cannot create branches - this will prevent PR creation.\nPlease ensure your token has 'repo' scope (not just 'public_repo').`);
                }
            } else {
                toast.error(`❌ Token validation failed: ${data.error}`);
            }
        } catch (error) {
            toast.error(`Error validating token: ${error}`);
            setTokenValidation({ status: 'error', error: String(error) });
        } finally {
            setIsValidatingToken(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
            {/* Header */}
            <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
                <div className="container mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <Link href="/" className="flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors">
                                <ArrowLeft className="w-4 h-4" />
                                Back
                            </Link>
                            <div className="w-8 h-8 bg-slate-700 rounded-lg flex items-center justify-center">
                                <Settings className="w-4 h-4 text-white" />
                            </div>
                            <div>
                                <h1 className="text-xl font-semibold text-slate-900">Settings</h1>
                                <p className="text-sm text-slate-500">Configure your GitHub authentication</p>
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="container mx-auto px-6 py-8 max-w-3xl">
                <div className="space-y-6">
                    {/* GitHub Authentication Section */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Github className="w-5 h-5" />
                                GitHub Authentication
                            </CardTitle>
                            <CardDescription>
                                Configure your GitHub Personal Access Token to enable repository access and PR creation
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="space-y-2">
                                <Label htmlFor="github-token" className="flex items-center gap-2">
                                    <Key className="w-4 h-4" />
                                    Personal Access Token
                                </Label>
                                <Input
                                    id="github-token"
                                    type="password"
                                    value={githubToken}
                                    onChange={(e) => setGithubToken(e.target.value)}
                                    placeholder="ghp_..."
                                    className="font-mono"
                                />
                                <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
                                    <div className="flex items-start gap-2 text-blue-800">
                                        <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                        <div className="text-sm">
                                                                                    Your token is stored locally in your browser and is required for repository access and PR creation.
                                        Make sure your token has the <strong>repo</strong> scope for full functionality.
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Test Repository URL */}
                            <div className="space-y-2">
                                <Label htmlFor="test-repo">Test Repository URL (for validation)</Label>
                                <Input
                                    id="test-repo"
                                    type="url"
                                    value={repoUrl}
                                    onChange={(e) => setRepoUrl(e.target.value)}
                                    placeholder="https://github.com/owner/repo"
                                />
                                <p className="text-sm text-slate-600">
                                    Use any accessible repository to test your token&apos;s permissions
                                </p>
                            </div>

                            {/* Validation Section */}
                            <div className="space-y-4">
                                <div className="flex items-center gap-2">
                                    <Button
                                        onClick={handleValidateToken}
                                        disabled={isValidatingToken || !githubToken.trim() || !repoUrl.trim()}
                                        variant="outline"
                                        className="gap-2"
                                    >
                                        <CheckCircle className="w-4 h-4" />
                                        {isValidatingToken ? 'Validating...' : 'Test Token'}
                                    </Button>
                                    {tokenValidation && (
                                        <div className="flex items-center gap-2">
                                            {tokenValidation.status === 'success' ? (
                                                <div className="flex items-center gap-1 text-sm text-green-600">
                                                    <CheckCircle className="w-4 h-4" />
                                                    Valid Token
                                                </div>
                                            ) : (
                                                <div className="flex items-center gap-1 text-sm text-red-600">
                                                    <Shield className="w-4 h-4" />
                                                    Invalid Token
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>

                                {tokenValidation && tokenValidation.status === 'success' && (
                                    <Card className="bg-green-50 border-green-200">
                                        <CardContent className="pt-6">
                                            <div className="space-y-2">
                                                <div className="flex items-center gap-2 text-green-800">
                                                    <CheckCircle className="w-4 h-4" />
                                                    <span className="font-medium">Token Validated Successfully</span>
                                                </div>
                                                <div className="text-sm text-green-700">
                                                    <div>User: <strong>{tokenValidation.user}</strong></div>
                                                    <div>Repository: <strong>{tokenValidation.repo?.name || 'N/A'}</strong></div>
                                                    <div className="mt-2">
                                                        <strong>Permissions:</strong>
                                                        <ul className="ml-4 mt-1 space-y-1">
                                                            <li>Read: {tokenValidation.repo?.permissions?.read ? '✅' : '❌'}</li>
                                                            <li>Write: {tokenValidation.repo?.permissions?.write ? '✅' : '❌'}</li>
                                                            <li>Create Branches: {tokenValidation.repo?.permissions?.create_branches ? '✅' : '❌'}</li>
                                                            <li>Admin: {tokenValidation.repo?.permissions?.admin ? '✅' : '❌'}</li>
                                                        </ul>
                                                    </div>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                )}

                                {tokenValidation && tokenValidation.status === 'error' && (
                                    <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                                        <div className="flex items-start gap-2 text-red-800">
                                            <Shield className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                            <div className="text-sm">
                                                <strong>Validation Error:</strong> {tokenValidation.error}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Token Creation Instructions */}
                    <Card className="bg-blue-50 border-blue-200">
                        <CardHeader>
                            <CardTitle className="text-lg">Creating a GitHub Personal Access Token</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-3 text-sm">
                                <div>
                                    <strong>1. Go to GitHub Settings</strong>
                                    <p className="text-blue-700 ml-4">Navigate to Settings → Developer settings → Personal access tokens → Tokens (classic)</p>
                                </div>
                                <div>
                                    <strong>2. Generate New Token</strong>
                                    <p className="text-blue-700 ml-4">Click &quot;Generate new token (classic)&quot; and give it a descriptive name</p>
                                </div>
                                <div>
                                    <strong>3. Required Scopes</strong>
                                    <p className="text-blue-700 ml-4">Select the <strong>repo</strong> scope for full repository access (including private repositories)</p>
                                </div>
                                <div>
                                    <strong>4. Copy and Save</strong>
                                    <p className="text-blue-700 ml-4">Copy the generated token immediately and paste it above (you won&apos;t be able to see it again)</p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </main>
        </div>
    );
} 