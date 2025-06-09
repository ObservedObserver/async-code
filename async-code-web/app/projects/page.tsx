"use client";

import { useState, useEffect } from "react";
import { Plus, Settings, Trash2, Activity, ExternalLink, Github } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { ProtectedRoute } from "@/components/protected-route";
import { useAuth } from "@/contexts/auth-context";
import { ApiService } from "@/lib/api-service";
import { Project } from "@/types";
import { toast } from "sonner";

interface ProjectWithStats extends Project {
    task_count?: number
    completed_tasks?: number
    active_tasks?: number
}

export default function ProjectsPage() {
    const { user } = useAuth();
    const [projects, setProjects] = useState<ProjectWithStats[]>([]);
    const [loading, setLoading] = useState(true);
    const [createDialogOpen, setCreateDialogOpen] = useState(false);
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        repo_url: ''
    });

    useEffect(() => {
        if (user?.id) {
            loadProjects();
        }
    }, [user?.id]);

    const loadProjects = async () => {
        if (!user?.id) return;
        
        try {
            setLoading(true);
            const data = await ApiService.getProjects(user.id);
            setProjects(data);
        } catch (error) {
            console.error('Error loading projects:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateProject = async (e: React.FormEvent) => {
        e.preventDefault();
        
        if (!user?.id) return;
        
        try {
            await ApiService.createProject(user.id, {
                name: formData.name,
                description: formData.description,
                repo_url: formData.repo_url
            });

            setFormData({ name: '', description: '', repo_url: '' });
            setCreateDialogOpen(false);
            loadProjects();
        } catch (error) {
            console.error('Error creating project:', error);
            toast.error('Error creating project. Please check the GitHub URL format.');
        }
    };

    const handleDeleteProject = async (id: number) => {
        if (!user?.id) return;
        
        if (!confirm('Are you sure you want to delete this project? This will also delete all associated tasks.')) {
            return;
        }

        try {
            await ApiService.deleteProject(user.id, id);
            loadProjects();
        } catch (error) {
            console.error('Error deleting project:', error);
            toast.error('Error deleting project');
        }
    };

    if (loading) {
        return (
            <ProtectedRoute>
                <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
                    <div className="text-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900 mx-auto"></div>
                        <p className="text-slate-600 mt-2">Loading projects...</p>
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
                                <Link href="/" className="text-slate-600 hover:text-slate-900">
                                    ← Back to Dashboard
                                </Link>
                                <div>
                                    <h1 className="text-2xl font-semibold text-slate-900">Projects</h1>
                                    <p className="text-sm text-slate-500">Manage your GitHub repositories and automation tasks</p>
                                </div>
                            </div>
                            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                                <DialogTrigger asChild>
                                    <Button className="gap-2">
                                        <Plus className="w-4 h-4" />
                                        New Project
                                    </Button>
                                </DialogTrigger>
                                <DialogContent>
                                    <DialogHeader>
                                        <DialogTitle>Create New Project</DialogTitle>
                                        <DialogDescription>
                                            Add a GitHub repository to start automating with AI
                                        </DialogDescription>
                                    </DialogHeader>
                                    <form onSubmit={handleCreateProject} className="space-y-4">
                                        <div className="space-y-2">
                                            <Label htmlFor="name">Project Name</Label>
                                            <Input
                                                id="name"
                                                value={formData.name}
                                                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                                                placeholder="My Awesome Project"
                                                required
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="repo_url">GitHub Repository URL</Label>
                                            <Input
                                                id="repo_url"
                                                type="url"
                                                value={formData.repo_url}
                                                onChange={(e) => setFormData(prev => ({ ...prev, repo_url: e.target.value }))}
                                                placeholder="https://github.com/owner/repo"
                                                required
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="description">Description (Optional)</Label>
                                            <Textarea
                                                id="description"
                                                value={formData.description}
                                                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                                                placeholder="Brief description of your project..."
                                                rows={3}
                                            />
                                        </div>
                                        <div className="flex justify-end gap-2">
                                            <Button type="button" variant="outline" onClick={() => setCreateDialogOpen(false)}>
                                                Cancel
                                            </Button>
                                            <Button type="submit">Create Project</Button>
                                        </div>
                                    </form>
                                </DialogContent>
                            </Dialog>
                        </div>
                    </div>
                </header>

                {/* Main Content */}
                <main className="container mx-auto px-6 py-8">
                    {projects.length === 0 ? (
                        <div className="text-center py-12">
                            <Github className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                            <h3 className="text-xl font-semibold text-slate-900 mb-2">No projects yet</h3>
                            <p className="text-slate-600 mb-6">Create your first project to start automating with AI</p>
                            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                                <DialogTrigger asChild>
                                    <Button size="lg" className="gap-2">
                                        <Plus className="w-4 h-4" />
                                        Create Your First Project
                                    </Button>
                                </DialogTrigger>
                            </Dialog>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {projects.map((project) => (
                                <Card key={project.id} className="hover:shadow-lg transition-shadow">
                                    <CardHeader>
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1">
                                                <CardTitle className="text-lg">{project.name}</CardTitle>
                                                <CardDescription className="flex items-center gap-1 mt-1">
                                                    <Github className="w-3 h-3" />
                                                    {project.repo_owner}/{project.repo_name}
                                                </CardDescription>
                                            </div>
                                            <div className="flex gap-1">
                                                <Button variant="ghost" size="sm" asChild>
                                                    <Link href={`/projects/${project.id}`}>
                                                        <Settings className="w-4 h-4" />
                                                    </Link>
                                                </Button>
                                                <Button 
                                                    variant="ghost" 
                                                    size="sm"
                                                    onClick={() => handleDeleteProject(project.id)}
                                                    className="text-red-600 hover:text-red-700"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        </div>
                                        {project.description && (
                                            <p className="text-sm text-slate-600 mt-2">{project.description}</p>
                                        )}
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-4">
                                            {/* Project Stats */}
                                            <div className="grid grid-cols-3 gap-2 text-center">
                                                <div className="p-2 bg-slate-50 rounded-lg">
                                                    <div className="text-lg font-semibold text-slate-900">{project.task_count || 0}</div>
                                                    <div className="text-xs text-slate-500">Total Tasks</div>
                                                </div>
                                                <div className="p-2 bg-green-50 rounded-lg">
                                                    <div className="text-lg font-semibold text-green-700">{project.completed_tasks || 0}</div>
                                                    <div className="text-xs text-green-600">Completed</div>
                                                </div>
                                                <div className="p-2 bg-blue-50 rounded-lg">
                                                    <div className="text-lg font-semibold text-blue-700">{project.active_tasks || 0}</div>
                                                    <div className="text-xs text-blue-600">Active</div>
                                                </div>
                                            </div>

                                            {/* Actions */}
                                            <div className="flex gap-2">
                                                <Button variant="outline" size="sm" className="flex-1" asChild>
                                                    <Link href={`/projects/${project.id}/tasks`}>
                                                        <Activity className="w-4 h-4 mr-1" />
                                                        View Tasks
                                                    </Link>
                                                </Button>
                                                <Button variant="outline" size="sm" asChild>
                                                    <a href={project.repo_url} target="_blank" rel="noopener noreferrer">
                                                        <ExternalLink className="w-4 h-4" />
                                                    </a>
                                                </Button>
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