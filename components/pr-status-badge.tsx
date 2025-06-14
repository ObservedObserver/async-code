import { GitPullRequest, ExternalLink, GitMerge } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PRStatusBadgeProps {
    prUrl?: string | null;
    prNumber?: number | null;
    prBranch?: string | null;
    prStatus?: "open" | "merged" | "closed";
    variant?: "badge" | "button";
    size?: "sm" | "default";
    className?: string;
}

export function PRStatusBadge({ 
    prUrl, 
    prNumber, 
    prBranch, 
    prStatus = "open",
    variant = "badge",
    size = "sm",
    className 
}: PRStatusBadgeProps) {
    if (!prUrl || !prNumber) {
        return null;
    }

    const handleClick = () => {
        if (prUrl) {
            window.open(prUrl, '_blank', 'noopener,noreferrer');
        }
    };

    const getStatusConfig = (status: string) => {
        switch (status) {
            case "merged":
                return {
                    icon: <GitMerge className={cn(size === "sm" ? "w-3 h-3" : "w-4 h-4")} />,
                    text: "Merged",
                    className: "bg-purple-100 text-purple-700 border-purple-200 hover:bg-purple-200"
                };
            case "open":
                return {
                    icon: <GitPullRequest className={cn(size === "sm" ? "w-3 h-3" : "w-4 h-4")} />,
                    text: "Open",
                    className: "bg-green-100 text-green-700 border-green-200 hover:bg-green-200"
                };
            case "closed":
                return {
                    icon: <GitPullRequest className={cn(size === "sm" ? "w-3 h-3" : "w-4 h-4")} />,
                    text: "Closed",
                    className: "bg-red-100 text-red-700 border-red-200 hover:bg-red-200"
                };
            default:
                return {
                    icon: <GitPullRequest className={cn(size === "sm" ? "w-3 h-3" : "w-4 h-4")} />,
                    text: "PR",
                    className: "bg-blue-100 text-blue-700 border-blue-200 hover:bg-blue-200"
                };
        }
    };

    const config = getStatusConfig(prStatus);

    if (variant === "button") {
        return (
            <Button 
                onClick={handleClick}
                variant="outline" 
                size={size}
                className={cn("gap-2 transition-colors", config.className, className)}
            >
                {config.icon}
                <span>#{prNumber}</span>
                <ExternalLink className={cn(size === "sm" ? "w-3 h-3" : "w-4 h-4")} />
            </Button>
        );
    }

    return (
        <Badge 
            onClick={handleClick}
            variant="outline" 
            className={cn(
                "gap-1 cursor-pointer transition-all hover:shadow-sm",
                config.className,
                size === "sm" ? "text-xs px-2 py-1" : "text-sm px-3 py-1",
                className
            )}
        >
            {config.icon}
            <span>#{prNumber}</span>
            <ExternalLink className={cn(size === "sm" ? "w-2.5 h-2.5" : "w-3 h-3")} />
        </Badge>
    );
}