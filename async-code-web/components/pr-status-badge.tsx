import { GitPullRequest, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PRStatusBadgeProps {
    prUrl?: string | null;
    prNumber?: number | null;
    prBranch?: string | null;
    variant?: "badge" | "button";
    size?: "sm" | "default";
    className?: string;
}

export function PRStatusBadge({ 
    prUrl, 
    prNumber, 
    prBranch, 
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

    if (variant === "button") {
        return (
            <Button 
                onClick={handleClick}
                variant="outline" 
                size={size}
                className={cn("gap-2 transition-colors hover:bg-blue-50 hover:border-blue-300", className)}
            >
                <GitPullRequest className="w-4 h-4 text-blue-600" />
                <span className="text-blue-600">PR #{prNumber}</span>
                <ExternalLink className="w-3 h-3 text-blue-600" />
            </Button>
        );
    }

    return (
        <Badge 
            onClick={handleClick}
            variant="outline" 
            className={cn(
                "gap-1 cursor-pointer transition-all hover:shadow-sm",
                "bg-blue-50 border-blue-200 text-blue-700 hover:bg-blue-100 hover:border-blue-300",
                size === "sm" ? "text-xs px-2 py-1" : "text-sm px-3 py-1",
                className
            )}
        >
            <GitPullRequest className={cn(size === "sm" ? "w-3 h-3" : "w-4 h-4")} />
            <span>PR #{prNumber}</span>
            <ExternalLink className={cn(size === "sm" ? "w-2.5 h-2.5" : "w-3 h-3")} />
        </Badge>
    );
}