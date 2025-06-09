"use client";

import { useState, useEffect } from "react";
import { ArrowLeft, Github, Clock, CheckCircle, XCircle, AlertCircle, Eye, Code2, Filter, Search, Calendar, FolderGit2, ExternalLink, RefreshCw } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ProtectedRoute } from "@/components/protected-route";
import { TaskStatusBadge } from "@/components/task-status-badge";
import { PRStatusBadge } from "@/components/pr-status-badge";
import { useAuth } from "@/contexts/auth-context";
import { ApiService } from "@/lib/api-service";
import { Task, Project } from "@/types";

interface TaskWithProject extends Task {
    project?: Project
}

export default function TasksPage() {
    const { user } = useAuth();
    const [tasks, setTasks] = useState<TaskWithProject[]>([]);
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState("");
    const [statusFilter, setStatusFilter] = useState("all");
    const [projectFilter, setProjectFilter] = useState("all");
    const [sortBy, setSortBy] = useState("created_at");

    useEffect(() => {
        if (user?.id) {
            loadData();
        }
    }, [user?.id]);

    // Poll for status updates of running tasks
    useEffect(() => {
        if (!user?.id) return;

        const runningTasks = tasks.filter(task => task.status === "running" || task.status === "pending");
        if (runningTasks.length === 0) return;

        const interval = setInterval(async () => {
            try {
                const updatedTasks = await Promise.all(
                    runningTasks.map(task => ApiService.getTaskStatus(user.id, task.id))
                );

                setTasks(prevTasks => 
                    prevTasks.map(task => {
                        const updated = updatedTasks.find(t => t.id === task.id);
                        return updated ? { ...task, ...updated } : task;
                    })
                );
            } catch (error) {
                console.error('Error polling task status:', error);
            }
        }, 3000);

        return () => clearInterval(interval);
    }, [tasks, user?.id]);

    const loadData = async () => {
        if (!user?.id) return;
        
        try {
            setLoading(true);
            const [taskData, projectData] = await Promise.all([
                ApiService.getTasks(user.id),
                ApiService.getProjects(user.id)
            ]);

            // Enhance tasks with project data
            const tasksWithProjects = taskData.map((task: any) => ({
                ...task,
                project: projectData.find(p => p.id === task.project_id)
            }));

            setTasks(tasksWithProjects);
            setProjects(projectData);
        } catch (error) {
            console.error('Error loading data:', error);
        } finally {
            setLoading(false);
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
            case "pending": return <Clock className="w-4 h-4" />;
            case "running": return <AlertCircle className="w-4 h-4" />;
            case "completed": return <CheckCircle className="w-4 h-4" />;
            case "failed": return <XCircle className="w-4 h-4" />;
            default: return null;
        }
    };

    const getPromptFromTask = (task: TaskWithProject): string => {
        if (task.chat_messages && 
            Array.isArray(task.chat_messages) && 
            task.chat_messages.length > 0) {
            const firstMessage = task.chat_messages[0];
            if (firstMessage && 
                typeof firstMessage === 'object' && 
                firstMessage !== null &&
                'content' in firstMessage && 
                typeof firstMessage.content === 'string') {
                return firstMessage.content;
            }
        }
        return 'No prompt available';
    };

    // Filter and sort tasks
    const filteredTasks = tasks
        .filter(task => {
            // Search filter
            if (searchQuery) {
                const prompt = getPromptFromTask(task).toLowerCase();
                const projectName = task.project?.name?.toLowerCase() || '';
                const repoUrl = task.repo_url?.toLowerCase() || '';
                const query = searchQuery.toLowerCase();
                
                if (!prompt.includes(query) && !projectName.includes(query) && !repoUrl.includes(query)) {
                    return false;
                }
            }

            // Status filter
            if (statusFilter !== "all" && task.status !== statusFilter) {
                return false;
            }

            // Project filter
            if (projectFilter !== "all") {
                if (projectFilter === "no-project" && task.project_id) {
                    return false;
                }
                if (projectFilter !== "no-project" && task.project_id?.toString() !== projectFilter) {
                    return false;
                }
            }

            return true;
        })
        .sort((a, b) => {
            switch (sortBy) {
                case "created_at":
                    return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
                case "status":
                    return (a.status || '').localeCompare(b.status || '');
                case "project":
                    return (a.project?.name || '').localeCompare(b.project?.name || '');
                default:
                    return 0;
            }
        });

    const statusCounts = {
        all: tasks.length,
        pending: tasks.filter(t => t.status === "pending").length,
        running: tasks.filter(t => t.status === "running").length,
        completed: tasks.filter(t => t.status === "completed").length,
        failed: tasks.filter(t => t.status === "failed").length,
    };

    if (loading) {
        return (
            <ProtectedRoute>
                <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
                    <div className="text-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900 mx-auto"></div>
                        <p className="text-slate-600 mt-2">Loading tasks...</p>
                    </div>
                </div>
            </ProtectedRoute>
        );
    }

    return (
        <ProtectedRoute>
            <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
                {/* Header */}
                <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
                    <div className="container mx-auto px-6 py-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <Link href="/" className="text-slate-600 hover:text-slate-900 flex items-center gap-2">
                                    <ArrowLeft className="w-4 h-4" />
                                    Back to Dashboard
                                </Link>
                                <div>
                                    <h1 className="text-xl font-semibold text-slate-900">All Tasks</h1>
                                    <p className="text-sm text-slate-500">
                                        {filteredTasks.length} of {tasks.length} tasks
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <Button onClick={loadData} variant="outline" size="sm" className="gap-2">
                                    <RefreshCw className="w-4 h-4" />
                                    Refresh
                                </Button>
                                <Link href="/">
                                    <Button className="gap-2">
                                        <Code2 className="w-4 h-4" />
                                        New Task
                                    </Button>
                                </Link>
                            </div>
                        </div>
                    </div>
                </header>

                {/* Main Content */}
                <main className="container mx-auto px-6 py-8 max-w-7xl">
                    {/* Status Overview Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
                        <Card className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-medium text-slate-600">Total</p>
                                    <p className="text-2xl font-bold text-slate-900">{statusCounts.all}</p>
                                </div>
                                <Code2 className="w-8 h-8 text-slate-400" />
                            </div>
                        </Card>
                        <Card className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-medium text-slate-600">Pending</p>
                                    <p className="text-2xl font-bold text-amber-600">{statusCounts.pending}</p>
                                </div>
                                <Clock className="w-8 h-8 text-amber-400" />
                            </div>
                        </Card>
                        <Card className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-medium text-slate-600">Running</p>
                                    <p className="text-2xl font-bold text-blue-600">{statusCounts.running}</p>
                                </div>
                                <AlertCircle className="w-8 h-8 text-blue-400" />
                            </div>
                        </Card>
                        <Card className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-medium text-slate-600">Completed</p>
                                    <p className="text-2xl font-bold text-green-600">{statusCounts.completed}</p>
                                </div>
                                <CheckCircle className="w-8 h-8 text-green-400" />
                            </div>
                        </Card>
                        <Card className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-medium text-slate-600">Failed</p>
                                    <p className="text-2xl font-bold text-red-600">{statusCounts.failed}</p>
                                </div>
                                <XCircle className="w-8 h-8 text-red-400" />
                            </div>
                        </Card>
                    </div>

                    {/* Filters and Search */}
                    <Card className="mb-6">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Filter className="w-5 h-5" />
                                Filters
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-slate-700">Search</label>
                                    <div className="relative">
                                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
                                        <Input
                                            placeholder="Search tasks..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-10"
                                        />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-slate-700">Status</label>
                                    <Select value={statusFilter} onValueChange={setStatusFilter}>
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Statuses</SelectItem>
                                            <SelectItem value="pending">Pending</SelectItem>
                                            <SelectItem value="running">Running</SelectItem>
                                            <SelectItem value="completed">Completed</SelectItem>
                                            <SelectItem value="failed">Failed</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-slate-700">Project</label>
                                    <Select value={projectFilter} onValueChange={setProjectFilter}>
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Projects</SelectItem>
                                            <SelectItem value="no-project">No Project</SelectItem>
                                            {projects.map((project) => (
                                                <SelectItem key={project.id} value={project.id.toString()}>
                                                    {project.name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-slate-700">Sort By</label>
                                    <Select value={sortBy} onValueChange={setSortBy}>
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="created_at">Date Created</SelectItem>
                                            <SelectItem value="status">Status</SelectItem>
                                            <SelectItem value="project">Project</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Tasks List */}
                    {filteredTasks.length === 0 ? (
                        <Card className="text-center py-12">
                            <CardContent>
                                <Code2 className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                                <h3 className="text-lg font-semibold text-slate-900 mb-2">No tasks found</h3>
                                <p className="text-slate-600 mb-6">
                                    {tasks.length === 0 
                                        ? "You haven't created any tasks yet. Start by creating your first task."
                                        : "No tasks match your current filters. Try adjusting your search criteria."
                                    }
                                </p>
                                <Link href="/">
                                    <Button className="gap-2">
                                        <Code2 className="w-4 h-4" />
                                        Create Your First Task
                                    </Button>
                                </Link>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-4">
                            {filteredTasks.map((task) => (
                                <Card key={task.id} className="hover:shadow-md transition-shadow">
                                    <CardContent className="p-6">
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-3 mb-3">
                                                    <TaskStatusBadge status={task.status || ''} />
                                                    {task.pr_url && task.pr_number && (
                                                        <PRStatusBadge 
                                                            prUrl={task.pr_url}
                                                            prNumber={task.pr_number}
                                                            prBranch={task.pr_branch}
                                                            variant="badge"
                                                            size="default"
                                                        />
                                                    )}
                                                    <span className="text-sm text-slate-500">
                                                        Task #{task.id}
                                                    </span>
                                                    <span className="text-sm text-slate-500">•</span>
                                                    <span className="text-sm text-slate-500">
                                                        {task.agent?.toUpperCase()}
                                                    </span>
                                                    {task.project && (
                                                        <>
                                                            <span className="text-sm text-slate-500">•</span>
                                                            <div className="flex items-center gap-1 text-sm text-slate-500">
                                                                <FolderGit2 className="w-3 h-3" />
                                                                {task.project.repo_owner}/{task.project.repo_name}
                                                            </div>
                                                        </>
                                                    )}
                                                </div>
                                                
                                                <h3 className="font-medium text-slate-900 mb-2 line-clamp-2">
                                                    {getPromptFromTask(task)}
                                                </h3>
                                                
                                                <div className="flex items-center gap-4 text-sm text-slate-500 mb-3">
                                                    <div className="flex items-center gap-1">
                                                        <Github className="w-3 h-3" />
                                                        <span className="truncate max-w-[200px]">
                                                            {task.repo_url}
                                                        </span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <Calendar className="w-3 h-3" />
                                                        <span>{new Date(task.created_at || '').toLocaleDateString()}</span>
                                                    </div>
                                                </div>

                                                {task.error && (
                                                    <div className="p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700 mb-3">
                                                        <strong>Error:</strong> {task.error}
                                                    </div>
                                                )}

                                                {task.status === "running" && (
                                                    <div className="flex items-center gap-2 p-2 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700">
                                                        <div className="animate-spin">
                                                            <AlertCircle className="w-3 h-3" />
                                                        </div>
                                                        <span>AI is working on this task...</span>
                                                    </div>
                                                )}
                                            </div>
                                            
                                            <div className="flex items-center gap-2 ml-4">
                                                <Link href={`/tasks/${task.id}`}>
                                                    <Button variant="outline" size="sm" className="gap-2">
                                                        <Eye className="w-4 h-4" />
                                                        View
                                                    </Button>
                                                </Link>
                                                {task.pr_url && task.pr_number && (
                                                    <PRStatusBadge 
                                                        prUrl={task.pr_url}
                                                        prNumber={task.pr_number}
                                                        prBranch={task.pr_branch}
                                                        variant="button"
                                                        size="sm"
                                                    />
                                                )}
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </main>
            </div>
        </ProtectedRoute>
    );
}