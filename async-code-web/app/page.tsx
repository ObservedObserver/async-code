"use client";

import { useState, useEffect } from "react";
import { Github, GitBranch, Code2, ExternalLink, CheckCircle, Clock, XCircle, AlertCircle, FileText, Eye, GitCommit, Bell, Settings, LogOut, User, FolderGit2, Plus } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { ProtectedRoute } from "@/components/protected-route";
import { TaskStatusBadge } from "@/components/task-status-badge";
import { PRStatusBadge } from "@/components/pr-status-badge";
import { useAuth } from "@/contexts/auth-context";
import { ApiService } from "@/lib/api-service";
import { SupabaseService } from "@/lib/supabase-service";
import { Project, Task } from "@/types";
import { ClaudeIcon } from "@/components/icon/claude";
import { OpenAIIcon } from "@/components/icon/openai";
import { toast } from "sonner";

interface TaskWithProject extends Task {
    project?: Project
}

export default function Home() {
    const { user, signOut } = useAuth();
    const [prompt, setPrompt] = useState("");
    const [selectedProject, setSelectedProject] = useState<string>("");
    const [branch, setBranch] = useState("main");
    const [githubToken, setGithubToken] = useState("");
    const [model, setModel] = useState("claude");
    const [tasks, setTasks] = useState<TaskWithProject[]>([]);
    const [projects, setProjects] = useState<Project[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [showNotification, setShowNotification] = useState(false);
    const [notificationMessage, setNotificationMessage] = useState("");

    // Initialize GitHub token from localStorage
    useEffect(() => {
        if (typeof window !== 'undefined') {
            const savedToken = localStorage.getItem('github-token');
            if (savedToken) {
                setGithubToken(savedToken);
            }
        }
    }, []);

    // Load initial data
    useEffect(() => {
        if (user?.id) {
            loadProjects();
            loadTasks();
        }
    }, [user?.id]);

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

    // Poll task status for running tasks
    useEffect(() => {
        if (!user?.id) return;

        const runningTasks = tasks.filter(task => task.status === "running" || task.status === "pending");
        if (runningTasks.length === 0) return;

        const interval = setInterval(async () => {
            try {
                const updatedTasks = await Promise.all(
                    runningTasks.map(task => SupabaseService.getTask(task.id))
                );

                setTasks(prevTasks => 
                    prevTasks.map(task => {
                        const updated = updatedTasks.find(t => t && t.id === task.id);
                        if (updated) {
                            // Check for status changes to show notifications
                            if (task.status !== updated.status) {
                                if (updated.status === "completed") {
                                    setNotificationMessage(`🎉 Task #${task.id} completed successfully!`);
                                    setShowNotification(true);
                                    setTimeout(() => setShowNotification(false), 5000);
                                } else if (updated.status === "failed") {
                                    setNotificationMessage(`❌ Task #${task.id} failed. Check details for more info.`);
                                    setShowNotification(true);
                                    setTimeout(() => setShowNotification(false), 5000);
                                }
                            }
                            return { ...task, ...updated };
                        }
                        return task;
                    })
                );
            } catch (error) {
                console.error('Error polling task status:', error);
            }
        }, 2000);

        return () => clearInterval(interval);
    }, [tasks, user?.id]);

    const loadProjects = async () => {
        if (!user?.id) return;
        
        try {
            const projectData = await ApiService.getProjects(user.id);
            setProjects(projectData);
        } catch (error) {
            console.error('Error loading projects:', error);
        }
    };

    const loadTasks = async () => {
        if (!user?.id) return;
        
        try {
            const taskData = await SupabaseService.getTasks();
            setTasks(taskData);
        } catch (error) {
            console.error('Error loading tasks:', error);
        }
    };

    const handleStartTask = async () => {
        if (!prompt.trim() || !githubToken.trim()) {
            toast.error('Please provide both a prompt and GitHub token');
            return;
        }

        if (!user?.id) {
            toast.error('User not authenticated');
            return;
        }

        let repoUrl = "";
        let projectId = undefined;

        if (selectedProject && selectedProject !== "custom") {
            const project = projects.find(p => p.id.toString() === selectedProject);
            if (project) {
                repoUrl = project.repo_url;
                projectId = project.id;
            }
        } else {
            // Custom repo URL - would need an input field for this
            toast.error('Custom repo URL input not implemented yet. Please select a project or create one first.');
            return;
        }

        setIsLoading(true);
        try {
            const response = await ApiService.startTask(user.id, {
                prompt: prompt.trim(),
                repo_url: repoUrl,
                branch: branch,
                github_token: githubToken,
                model: model,
                project_id: projectId
            });

            // Create a new task object for immediate display
            const newTask = {
                id: response.task_id,
                status: "pending",
                repo_url: repoUrl,
                target_branch: branch,
                agent: model,
                chat_messages: [{
                    role: 'user',
                    content: prompt.trim(),
                    timestamp: new Date().toISOString()
                }],
                created_at: new Date().toISOString(),
                user_id: user.id,
                project_id: projectId || null,
                project: projects.find(p => p.id === projectId)
            } as unknown as TaskWithProject;

            setTasks(prev => [newTask, ...prev]);
            setPrompt("");
            
            // Show success notification
            setNotificationMessage(`🚀 Task #${response.task_id} started successfully!`);
            setShowNotification(true);
            setTimeout(() => setShowNotification(false), 5000);
        } catch (error) {
            toast.error(`Error starting task: ${error}`);
        } finally {
            setIsLoading(false);
        }
    };

    const getStatusVariant = (status: string) => {
        switch (status) {
            case "pending": return "secondary";
            case "running": return "default";
            case "completed": return "default";
            case "failed": return "destructive";
            default: return "outline";
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case "pending": return <Clock className="w-3 h-3" />;
            case "running": return <AlertCircle className="w-3 h-3" />;
            case "completed": return <CheckCircle className="w-3 h-3" />;
            case "failed": return <XCircle className="w-3 h-3" />;
            default: return null;
        }
    };

    const getAgentIcon = (agent: string) => {
        switch (agent) {
            case "claude": return <ClaudeIcon className="w-3 h-3" />;
            case "codex": return <OpenAIIcon className="w-3 h-3" />;
            default: return null;
        }
    };

    return (
        <ProtectedRoute>
            <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
            {/* Notification Banner */}
            {showNotification && (
                <div className="bg-green-600 text-white px-6 py-3 text-center relative">
                    <div className="flex items-center justify-center gap-2">
                        <Bell className="w-4 h-4" />
                        <span>{notificationMessage}</span>
                    </div>
                    <button
                        onClick={() => setShowNotification(false)}
                        className="absolute right-4 top-1/2 transform -translate-y-1/2 text-white hover:text-gray-200"
                    >
                        <XCircle className="w-4 h-4" />
                    </button>
                </div>
            )}

            {/* Header */}
            <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
                <div className="container mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 bg-black rounded-lg flex items-center justify-center">
                                <Code2 className="w-4 h-4 text-white" />
                            </div>
                            <div>
                                <h1 className="text-xl font-semibold text-slate-900">Async Code</h1>
                                <p className="text-sm text-slate-500">Manage parallel AI code agents (Codex & Claude)</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-4">
                            <Link href="/projects">
                                <Button variant="outline" className="gap-2">
                                    <FolderGit2 className="w-4 h-4" />
                                    Projects
                                </Button>
                            </Link>
                            
                            <Link href="/settings">
                                <Button variant="outline" className="gap-2">
                                    <Settings className="w-4 h-4" />
                                    Settings
                                </Button>
                            </Link>
                            
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Avatar className="cursor-pointer">
                                        <AvatarFallback>
                                            {user?.email ? 
                                                user.email.split('@')[0].slice(0, 2).toUpperCase() : 
                                                'U'
                                            }
                                        </AvatarFallback>
                                    </Avatar>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end" className="w-56">
                                    <div className="p-2">
                                        <p className="text-sm font-medium">{user?.email}</p>
                                        <p className="text-xs text-slate-500">Signed in</p>
                                    </div>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem onClick={signOut} className="gap-2 text-red-600">
                                        <LogOut className="w-4 h-4" />
                                        Sign Out
                                    </DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </div>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="container mx-auto px-6 py-8 max-w-8xl">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Left Column - Task Creation */}
                    <div className="lg:col-span-2 space-y-6">
                        {/* Main Input Card */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Code Generation Prompt</CardTitle>
                                <CardDescription>
                                    Describe the feature, bug fix, or enhancement you want AI to implement
                                </CardDescription>
                                {!githubToken.trim() && (
                                    <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
                                        <div className="flex items-start gap-2 text-amber-800">
                                            <Github className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                            <div className="text-sm">
                                                <strong>GitHub Token Required:</strong> Please configure your GitHub token in{" "}
                                                <Link href="/settings" className="underline hover:text-amber-900">
                                                    Settings
                                                </Link>{" "}
                                                to enable code generation.
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="space-y-2">
                                    <Label htmlFor="prompt">Your Prompt</Label>
                                    <Textarea
                                        id="prompt"
                                        value={prompt}
                                        onChange={(e) => setPrompt(e.target.value)}
                                        placeholder="e.g., Add a dark mode toggle to the navigation bar with persistent user preferences..."
                                        className="min-h-[120px] resize-none"
                                    />
                                </div>

                                <Separator />

                                {/* Repository Configuration */}
                                <div className="space-y-4">
                                    <h3 className="font-medium text-slate-900 flex items-center gap-2">
                                        <Github className="w-4 h-4" />
                                        Repository Settings
                                    </h3>
                                    
                                    {/* Project Selection - Full Width */}
                                    <div className="space-y-2">
                                        <Label htmlFor="project" className="flex items-center gap-2">
                                            <FolderGit2 className="w-3 h-3" />
                                            Project
                                        </Label>
                                        <Select value={selectedProject} onValueChange={setSelectedProject}>
                                            <SelectTrigger id="project" className="w-full">
                                                <SelectValue placeholder="Select a project" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {projects.map((project) => (
                                                    <SelectItem key={project.id} value={project.id.toString()}>
                                                        <div className="flex items-center gap-2 min-w-0">
                                                            <Github className="w-3 h-3 flex-shrink-0" />
                                                            <span className="truncate">{project.name}</span>
                                                            <span className="text-slate-500 text-xs flex-shrink-0">
                                                                ({project.repo_owner}/{project.repo_name})
                                                            </span>
                                                        </div>
                                                    </SelectItem>
                                                ))}
                                                <SelectItem value="custom">Custom Repository URL</SelectItem>
                                            </SelectContent>
                                        </Select>
                                        {projects.length === 0 && (
                                            <p className="text-sm text-slate-500">
                                                No projects found.{" "}
                                                <Link href="/projects" className="text-blue-600 hover:underline">
                                                    Create a project first
                                                </Link>
                                            </p>
                                        )}
                                    </div>

                                    {/* Branch and Model in a responsive grid */}
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label htmlFor="branch" className="flex items-center gap-2">
                                                <GitBranch className="w-3 h-3" />
                                                Branch
                                            </Label>
                                            <Input
                                                id="branch"
                                                value={branch}
                                                onChange={(e) => setBranch(e.target.value)}
                                                placeholder="main"
                                                className="w-full"
                                            />
                                        </div>
                                        
                                        <div className="space-y-2">
                                            <Label htmlFor="model" className="flex items-center gap-2">
                                                <Code2 className="w-3 h-3" />
                                                Code Agent
                                            </Label>
                                            <Select value={model} onValueChange={setModel}>
                                                <SelectTrigger id="model" className="w-full">
                                                    <SelectValue placeholder="Select an AI model" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="claude">
                                                        <div className="flex items-center gap-3">
                                                            <ClaudeIcon className="w-4 h-4 flex-shrink-0" />
                                                            <div className="flex items-center gap-2">
                                                                <span className="font-medium">Claude Code</span>
                                                                <span className="text-xs text-slate-500">• Anthropic's agentic coding tool</span>
                                                            </div>
                                                        </div>
                                                    </SelectItem>
                                                    <SelectItem value="codex">
                                                        <div className="flex items-center gap-3">
                                                            <OpenAIIcon className="w-4 h-4 flex-shrink-0" />
                                                            <div className="flex items-center gap-2">
                                                                <span className="font-medium">Codex</span>
                                                                <span className="text-xs text-slate-500">• OpenAI's lightweight coding agent</span>
                                                            </div>
                                                        </div>
                                                    </SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex justify-start pt-2">
                                    <Button
                                        onClick={handleStartTask}
                                        disabled={isLoading || !selectedProject || !prompt.trim() || !githubToken.trim()}
                                        className="gap-2 rounded-full min-w-[100px]"
                                    >
                                        <Code2 className="w-4 h-4" />
                                        {isLoading ? 'Coding...' : 'Code'}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Running Tasks Summary */}
                        {tasks.filter(task => task.status === "running" || task.status === "pending").length > 0 && (
                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <AlertCircle className="w-5 h-5 text-blue-600" />
                                        Active Tasks
                                    </CardTitle>
                                    <CardDescription>
                                        {tasks.filter(task => task.status === "running" || task.status === "pending").length} tasks currently running
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                                        <div className="flex items-center gap-3">
                                            <div className="animate-spin">
                                                <AlertCircle className="w-5 h-5 text-blue-600" />
                                            </div>
                                            <div>
                                                <div className="font-medium text-blue-900">AI agents are working on your code...</div>
                                                <div className="text-sm text-blue-700 mt-1">
                                                    You can start additional tasks or check individual task progress in the task list.
                                                </div>
                                            </div>
                                        </div>
                                        <div className="mt-3 bg-blue-100 rounded-full h-2">
                                            <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{width: '60%'}}></div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    </div>

                    {/* Right Column - Task List */}
                    <div className="space-y-6">
                        <Card>
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <CardTitle className="text-lg">All Tasks</CardTitle>
                                    <Link href="/tasks">
                                        <Button variant="outline" size="sm">View All</Button>
                                    </Link>
                                </div>
                                <CardDescription>
                                    Track all your automation tasks
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-3 max-h-[500px] overflow-y-auto">
                                {tasks.length === 0 ? (
                                    <div className="text-center py-8 text-slate-500">
                                        <Code2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
                                        <p className="text-sm">No tasks yet</p>
                                        <p className="text-xs">Start your first automation above</p>
                                    </div>
                                ) : (
                                    tasks.slice(0, 10).map((task) => (
                                        <div key={task.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <TaskStatusBadge status={task.status || ''} />
                                                    {task.pr_url && task.pr_number && (
                                                        <PRStatusBadge 
                                                            prUrl={task.pr_url}
                                                            prNumber={task.pr_number}
                                                            prBranch={task.pr_branch}
                                                            variant="badge"
                                                            size="sm"
                                                        />
                                                    )}
                                                    <span className="text-xs text-slate-500 flex items-center gap-1">
                                                        #{task.id} • {getAgentIcon(task.agent || '')} {task.agent?.toUpperCase()}
                                                    </span>
                                                </div>
                                                <p className="text-sm font-medium text-slate-900 truncate">
                                                    {(task.chat_messages as any[])?.[0]?.content?.substring(0, 50) || ''}...
                                                </p>
                                                <div className="flex items-center gap-2 text-xs text-slate-500 mt-1">
                                                    {task.project ? (
                                                        <>
                                                            <FolderGit2 className="w-3 h-3" />
                                                            {task.project.repo_name}
                                                        </>
                                                    ) : (
                                                        <>
                                                            <Github className="w-3 h-3" />
                                                            Custom
                                                        </>
                                                    )}
                                                    <span>•</span>
                                                    <span>{new Date(task.created_at || '').toLocaleDateString()}</span>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {task.status === "completed" && (
                                                    <CheckCircle className="w-4 h-4 text-green-600" />
                                                )}
                                                {task.status === "running" && (
                                                    <div className="animate-spin">
                                                        <AlertCircle className="w-4 h-4 text-blue-600" />
                                                    </div>
                                                )}
                                                <Link href={`/tasks/${task.id}`}>
                                                    <Button variant="ghost" size="sm">
                                                        <Eye className="w-3 h-3" />
                                                    </Button>
                                                </Link>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </CardContent>
                        </Card>

                    </div>
                </div>
            </main>
        </div>
        </ProtectedRoute>
    );
}